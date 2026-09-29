"""Running suites: the pilot, the frozen main experiment, and the freeze (SPEC §4, §7.4).

Results layout (one directory per suite):
    manifest.json           configuration, frozen hash, exploratory flag
    events/<run_id>.jsonl   append-only event log per run (the source of truth)
    runs.jsonl              per-run metrics, recomputed from each log (a convenience copy)
    errors.jsonl            infrastructure errors, one line per failed attempt
"""

from __future__ import annotations

import json
import random
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

from devagents.config import FROZEN_PATH, SPEC_PATH, Constants, default_constants, load_frozen, sha256_file
from devagents.environment.sources import InformationEnvironment
from devagents.environment.tasks import PILOT_TASKS, TASKS, Task
from devagents.environment.world import load_world
from devagents.evals.analysis import criteria_check
from devagents.evals.calibrate import Assumptions, calibrate, label, measure
from devagents.evals.metrics import metrics_from_events
from devagents.runtime.events import EventLog, read_events
from devagents.runtime.runtime import MODES, ReserveViolation, Run, RunConfig, policy_config

MAX_ATTEMPTS = 4  # the original attempt plus up to 3 retries (SPEC §8)


def is_infra_error(exc: BaseException) -> bool:
    """The exhaustive infrastructure-error list of SPEC §8. Everything else is a policy outcome or a bug."""
    if isinstance(exc, ReserveViolation):
        return True
    try:
        import anthropic
    except ImportError:
        return False
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    return isinstance(exc, anthropic.APIStatusError) and (exc.status_code == 429 or exc.status_code >= 500)


def plan(tasks: list[Task], constants: Constants, modes: list[str], repeats: int, regimes: list[str] | None = None,
         seed: int = 0, frozen_sha: str = "") -> list[RunConfig]:
    """Blocks of (repeat, task, regime), each running every mode in a seeded random order (SPEC §4)."""
    rng = random.Random(seed)
    configs = []
    for rep in range(repeats):
        for task in tasks:
            for name in regimes or list(constants.regimes):
                block = list(modes)
                rng.shuffle(block)
                configs += [RunConfig(task, constants.regimes[name], m, compute=constants.compute, coord=constants.coord,
                                      repeat=rep, frozen_sha=frozen_sha) for m in block]
    return configs


def run_one(cfg: RunConfig, policy, constants: Constants, out_dir: Path) -> dict:
    """Execute one run, retrying infrastructure errors with the identical config. Returns a result line."""
    errors = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        path = out_dir / "events" / f"{cfg.run_id}.jsonl"
        if path.exists():
            path.unlink()
        log = EventLog(cfg.run_id, path)
        try:
            Run(cfg, policy, InformationEnvironment(load_world(), constants.sources), log).execute()
            log.close()
            return {"run_id": cfg.run_id, "ok": True, "metrics": metrics_from_events(log.events), "errors": errors}
        except Exception as exc:  # classified below; anything that is not infrastructure propagates
            log.close()
            if not is_infra_error(exc):
                raise
            errors.append({"run_id": cfg.run_id, "attempt": attempt, "error": f"{type(exc).__name__}: {exc}"})
            time.sleep(min(30, 2 ** attempt))
    return {"run_id": cfg.run_id, "ok": False, "errors": errors}


RESUME_KEYS = ("kind", "exploratory", "frozen_sha", "planned_runs", "policy", "constants")


def run_suite(configs: list[RunConfig], policy, constants: Constants, out_dir: Path, manifest: dict,
              workers: int = 1) -> dict:
    out_dir = Path(out_dir)
    (out_dir / "events").mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = {**manifest, "policy": policy_config(policy)}
    if manifest_path.exists():  # resuming: only the identical suite may continue in this directory
        old = json.loads(manifest_path.read_text())
        diff = [k for k in RESUME_KEYS if old.get(k) != manifest.get(k)]
        if diff:
            raise SystemExit(f"{out_dir} holds a different suite (differs in {', '.join(diff)}); use another --out.")
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    done = set()
    runs_path = out_dir / "runs.jsonl"
    if runs_path.exists():  # resume: completed runs are never repeated
        done = {json.loads(line)["run_id"] for line in runs_path.read_text().splitlines() if line.strip()}
    todo = [c for c in configs if c.run_id not in done]
    lock = threading.Lock()
    counter = {"done": 0, "failed": 0}

    def work(cfg: RunConfig):
        res = run_one(cfg, policy, constants, out_dir)
        with lock:
            with open(out_dir / "errors.jsonl", "a") as fh:
                for e in res["errors"]:
                    fh.write(json.dumps(e) + "\n")
            if res["ok"]:
                with open(runs_path, "a") as fh:
                    fh.write(json.dumps(res["metrics"]) + "\n")
                counter["done"] += 1
                m = res["metrics"]
                print(f"[{counter['done'] + counter['failed']}/{len(todo)}] {cfg.run_id}: {m['outcome']} q={m['quality']:.0f} "
                      f"${m['money_usd']:.4f} {m['elapsed_s']:.0f}s agents={m['agents']}", flush=True)
            else:
                counter["failed"] += 1
                print(f"[{counter['done'] + counter['failed']}/{len(todo)}] {cfg.run_id}: INFRASTRUCTURE ERROR after "
                      f"{MAX_ATTEMPTS} attempts", flush=True)

    print(f"{len(configs)} planned runs, {len(done)} already complete, {len(todo)} to run -> {out_dir}", flush=True)
    if workers > 1:
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(work, todo))
    else:
        for cfg in todo:
            work(cfg)
    return {"planned": len(configs), "completed": len(done) + counter["done"], "failed": counter["failed"]}


