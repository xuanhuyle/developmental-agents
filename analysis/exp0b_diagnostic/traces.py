"""Experiment 0b diagnostic, part 2: read the live logs. Offline; no API call; changes no file outside --out.

    python analysis/exp0b_diagnostic/traces.py results/exp0b/main --pilot results/pilot --out results/exp0b_diagnostic

It writes traces.md (tables) and traces.json (the same numbers) and prints the markdown. It reports:

1. a recomputation of the Experiment 0b report from the event logs: with the repository's own evaluator
   (`build_report`, 10,000 resamples) and with independent tallies (completion, spawn and parallel rates, agents,
   fitness by class, regime and mode, the manipulation check), compared with the report's summary.json;
2. every P-cell run (cells read from data/exp0b/frozen.json) in every mode: the root's actions, SPAWN requests and
   their children, allocations and lifetimes (requested and applied), WAIT and MESSAGE use, invalid actions,
   termination, cost, time and fitness;
3. a census of organizations in every cell: children per central SPAWN, and SPAWN attempts by developmental and
   router;
4. the live main run's token statistics (r and reasoning tokens, measured as pilot_stats measures them), to rerun
   offline.py at live assumptions;
5. the pilot's central organizations (children per SPAWN) and single vs central fitness per pilot task and regime.

Privacy: it prints structure only (action types, counts, dollars, seconds, error strings, the number of known document
ids named in each child objective) plus each root's *first* rationale, truncated. The first rationale is written before
any document is read. No document text, answer, SQL, message content or key is printed. --no-rationales omits them.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from devagents.config import EXPERIMENTS, Constants, load_frozen, sha256_file  # noqa: E402
from devagents.environment.world import load_world  # noqa: E402
from devagents.evals.metrics import Weights, fitness, metrics_from_events  # noqa: E402
from devagents.runtime.events import read_events  # noqa: E402
from devagents.runtime.resources import to_usd  # noqa: E402

DOC_IDS = sorted(load_world().docs)
MODES = ("single", "central", "router", "developmental")
KEYWORDS = ("spawn", "agent", "child", "parallel", "concurren", "delegat", "split", "divide", "time", "second", "latency")


def load_suite(results_dir: Path) -> tuple[dict, dict[str, list[dict]]]:
    manifest = json.loads((results_dir / "manifest.json").read_text())
    logs = {}
    for run_id in manifest["planned_runs"]:
        path = results_dir / "events" / f"{run_id}.jsonl"
        if path.exists():
            logs[run_id] = read_events(path)
    return manifest, logs


def complete(events: list[dict]) -> bool:
    return any(e["type"] == "RUN_COMPLETED" for e in events)


def weights_of(events: list[dict]) -> Weights:
    r = next(e for e in events if e["type"] == "RUN_STARTED")["audit"]["regime"]
    return Weights(r["task_value"], r["value_of_time"], 0.0, r["failure_penalty"])


def doc_mentions(text: str) -> int:
    return sum(1 for d in DOC_IDS if d in (text or ""))


def trace(events: list[dict], rationales: bool) -> dict:
    """The organizational decisions of one run."""
    root_steps, spawns, invalid, waits, messages = [], [], [], 0, 0
    completed = {(e["agent"], e["step"]): e for e in events if e["type"] == "ACTION_COMPLETED"}
    spawned = [e for e in events if e["type"] == "AGENT_SPAWNED"]
    created = {e["agent"]: e for e in events if e["type"] == "AGENT_CREATED"}
    first_rationale = None
    for e in events:
        if e["type"] != "ACTION_STARTED":
            continue
        d = e.get("detail") if isinstance(e.get("detail"), dict) else {}
        done = completed.get((e["agent"], e["step"]), {})
        if e["action"] == "INVALID" or not done.get("ok", True):
            invalid.append({"agent": e["agent"], "step": e["step"], "action": e["action"], "error": done.get("error", "")})
        if e["action"] == "WAIT":
            waits += 1
        if e["action"] == "MESSAGE":
            messages += 1
        if e["agent"] != "A0":
            continue
        if first_rationale is None and rationales:
            first_rationale = (d.get("rationale") or "")[:200]
        label = e["action"]
        if e["action"] == "QUERY":
            reqs = d.get("requests") or []
            label += f"({sum(r.get('kind') == 'doc' for r in reqs)}d{sum(r.get('kind') == 'sql' for r in reqs)}s)"
        if e["action"] == "SPAWN":
            kids = d.get("children") or []
            label += f"({len(kids)})"
            mine = [s for s in spawned if s["agent"] == "A0" and abs(s["t"] - (e["t"] + e["llm_latency_s"] + e["action_latency_s"])) < 1e-6]
            spawns.append({
                "step": e["step"], "ok": done.get("ok", False), "error": done.get("error", ""),
                "children_requested": len(kids), "children_created": len(mine),
                "budget_requested_usd": [c.get("budget_usd") for c in kids],
                "lifetime_requested_s": [c.get("lifetime_s") for c in kids],
                "allocation_applied_usd": [to_usd(s["allocation"]) for s in mine],
                "lifetime_applied_s": [round(created[s["child"]]["deadline"] - s["t"], 1) for s in mine],
                "wait_for_children": d.get("wait_for_children"),
                "docs_named_per_objective": [doc_mentions(c.get("objective", "") + " " + c.get("context", "")) for c in kids],
                "objective_chars": [len(c.get("objective", "")) for c in kids]})
        root_steps.append(label)
    m = metrics_from_events(events)
    child_actions = Counter(e["action"] for e in events if e["type"] == "ACTION_STARTED" and e["agent"] != "A0")
    return {"root_actions": " > ".join(root_steps), "spawn_attempts": spawns, "invalid": invalid, "waits": waits,
            "messages": messages, "agents": m["agents"], "parallel": m["parallel"], "spawned": m["spawned"],
            "child_actions": dict(child_actions), "termination_reasons": m["termination_reasons"],
            "outcome": m["outcome"], "quality": m["quality"], "money_usd": m["money_usd"], "elapsed_s": m["elapsed_s"],
            "fitness": round(fitness(m, weights_of(events)), 4), "first_rationale": first_rationale,
            "rationale_keywords": dict(Counter(k for e in events if e["type"] == "ACTION_STARTED" and e["agent"] == "A0"
                                               for k in KEYWORDS
                                               if k in ((e.get("detail") or {}).get("rationale") or "").lower()))}


def token_stats(logs: dict[str, list[dict]]) -> dict:
    """r and reasoning tokens, as pilot_stats measures them, over every live LLM step of the suite."""
    ratios, reasoning = [], []
    for events in logs.values():
        for e in events:
            if e["type"] == "RESOURCE_CONSUMED" and e["kind"] == "llm" and e.get("est_in_tokens"):
                ratios.append(e["in_tokens"] / e["est_in_tokens"])
                reasoning.append(max(0, e["out_tokens"] - e.get("est_visible_out_tokens", 0)))
    return {"llm_calls": len(ratios), "input_scale": round(statistics.median(ratios), 4) if ratios else None,
            "reasoning_tokens": int(statistics.median(reasoning)) if reasoning else None}


def verify(results_dir: Path, manifest: dict, logs: dict, frozen: dict, frozen_path: Path) -> dict:
    from devagents.evals.experiment import verify_frozen
    from devagents.evals.report import build_report
    frozen_ok = manifest.get("frozen_sha") == sha256_file(frozen_path) and not verify_frozen(frozen)
    rep = build_report(results_dir, frozen, frozen_ok)  # the repository's evaluator, 10,000 resamples
    cells = frozen["calibration"]["cells"]
    runs = {rid: ev for rid, ev in logs.items() if complete(ev)}
    by_mode = Counter(rid.split("-")[2] for rid in manifest["planned_runs"])
    done_mode = Counter(rid.split("-")[2] for rid in runs)
    groups = defaultdict(list)
    for rid, ev in runs.items():
        m = metrics_from_events(ev)
        c = cells[f"{m['task_id']}|{m['regime']}"]
        groups[(c["task_class"], m["regime"], m["mode"])].append({**m, "fitness": fitness(m, weights_of(ev)),
                                                                   "label": c["label"]})
    table = {f"{cls}|{reg}|{mode}": {"n": len(rs), "fitness": statistics.fmean(r["fitness"] for r in rs),
                                     "quality": statistics.fmean(r["quality"] for r in rs),
                                     "spawned": statistics.fmean(r["spawned"] for r in rs),
                                     "parallel": statistics.fmean(r["parallel"] for r in rs),
                                     "agents": statistics.fmean(r["agents"] for r in rs),
                                     "money_usd": statistics.fmean(r["money_usd"] for r in rs),
                                     "elapsed_s": statistics.fmean(r["elapsed_s"] for r in rs)}
             for (cls, reg, mode), rs in sorted(groups.items())}
    manip = {}
    for name, (cls, reg) in {"B_urgent": ("parallel", "urgent"), "B_relaxed": ("parallel", "relaxed"),
                             "A": ("solo", None)}.items():
        manip[name] = {mode: statistics.fmean(r["fitness"] for (c, rg, md), rs in groups.items() for r in rs
                                              if c == cls and (reg is None or rg == reg) and md == mode)
                       for mode in ("central", "single")}
    # Criteria 1-3 recomputed independently with SPEC section 8's estimand: the unweighted mean over (class, regime)
    # strata of the per-cell rate, developmental runs only.
    per_cell = defaultdict(list)
    for (cls, reg, mode), rs in groups.items():
        if mode == "developmental":
            for r in rs:
                per_cell[f"{r['task_id']}|{r['regime']}"].append(r)
    sets = {k: set(v) for k, v in frozen["calibration"]["gate"]["sets"].items()}

    def rate(keys, indicator):
        strata = defaultdict(list)
        for k in keys:
            if per_cell.get(k):
                strata[(cells[k]["task_class"], cells[k]["regime"])].append(
                    statistics.fmean(bool(r[indicator]) for r in per_cell[k]))
        return statistics.fmean(statistics.fmean(v) for v in strata.values()) if strata else None
    twin_u = {k for k in sets["twin"] if k.endswith("|urgent")}
    twin_r = {k for k in sets["twin"] if k.endswith("|relaxed")}
    independent = {"spawned_rate_S": rate(sets["S"], "spawned"), "parallel_rate_P": rate(sets["P"], "parallel"),
                   "3a_urgent": rate(sets["P_urgent"], "parallel") - rate(sets["S_urgent"], "spawned")
                   if sets["P_urgent"] and sets["S_urgent"] else None,
                   "3b_twin": rate(twin_u, "parallel") - rate(twin_r, "spawned") if twin_u else None,
                   "3c_dissociation": rate(sets["P_urgent"], "parallel") - rate(sets["D_urgent"], "spawned")}
    crit = rep["criteria"].get("criteria", {})
    evaluator = {"spawned_rate_S": crit.get("1_always_spawn", {}).get("spawned_rate_S"),
                 "parallel_rate_P": crit.get("2_never_spawn", {}).get("parallel_rate_P"),
                 "3a_urgent": crit.get("3a_within_regime", {}).get("contrasts", {}).get("urgent"),
                 "3b_twin": crit.get("3b_twin", {}).get("contrast"),
                 "3c_dissociation": crit.get("3c_dissociation", {}).get("contrast")}
    by_label = defaultdict(list)
    for (cls, reg, mode), rs in groups.items():
        for r in rs:
            by_label[(mode, r["label"])].append(r)
    label_rates = {f"{mode}|{lab}": {"spawned": statistics.fmean(r["spawned"] for r in rs),
                                     "parallel": statistics.fmean(r["parallel"] for r in rs), "n": len(rs)}
                   for (mode, lab), rs in sorted(by_label.items())}
    out = {"frozen_ok": frozen_ok, "planned": dict(by_mode), "completed": dict(done_mode),
           "completion": {m: done_mode[m] / by_mode[m] for m in by_mode}, "table": table, "manipulation": manip,
           "label_rates_pooled": label_rates, "criteria_statistics": {"evaluator": evaluator, "independent": independent,
                                                                       "agree": all(
               (evaluator[k] is None and independent[k] is None) or
               (evaluator[k] is not None and independent[k] is not None and abs(evaluator[k] - independent[k]) < 1e-9)
               for k in evaluator)},
           "report": {k: rep[k] for k in ("verdict", "n_runs", "exploratory")},
           "report_validity": rep["validity"], "report_fired": rep["criteria"].get("fired"),
           "report_criteria": rep["criteria"].get("criteria")}
    summary = results_dir / "summary.json"
    if summary.exists():
        s = json.loads(summary.read_text())
        v, sv = rep["validity"].get("v_detail", {}), s.get("validity", {}).get("v_detail", {})
        out["consistent_with_summary_json"] = {
            "verdict": s.get("verdict") == rep["verdict"], "n_runs": s.get("n_runs") == rep["n_runs"],
            "fired": s.get("criteria", {}).get("fired") == rep["criteria"].get("fired"),
            "manipulation_detail": all(abs((sv.get(g, {}).get(k) or 0) - (v.get(g, {}).get(k) or 0)) < 1e-9
                                       for g in v for k in ("central", "single")),
            "independent_manipulation": all(abs(manip[g][k] - (v.get(g, {}).get(k) or 0)) < 1e-9
                                            for g in manip for k in ("central", "single"))}
    return out


def census(logs: dict, cells: dict) -> dict:
    """Children per central SPAWN, and SPAWN attempts by developmental and router, in every cell."""
    central = Counter()
    attempts = defaultdict(Counter)
    for rid, ev in logs.items():
        if not complete(ev):
            continue
        task, regime, mode, _ = rid.split("-")
        cls = cells[f"{task}|{regime}"]["task_class"]
        t = trace(ev, rationales=False)
        if mode == "central":
            for s in t["spawn_attempts"][:1]:
                central[(cls, regime, s["children_requested"])] += 1
        if mode in ("developmental", "router"):
            key = (mode, cls, regime)
            attempts[key]["runs"] += 1
            attempts[key]["runs_with_spawn_attempt"] += bool(t["spawn_attempts"])
            attempts[key]["runs_with_valid_spawn"] += any(s["ok"] for s in t["spawn_attempts"])
            attempts[key]["runs_with_invalid_action"] += bool(t["invalid"])
    return {"central_children": {f"{c}|{r}|k={k}": n for (c, r, k), n in sorted(central.items())},
            "spawn_attempts": {"|".join(k): dict(v) for k, v in sorted(attempts.items())}}


def pilot(pilot_dir: Path) -> dict:
    manifest, logs = load_suite(pilot_dir)
    rows, fit = [], defaultdict(list)
    for rid, ev in sorted(logs.items()):
        if not complete(ev):
            continue
        task, regime, mode, rep = rid.split("-")
        t = trace(ev, rationales=False)
        fit[(task, regime, mode)].append(t["fitness"])
        if mode == "central":
            s = t["spawn_attempts"][0] if t["spawn_attempts"] else {}
            rows.append({"run": rid, "children": s.get("children_requested"), "created": s.get("children_created"),
                         "docs_named_per_objective": s.get("docs_named_per_objective"), "agents": t["agents"],
                         "parallel": t["parallel"], "fitness": t["fitness"], "root_actions": t["root_actions"]})
    comp = {f"{task}|{regime}": {mode: round(statistics.fmean(fit[(task, regime, mode)]), 4)
                                 for mode in ("single", "central") if fit[(task, regime, mode)]}
            for task, regime in sorted({(k[0], k[1]) for k in fit})}
    return {"central_runs": rows, "single_vs_central": comp,
            "central_ever_more_than_one_child": any((r["children"] or 0) > 1 for r in rows)}


def markdown(res: dict) -> str:
    L = ["# Experiment 0b diagnostic traces", ""]
    v = res["verify"]
    L += ["## 1. Recomputation", "", f"- frozen file verifies and matches the suite: {v['frozen_ok']}",
          f"- planned / completed per mode: {v['planned']} / {v['completed']}",
          f"- verdict (repository evaluator): {v['report']['verdict']}; fired: {v['report_fired']}",
          f"- validity: " + ", ".join(f"{k}={val}" for k, val in v["report_validity"].items() if not k.endswith("detail")),
          f"- manipulation check (independent): {json.dumps(v['manipulation'])}",
          f"- criteria statistics, evaluator: {json.dumps(v['criteria_statistics']['evaluator'])}",
          f"- criteria statistics, independent: {json.dumps(v['criteria_statistics']['independent'])} "
          f"(agree: {v['criteria_statistics']['agree']})",
          f"- consistency with summary.json: {v.get('consistent_with_summary_json', 'summary.json not found')}", "",
          "| class | regime | mode | n | fitness | quality | spawned | parallel | agents | money | time (s) |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in v["table"].items():
        cls, reg, mode = k.split("|")
        L.append(f"| {cls} | {reg} | {mode} | {r['n']} | {r['fitness']:.4f} | {r['quality']:.3f} | {r['spawned']:.2f} | "
                 f"{r['parallel']:.2f} | {r['agents']:.2f} | ${r['money_usd']:.4f} | {r['elapsed_s']:.1f} |")
    L += ["", "## 2. P-cell traces", "",
          "| run | root actions | SPAWN: requested/created children, docs named per child, allocation, lifetime | "
          "invalid | waits/msgs | agents | parallel | time (s) | money | fitness | first rationale |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for rid, t in res["p_cell_traces"].items():
        sp = "; ".join(f"{s['children_requested']}/{s['children_created']} kids, docs {s['docs_named_per_objective']}, "
                       f"${[round(x, 3) for x in s['allocation_applied_usd']]}, {s['lifetime_applied_s']}s"
                       + ("" if s["ok"] else f" [REJECTED: {s['error']}]") for s in t["spawn_attempts"]) or "-"
        inv = "; ".join(f"{i['agent']}#{i['step']} {i['error'][:60]}" for i in t["invalid"]) or "-"
        L.append(f"| {rid} | {t['root_actions']} | {sp} | {inv} | {t['waits']}/{t['messages']} | {t['agents']} | "
                 f"{t['parallel']} | {t['elapsed_s']:.0f} | ${t['money_usd']:.4f} | {t['fitness']:.3f} | "
                 f"{(t['first_rationale'] or '').replace('|', '/')} |")
    c = res["census"]
    L += ["", "## 3. Organization census (all cells)", "", f"- central children per first SPAWN: {c['central_children']}",
          f"- developmental/router SPAWN attempts: {json.dumps(c['spawn_attempts'])}", "",
          "## 4. Live token statistics (main run)", "", f"- {res['live_tokens']}", ""]
    if "pilot" in res:
        p = res["pilot"]
        L += ["## 5. Pilot central organizations", "",
              f"- central ever used more than one child: {p['central_ever_more_than_one_child']}",
              f"- single vs central mean fitness: {json.dumps(p['single_vs_central'])}", "",
              "| run | children | docs named per child | agents | parallel | fitness | root actions |", "|---|---|---|---|---|---|---|"]
        L += [f"| {r['run']} | {r['children']} | {r['docs_named_per_objective']} | {r['agents']} | {r['parallel']} | "
              f"{r['fitness']:.3f} | {r['root_actions']} |" for r in p["central_runs"]]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("main_dir", nargs="?", default="results/exp0b/main")
    p.add_argument("--pilot", default="results/pilot")
    p.add_argument("--out", default="results/exp0b_diagnostic")
    p.add_argument("--no-rationales", action="store_true")
    a = p.parse_args(argv)
    frozen_path = EXPERIMENTS["0b"].frozen
    frozen = load_frozen(frozen_path)
    cells = frozen["calibration"]["cells"]
    manifest, logs = load_suite(Path(a.main_dir))
    p_cells = sorted(k for k, c in cells.items() if c["label"] == "P")
    res = {"verify": verify(Path(a.main_dir), manifest, logs, frozen, frozen_path),
           "p_cell_traces": {rid: trace(ev, not a.no_rationales) for rid, ev in sorted(logs.items())
                             if complete(ev) and "|".join(rid.split("-")[:2]) in p_cells},
           "census": census(logs, cells), "live_tokens": token_stats(logs)}
    if Path(a.pilot).exists():
        res["pilot"] = pilot(Path(a.pilot))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "traces.json").write_text(json.dumps(res, indent=1, default=str))
    md = markdown(res)
    (out / "traces.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
