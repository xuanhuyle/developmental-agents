"""Reports: every number is recomputed from the event logs, then scored with the frozen weights (SPEC §8, §9).

Rescoring with other weights is allowed. It is stamped EXPLORATORY and never presented as the §8 verdict.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from devagents.config import Constants
from devagents.evals.analysis import N_BOOT, evaluate, secondary_router, validity
from devagents.evals.metrics import Weights, fitness, metrics_from_events
from devagents.runtime.events import read_events
from devagents.runtime.runtime import MODES


def load_runs(results_dir: Path, planned: set[str] | None = None) -> tuple[list[dict], list[dict], dict]:
    """(per-run metrics, RUN_STARTED events, infrastructure-error lines), all read from disk. Only runs in `planned`
    (the manifest's run ids) count; any other log in the directory is ignored."""
    results_dir = Path(results_dir)
    metrics, starts = [], []
    for path in sorted((results_dir / "events").glob("*.jsonl")):
        if planned is not None and path.stem not in planned:
            continue
        events = read_events(path)
        start = next((e for e in events if e["type"] == "RUN_STARTED"), None)
        if start is None or not any(e["type"] == "RUN_COMPLETED" for e in events):
            continue  # an attempt interrupted by an infrastructure error
        metrics.append(metrics_from_events(events))
        starts.append(start)
    errors = defaultdict(list)
    err_path = results_dir / "errors.jsonl"
    if err_path.exists():
        for line in err_path.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                errors[e["run_id"]].append(e)
    return metrics, starts, errors


def audit_parity(starts: list[dict], frozen_sha: str | None = None) -> tuple[bool, list[str]]:
    """Every (task, regime, repeat) block has identical audit records, prompt fingerprints and policy configurations
    across modes, and every run carries the manifest's frozen hash."""
    blocks = defaultdict(list)
    for s in starts:
        blocks[(s["task_id"], s["regime"], s["repeat"])].append(s)
    problems = []
    if frozen_sha is not None:
        problems += [f"{s['run_id']} ran under a different freeze" for s in starts if s["audit"].get("frozen_sha") != frozen_sha]
    for key, ss in blocks.items():
        if len({json.dumps(s["audit"], sort_keys=True) for s in ss}) > 1:
            problems.append(f"audit differs across modes in block {key}")
        if len({s["prompt_sha"] for s in ss}) > 1:
            problems.append(f"prompt fingerprint differs across modes in block {key}")
        if len({json.dumps(s.get("policy"), sort_keys=True) for s in ss}) > 1:
            problems.append(f"policy configuration differs across modes in block {key}")
    return not problems, problems


def to_records(metrics: list[dict], weights: dict[str, Weights], cells: dict) -> list[dict]:
    out = []
    for m in metrics:
        key = f"{m['task_id']}|{m['regime']}"
        f = fitness(m, weights[m["regime"]])
        out.append({**m, "fitness": f, "cost": m["quality"] - f, "subtype": cells.get(key, {}).get("subtype", ""),
                    "infra_error": False})
    return out


def pareto(rows: dict[str, dict]) -> list[str]:
    """Modes not dominated on (quality↑, money↓, time↓)."""
    def dominates(a, b):
        ge = a["quality"] >= b["quality"] and a["money_usd"] <= b["money_usd"] and a["elapsed_s"] <= b["elapsed_s"]
        gt = a["quality"] > b["quality"] or a["money_usd"] < b["money_usd"] or a["elapsed_s"] < b["elapsed_s"]
        return ge and gt
    return sorted(m for m, r in rows.items() if not any(dominates(o, r) for n, o in rows.items() if n != m))


def build_report(results_dir: Path, frozen: dict, frozen_ok: bool, weight_overrides: dict | None = None,
                 n_boot: int = N_BOOT) -> dict:
    results_dir = Path(results_dir)
    manifest = json.loads((results_dir / "manifest.json").read_text())
    constants = Constants.from_json(frozen["constants"])
    cells, sets = frozen["calibration"]["cells"], frozen["calibration"]["gate"]["sets"]
    regimes = dict(constants.regimes)
    for name, vot in (weight_overrides or {}).get("value_of_time", {}).items():
        regimes[name] = replace(regimes[name], value_of_time=vot)
    w_coord = (weight_overrides or {}).get("w_coord", 0.0)
    weights = {k: Weights(r.task_value, r.value_of_time, w_coord, r.failure_penalty) for k, r in regimes.items()}
    exploratory = bool(manifest.get("exploratory")) or bool(weight_overrides) or not frozen_ok or n_boot != N_BOOT

    metrics, starts, errors = load_runs(results_dir, set(manifest["planned_runs"]))
    records = to_records(metrics, weights, cells)
    audit_ok, audit_problems = audit_parity(starts, manifest.get("frozen_sha"))
    planned = defaultdict(int)
    for run_id in manifest["planned_runs"]:
        planned[run_id.split("-")[2]] += 1
    main_cells = {k: v for k, v in cells.items() if k.split("|")[0] in manifest["tasks"]}
    if main_cells:
        val = validity(records, main_cells, dict(planned), manifest["repeats"], audit_ok, frozen_ok)
        crit = evaluate(records, main_cells, sets, n_boot=n_boot)
        h2 = secondary_router(records, main_cells, sets, n_boot) if any(r["mode"] == "router" for r in records) else None
        verdict = "uninformative" if not val["valid"] else crit["verdict"]
    else:  # a pilot or smoke suite: its tasks have no calibrated labels, so §8 does not apply
        val, crit, h2 = {"valid": False}, {"criteria": {}, "verdict": "n/a", "fired": []}, None
        verdict, exploratory = "not applicable (no calibrated main-suite cells)", True

    groups = defaultdict(list)
    for r in records:
        groups[(r["task_class"], r["regime"], r["mode"])].append(r)
    table = []
    for (cls, reg, mode), rs in sorted(groups.items()):
        table.append({"class": cls, "regime": reg, "mode": mode, "n": len(rs),
                      **{k: statistics.fmean(float(r[k]) for r in rs) for k in
                         ("quality", "money_usd", "elapsed_s", "fitness", "cost", "spawned", "parallel", "agents",
                          "coordination_usd", "invalid_actions", "cap_hits")}})
    per_cell = defaultdict(dict)
    for r in records:
        per_cell[f"{r['task_id']}|{r['regime']}"].setdefault(r["mode"], []).append(r)
    frontier, agreement = {}, []
    for key, by_mode in sorted(per_cell.items()):
        means = {m: {k: statistics.fmean(float(x[k]) for x in rs) for k in ("quality", "money_usd", "elapsed_s")}
                 for m, rs in by_mode.items()}
        frontier[key] = pareto(means)
        lab = cells.get(key, {}).get("label")
        for r in by_mode.get("developmental", []):
            if lab in ("S", "P"):
                agreement.append((r["parallel"] if lab == "P" else not r["spawned"]))
    return {"results_dir": str(results_dir), "exploratory": exploratory, "verdict": verdict, "criteria": crit,
            "validity": val, "audit_problems": audit_problems, "h2_router": h2, "table": table, "frontier": frontier,
            "agreement_with_labels": statistics.fmean(agreement) if agreement else None,
            "n_runs": len(records), "infra_errors": {k: len(v) for k, v in errors.items()},
            "weights": {k: vars(w) for k, w in weights.items()}, "frozen_sha": manifest.get("frozen_sha"),
            "n_boot": n_boot,
            "provisional_freeze": frozen.get("provisional", False)}


def _f(x, fmt="{:+.3f}"):
    return "n/a" if x is None else fmt.format(x)


def format_markdown(rep: dict) -> str:
    L = []
    if rep["exploratory"]:
        L.append("> **EXPLORATORY.** This is not the pre-registered §8 verdict: the run was exploratory, the weights were "
                 "overridden, or the frozen configuration did not verify.\n")
    if rep["provisional_freeze"]:
        L.append("> The freeze is **provisional** (no pilot). Its token assumptions are defaults, not measurements.\n")
    L.append(f"# Experiment 0 report\n\nResults: `{rep['results_dir']}`. Frozen config sha256: `{rep['frozen_sha']}`. "
             f"Completed runs: {rep['n_runs']}. Bootstrap resamples: {rep['n_boot']}.\n")
    L.append(f"## Verdict: **{rep['verdict'].upper()}**\n")
    L.append("### Validity conditions (SPEC §8)\n")
    v = rep["validity"]
    for k in [k for k in ("i_frozen_gate", "ii_single_accuracy", "iii_audit_parity", "iv_completion",
                          "v_manipulation_check", "vi_single_caps") if k in v]:
        detail = v.get(k.split("_")[0] + "_detail")
        L.append(f"- {k}: {'ok' if v[k] else '**FAILED**'}" + (f" — {json.dumps(detail, default=str)}" if detail else ""))
    L.append("\n### Falsification criteria (SPEC §8; FIRES means that criterion alone is enough to reject H)\n")
    for k, c in rep["criteria"]["criteria"].items():
        nums = {kk: vv for kk, vv in c.items() if kk != "fires"}
        L.append(f"- **{k}**: {'FIRES' if c['fires'] else 'does not fire'} — {json.dumps(nums, default=lambda x: round(x, 4) if isinstance(x, float) else str(x))}")
    if rep["h2_router"]:
        L.append("\n### H2 (secondary, does not affect the verdict): developmental − router\n")
        for scope, block in rep["h2_router"].items():
            for m, c in block.items():
                if c["theta"] is None:
                    L.append(f"- {scope} cells, {m}: no cells" + (" (the freeze has no I cells)" if scope == "I" else ""))
                else:
                    L.append(f"- {scope} cells, {m}: θ={_f(c['theta'])} 95% CI [{_f(c['lo'])}, {_f(c['hi'])}]")
    L.append(f"\nAgreement of developmental organizations with calibrated labels: {_f(rep['agreement_with_labels'], '{:.2f}')}\n")
    L.append("## Means per (class, regime, mode)\n")
    L.append("| class | regime | mode | n | quality | money $ | time s | fitness | spawned | parallel | agents | coord $ | invalid | caps |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rep["table"]:
        L.append(f"| {r['class']} | {r['regime']} | {r['mode']} | {r['n']} | {r['quality']:.2f} | {r['money_usd']:.4f} | "
                 f"{r['elapsed_s']:.0f} | {r['fitness']:+.3f} | {r['spawned']:.2f} | {r['parallel']:.2f} | {r['agents']:.1f} | "
                 f"{r['coordination_usd']:.4f} | {r['invalid_actions']:.2f} | {r['cap_hits']:.2f} |")
    L.append("\n## Pareto frontier per cell (quality↑, money↓, time↓)\n")
    for key, modes in rep["frontier"].items():
        L.append(f"- {key}: {', '.join(modes)}")
    if rep["infra_errors"]:
        L.append(f"\nInfrastructure errors (run id → failed attempts): {json.dumps(rep['infra_errors'])}")
    return "\n".join(L) + "\n"