def make_manifest(kind: str, configs: list[RunConfig], constants: Constants, exploratory: bool, frozen_sha: str) -> dict:
    return {"kind": kind, "exploratory": exploratory, "frozen_sha": frozen_sha, "spec_sha": sha256_file(SPEC_PATH),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "constants": constants.to_json(),
            "planned_runs": [c.run_id for c in configs], "modes": sorted({c.mode for c in configs}),
            "tasks": sorted({c.task.id for c in configs}), "repeats": max(c.repeat for c in configs) + 1}


# --------------------------------------------------------------------------- pilot statistics and freeze

def _quantile(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def pilot_stats(pilot_dir: Path) -> dict:
    """Token and dispersion statistics from a pilot (single and central modes only; SPEC §7.4)."""
    pilot_dir = Path(pilot_dir)
    manifest_path = pilot_dir / "manifest.json"
    if manifest_path.exists() and set(json.loads(manifest_path.read_text()).get("modes", [])) - {"single", "central"}:
        raise ValueError("the pilot manifest lists modes other than single and central (SPEC §7.4)")
    ratios, reasoning, outs, runs = [], [], [], []
    for path in sorted((pilot_dir / "events").glob("*.jsonl")):
        events = read_events(path)
        start = next((e for e in events if e["type"] == "RUN_STARTED"), None)
        if start and start["mode"] in ("developmental", "router"):  # checked for complete AND incomplete logs
            raise ValueError(f"a pilot must not contain developmental or router output (SPEC §7.4): {path.name}")
        if not any(e["type"] == "RUN_COMPLETED" for e in events):
            continue
        m = metrics_from_events(events)
        runs.append(m)
        for e in events:
            if e["type"] == "RESOURCE_CONSUMED" and e["kind"] == "llm" and e.get("est_in_tokens"):
                ratios.append(e["in_tokens"] / e["est_in_tokens"])
                reasoning.append(max(0, e["out_tokens"] - e.get("est_visible_out_tokens", 0)))
                outs.append(e["out_tokens"])
    if not runs or not ratios:
        raise ValueError(f"no completed pilot runs with token statistics in {pilot_dir}")
    single = [m for m in runs if m["mode"] == "single"]
    accuracy = {}
    for cls in ("solo", "parallel", "cross"):
        xs = [m["quality"] for m in single if m["task_class"] == cls]
        accuracy[cls] = statistics.fmean(xs) if xs else None
    # Cost as in §3.4, without the failure penalty (failures belong to the quality channel of the §7.3 model).
    # The CV is a pooled relative variance using n-1 sample variances; a median of per-group n=2 CVs is biased low.
    groups: dict = {}
    for m in runs:
        elapsed = m["elapsed_s"] if m["outcome"] == "answered" else m["deadline_s"]
        groups.setdefault((m["task_id"], m["regime"], m["mode"]), []).append(m["money_usd"] + m["value_of_time"] * elapsed)
    rel_vars = [statistics.variance(v) / statistics.fmean(v) ** 2 for v in groups.values()
                if len(v) > 1 and statistics.fmean(v) > 0]
    return {"runs": len(runs), "llm_calls": len(ratios), "input_scale": round(statistics.median(ratios), 4),
            "reasoning_tokens": int(statistics.median(reasoning)), "p90_output_tokens": int(_quantile(outs, 0.9)),
            "single_p95_elapsed_s": _quantile([m["elapsed_s"] for m in single], 0.95) if single else None,
            "single_accuracy": accuracy,
            "cost_cv": round(statistics.fmean(rel_vars) ** 0.5, 4) if rel_vars else None, "cost_cv_groups": len(rel_vars)}


def freeze(pilot_dir: Path | None = None, compute: str = "opus", out: Path = FROZEN_PATH, n_sims: int = 200,
           max_repair_steps: int = 6) -> dict:
    """Calibrate with the pilot's measurements, repair the gate mechanically if needed, run the criteria check, and
    write data/frozen.json (SPEC §7.4). No LLM is called."""
    constants = default_constants(compute)
    base, stats = Assumptions(), None
    if pilot_dir:
        stats = pilot_stats(pilot_dir)
        base = Assumptions(input_scale=stats["input_scale"], reasoning_tokens=stats["reasoning_tokens"])
        compute_opt = replace(constants.compute, min_step_tokens=max(constants.compute.min_step_tokens,
                                                                     stats["p90_output_tokens"]))
        deadline = max(next(iter(constants.regimes.values())).deadline_s, 2 * (stats["single_p95_elapsed_s"] or 0))
        constants = replace(constants, compute=compute_opt,
                            regimes={k: replace(v, deadline_s=deadline) for k, v in constants.regimes.items()})
    accuracy = {k: (v if v is not None else 0.9) for k, v in (stats or {}).get("single_accuracy", {}).items()} or None
    cost_cv = max(0.25, (stats or {}).get("cost_cv") or 0.25)
    max_docs = {t.id: t.max_doc_route for t in TASKS}

    attempts = []
    for doc_steps in range(max_repair_steps + 1):
        c_doc = replace(constants, sources=replace(constants.sources, doc_per_token_s=round(
            constants.sources.doc_per_token_s + 0.005 * doc_steps, 6)))
        meas = measure(c_doc, base)
        for u in range(max_repair_steps + 1):
            for r in range(max_repair_steps + 1):
                c = c_doc.with_value_of_time("urgent", round(c_doc.regimes["urgent"].value_of_time * 1.25 ** u, 8))
                c = c.with_value_of_time("relaxed", round(c.regimes["relaxed"].value_of_time * 0.8 ** r, 8))
                if not label(meas, c)["gate"]["passed"]:
                    continue
                cal = calibrate(c, base)  # exact re-simulation with these weights
                if not cal["gate"]["passed"]:
                    continue
                cc = criteria_check(cal["cells"], cal["gate"]["sets"], max_docs, accuracy=accuracy, cost_cv=cost_cv,
                                    n_sims=n_sims)
                steps = {"doc_per_token": doc_steps, "urgent_vot": u, "relaxed_vot": r}
                attempts.append({"steps": steps, "R": cc["R"]})
                if cc["R"] is not None:
                    frozen = {"created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "spec_sha": sha256_file(SPEC_PATH), "provisional": stats is None, "pilot": stats,
                              "assumptions": asdict(base), "constants": c.to_json(), "repair_steps": steps,
                              "calibration": {"delta": cal["delta"], "cells": cal["cells"], "gate": cal["gate"]},
                              "criteria_check": cc, "R": cc["R"], "prompt_sha": prompt_fingerprint(c)}
                    Path(out).parent.mkdir(parents=True, exist_ok=True)
                    Path(out).write_text(json.dumps(frozen, indent=1, sort_keys=True))
                    return {"ok": True, "path": str(out), "sha": sha256_file(out), "R": cc["R"], "steps": steps,
                            "provisional": stats is None}
    return {"ok": False, "attempts": attempts}


def verify_frozen(frozen: dict) -> list[str]:
    """Recompute the calibration from the frozen constants and assumptions. Any difference means the code or the
    world changed after the freeze, and the main run must not start."""
    problems = []
    constants = Constants.from_json(frozen["constants"])
    cal = calibrate(constants, Assumptions(**frozen["assumptions"]))
    numeric = ("solo_fitness", "div_fitness", "router_div_fitness", "min_margin", "max_margin", "min_incremental_gain")
    for key, cell in frozen["calibration"]["cells"].items():
        now = cal["cells"].get(key)
        if now is None or now["label"] != cell["label"]:
            problems.append(f"label of {key} changed: {cell['label']} -> {now and now['label']}")
        elif any(abs(now[k] - cell[k]) > 1e-9 for k in numeric):
            problems.append(f"calibrated values of {key} changed (world, prices, prompts or runtime differ from the freeze)")
    if frozen.get("prompt_sha") != prompt_fingerprint(constants):
        problems.append("the prompt fingerprint differs from the freeze")
    if cal["gate"]["sets"] != frozen["calibration"]["gate"]["sets"]:
        problems.append("the S/P/twin/D sets changed")
    if not cal["gate"]["passed"]:
        problems.append("the gate no longer passes")
    return problems


def prompt_fingerprint(constants: Constants) -> str:
    """The mode-independent system-prompt fingerprint for the first task and regime (frozen and verified)."""
    cfg = RunConfig(TASKS[0], next(iter(constants.regimes.values())), "developmental", compute=constants.compute,
                    coord=constants.coord)
    return Run(cfg, None, InformationEnvironment(load_world(), constants.sources)).prompt_fingerprint()


def frozen_constants() -> tuple[dict, Constants, str]:
    frozen = load_frozen()
    if frozen is None:
        raise SystemExit("data/frozen.json not found: run `python -m devagents freeze` first (SPEC §7.4).")
    return frozen, Constants.from_json(frozen["constants"]), sha256_file(FROZEN_PATH)


def modes_for(kind: str) -> list[str]:
    return ["single", "central"] if kind == "pilot" else list(MODES)


def pilot_configs(constants: Constants, repeats: int) -> list[RunConfig]:
    return plan(PILOT_TASKS, constants, modes_for("pilot"), repeats)
