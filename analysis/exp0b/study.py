"""Experiment 0b proposal: offline calibration study. LLM-free: no API call, no live policy.

It reproduces Experiment 0's failed post-pilot calibration from the pilot statistics the user reported, decomposes the
gate (d) and (f) failures, and evaluates candidate environment changes with the unchanged pre-registered freeze
procedure (calibration grid, gate, mechanical repair, criteria check; SPEC §7). Candidate constants exist only in
memory: nothing here changes the runtime, prompts, tasks, data/frozen.json or SPEC.md.

    python analysis/exp0b/study.py                 # everything -> results/exp0b_analysis/ (about 15 minutes on 4 cores)
    python analysis/exp0b/study.py --only failure  # steps 1-2 only (seconds)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from devagents.agents.policies import ScriptedPolicy  # noqa: E402
from devagents.config import Constants, default_constants, load_frozen  # noqa: E402
from devagents.environment.sources import SQL_SOURCE, InformationEnvironment  # noqa: E402
from devagents.environment.tasks import PILOT_TASKS, TASKS, TASKS_BY_ID  # noqa: E402
from devagents.environment.world import load_world  # noqa: E402
from devagents.evals import calibrate as cal_mod  # noqa: E402
from devagents.evals import analysis, experiment  # noqa: E402
from devagents.evals.calibrate import DELTA, Assumptions, label, measure, oracle_script, organizations  # noqa: E402
from devagents.evals.metrics import metrics_from_events  # noqa: E402
from devagents.runtime import runtime as rt  # noqa: E402
from devagents.runtime.resources import to_usd, usd  # noqa: E402

OUT = ROOT / "results" / "exp0b_analysis"

# The live pilot's statistics exactly as reported (pilot_stats(results/pilot)); the logs are not in the repository.
# Every value freeze() reads from them is already rounded or clamped, so these reproduce freeze --pilot exactly:
# input_scale and reasoning_tokens are the rounded values freeze uses; min_step_tokens = max(256, 203) = 256;
# deadline = max(1500, 2 x 344.0196) = 1500; cost CV = max(0.25, 0.008) = 0.25; accuracy is 1.0 in every class.
PILOT = {"runs": 24, "llm_calls": 80, "input_scale": 2.0052, "reasoning_tokens": 36, "p90_output_tokens": 203,
         "single_p95_elapsed_s": 344.0196, "single_accuracy": {"solo": 1.0, "parallel": 1.0, "cross": 1.0},
         "cost_cv": 0.008}
BASE = Assumptions(input_scale=PILOT["input_scale"], reasoning_tokens=PILOT["reasoning_tokens"])
PRE_PILOT = Assumptions()  # r = 1, 150 reasoning tokens: what Experiment 0 was calibrated against before the pilot
# Median over all 256 base-point oracle organizations of money(pilot assumptions) / money(pre-pilot assumptions), at
# Experiment 0's constants; recomputed and checked by money_multiplier().
MONEY_MULTIPLIER = 1.392


# --------------------------------------------------------------------------- candidate environments

@dataclass(frozen=True)
class Candidate:
    name: str
    family: str
    budget: float = 1.0  # B, $ per run (both regimes)
    value: float = 0.5  # V, $ per correct answer (both regimes)
    share: float = 0.5  # fixed allocation share of `central` and the calibration oracle (SPEC §6)
    k: int = 8  # K = max_concurrency - 1
    vot_scale: float = 1.0  # multiplies both regimes' value of time (uniform currency rescaling only)


def candidate_constants(c: Candidate) -> Constants:
    """Code-default constants with the candidate's changes, before freeze's pilot adjustments and repair."""
    base = default_constants()
    regimes = {k: replace(r, budget_usd=c.budget, task_value=c.value, value_of_time=round(r.value_of_time * c.vot_scale, 10))
               for k, r in base.regimes.items()}
    return replace(base, regimes=regimes, compute=replace(base.compute, max_concurrency=c.k + 1))


def pilot_adjusted(constants: Constants) -> Constants:
    """What freeze() does with the pilot before calibrating (min_step_tokens and deadline; SPEC §7.4)."""
    compute = replace(constants.compute, min_step_tokens=max(constants.compute.min_step_tokens, PILOT["p90_output_tokens"]))
    regimes = {k: replace(v, deadline_s=max(v.deadline_s, 2 * PILOT["single_p95_elapsed_s"]))
               for k, v in constants.regimes.items()}
    return replace(constants, compute=compute, regimes=regimes)


@contextlib.contextmanager
def sorted_bootstrap():
    """analysis.contrast_ci iterates a *set* of cell keys, so the bootstrap's draws depend on PYTHONHASHSEED and the
    criteria check's rates (and R) vary between processes. This emulates the one-line fix proposed as amendment 0b-0
    (iterate the cells in sorted order), so every rate reported here is reproducible."""
    original = analysis.contrast_ci

    def contrast_ci(runs, cells, *args, **kwargs):
        return original(runs, sorted(cells), *args, **kwargs)

    analysis.contrast_ci = contrast_ci
    try:
        yield
    finally:
        analysis.contrast_ci = original


@contextlib.contextmanager
def allocation_share(share: float):
    """The calibration oracle builds its RunConfig in calibrate.run_org; give it the candidate's fixed share."""
    original = cal_mod.RunConfig

    def config(*args, **kwargs):
        kwargs.setdefault("central_budget_share", share)
        return original(*args, **kwargs)

    cal_mod.RunConfig = config
    try:
        yield
    finally:
        cal_mod.RunConfig = original


# --------------------------------------------------------------------------- instrumented oracle runs

class Probe(ScriptedPolicy):
    """The oracle's policy, recording at every START the reserve the runtime applied."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.records = []

    def decide(self, agent, allowed, max_tokens, run):
        c = run.cfg
        in_upper = run._input_upper_bound(agent)  # pure: the value _on_start just used
        required = (in_upper * c.compute.price_in + c.coord.message_fee
                    + c.compute.min_step_tokens * (c.compute.price_out + c.coord.message_per_token))
        self.records.append({"agent": agent.id, "step": agent.steps, "spent": run.ledger.spent[agent.id],
                             "balance": run.ledger.balance[agent.id], "in_upper": in_upper, "required": required})
        return super().decide(agent, allowed, max_tokens, run)


def run_oracle(task, regime, org, asm, info, constants, share=0.5):
    """One oracle organization, exactly as calibrate.run_org runs it, plus instrumentation."""
    script = oracle_script(task, task.routes[org.route], org, asm.extra_work_steps)
    policy = Probe(script, reasoning_tokens=asm.reasoning_tokens, input_scale=asm.input_scale)
    cfg = rt.RunConfig(task, regime, "developmental", compute=constants.compute, coord=constants.coord,
                       fixed_rule_spawns=True, central_budget_share=share)
    run = rt.Run(cfg, policy, info)
    allocations = []
    original = rt.fixed_allocation

    def spy(balance, fees, k, remaining, budget_share, lifetime_share):
        out = original(balance, fees, k, remaining, budget_share, lifetime_share)
        allocations.append({"balance": balance, "fees": fees, "k": k, "share": budget_share, "per_child": out[0],
                            "lifetime_s": out[1] / rt.US})
        return out

    rt.fixed_allocation = spy
    try:
        run.execute()
    finally:
        rt.fixed_allocation = original
    return run, policy.records, allocations


def clean(m: dict) -> bool:
    return (not m["invalid_actions"] and not m["cap_hits"] and m["quality"] == 1.0 and m["outcome"] == "answered"
            and "budget_exhausted" not in m["termination_reasons"])


def critical_path(events: list[dict]) -> dict:
    """Attribute the run's elapsed time to the actions on its critical path. The parts sum exactly to elapsed."""
    tol = 1e-5
    end = next(e for e in events if e["type"] == "RUN_COMPLETED")["t"]
    starts, queried, created, sent = defaultdict(list), defaultdict(list), {}, []
    for e in events:
        if e["type"] == "ACTION_STARTED":
            starts[e["agent"]].append(e)
        elif e["type"] == "INFORMATION_QUERIED":
            queried[(e["agent"], round(e["t"], 6))].append(e)
        elif e["type"] == "AGENT_CREATED":
            created[e["agent"]] = (e["t"], e["parent"])
        elif e["type"] == "MESSAGE_SENT":
            sent.append(e)
    parts = defaultdict(float)
    agent, t = rt.ROOT, end
    while t > tol:
        done = [s for s in starts[agent] if abs(s["t"] + s["llm_latency_s"] + s["action_latency_s"] - t) < tol]
        if done:
            s = done[-1]
            parts["llm_latency"] += s["llm_latency_s"]
            if s["action"] == "QUERY" and s["action_latency_s"]:
                for q in queried[(agent, round(t, 6))]:
                    parts["sql_latency" if q["source"] == SQL_SOURCE else "doc_latency"] += q["latency_s"]
            elif s["action"] == "SPAWN":
                parts["spawn_latency"] += s["action_latency_s"]
            else:
                parts["other_latency"] += s["action_latency_s"]
            t = s["t"]
            continue
        woke = [m for m in sent if m["to"] == agent and abs(m["deliver_at"] - t) < tol]
        if woke:
            m = woke[-1]
            parts["message_latency"] += m["deliver_at"] - m["t"]
            agent, t = m["agent"], m["t"]
            continue
        if agent in created and created[agent][1] is not None and abs(created[agent][0] - t) < tol:
            agent = created[agent][1]
            continue
        before = [s["t"] + s["llm_latency_s"] + s["action_latency_s"] for s in starts[agent]
                  if s["t"] + s["llm_latency_s"] + s["action_latency_s"] < t - tol]
        prev = max(before, default=0.0)
        parts["idle"] += t - prev
        t = prev
    total = sum(parts.values())
    assert abs(total - end) < 1e-3, (total, end)
    return dict(parts)


# --------------------------------------------------------------------------- step 1-2: the failed calibration

def gate_kinds(failures: list[str]) -> dict[str, list[str]]:
    """cell key -> gate conditions it violates, parsed from the gate's failure strings."""
    out = defaultdict(set)
    for f in failures:
        kind = re.match(r"\((\w)\)", f).group(1)
        m = re.search(r"(T\d\d)/(relaxed|urgent)", f)
        out[f"{m.group(1)}|{m.group(2)}" if m else "(sets)"].add(kind + (" solo<0.3" if "solo fitness" in f else
                                                                        " best<0.5" if "best fitness" in f else ""))
    return {k: sorted(v) for k, v in out.items()}


def fitness_parts(m: dict, events: list[dict], regime) -> dict:
    """1 - fitness as money and time terms (fractions of V), with the time term split along the critical path."""
    V, vot = regime.task_value, regime.value_of_time
    cp = critical_path(events)
    return {
        "money_llm": m["llm_usd"] / V, "money_query": m["query_usd"] / V, "money_coord": m["coordination_usd"] / V,
        "time_llm": vot * cp.get("llm_latency", 0) / V, "time_doc": vot * cp.get("doc_latency", 0) / V,
        "time_sql": vot * cp.get("sql_latency", 0) / V,
        "time_coord": vot * (cp.get("spawn_latency", 0) + cp.get("message_latency", 0)) / V,
        "time_other": vot * (cp.get("other_latency", 0) + cp.get("idle", 0)) / V,
        "money_usd": m["money_usd"], "elapsed_s": m["elapsed_s"], "agents": m["agents"], "llm_calls": m["llm_calls"],
        "critical_path_s": cp,
    }


def run_with_allocation(task, regime, org, asm, info, constants, per_child: int, share: float = 0.5):
    """The oracle organization exactly as the fixed rule runs it (same lifetime, same budget, same briefs), except that
    each child receives `per_child` µ$."""
    original = rt.fixed_allocation

    def fixed(balance, fees, k, remaining, budget_share, lifetime_share):
        return per_child, original(balance, fees, k, remaining, budget_share, lifetime_share)[1]

    rt.fixed_allocation = fixed
    try:
        return run_oracle(task, regime, org, asm, info, constants, share=share)
    finally:
        rt.fixed_allocation = original


def min_child_allocation(task, regime, org, asm, info, constants) -> dict:
    """Smallest equal per-child allocation (µ$, exact) with which every child of `org` completes cleanly, by bisection,
    plus the children's actual spend when the allocation does not constrain them."""
    def ok(x):
        run, _, _ = run_with_allocation(task, regime, org, asm, info, constants, x)
        return clean(metrics_from_events(run.log.events))
    top = min(usd(0.2), (usd(regime.budget_usd) - usd(0.06)) // org.k)  # what the parent can always fund
    lo, hi = 0, top
    assert ok(hi), (task.id, regime.name, org.name)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
    run, records, _ = run_with_allocation(task, regime, org, asm, info, constants, top)
    spends = {aid: run.ledger.spent[aid] for aid in run.agents if aid != rt.ROOT}
    return {"min_allocation": hi, "child_spend_max": max(spends.values()), "child_spend_mean": statistics.fmean(spends.values())}


def failure_analysis() -> dict:
    """Steps 1 and 2: reproduce the unrepaired post-pilot calibration and decompose every failing cell."""
    constants = pilot_adjusted(default_constants())
    meas = measure(constants, BASE)
    lab = label(meas, constants)
    failing = gate_kinds(lab["gate"]["failures"])
    info = InformationEnvironment(load_world(), constants.sources)
    design = load_frozen()["calibration"]["cells"]  # the pre-pilot design: the provisional freeze (r = 1, doc 0.105)

    rows = []
    for key in sorted(k for k in failing if k != "(sets)"):
        cell = lab["cells"][key]
        task, regime = TASKS_BY_ID[cell["task"]], constants.regimes[cell["regime"]]
        orgs = {o.name: o for o in organizations(task, constants.compute.max_concurrency - 1)}
        row = {"cell": key, "task": cell["task"], "regime": cell["regime"], "class": cell["task_class"],
               "subtype": cell["subtype"], "label": cell["label"], "violations": failing[key],
               "min_margin": cell["min_margin"], "max_margin": cell["max_margin"],
               "pre_pilot_label": design[key]["label"]}
        for side in ("solo", "div"):
            org = orgs[cell[side]]
            run, _, _ = run_oracle(task, regime, org, BASE, info, constants)
            m = metrics_from_events(run.log.events)
            row[side] = {"org": org.name, "fitness": cell[f"{side}_fitness"],
                         "pre_pilot_fitness": design[key][f"{side}_fitness"], **fitness_parts(m, run.log.events, regime)}
            # The same organization at the same constants under the pre-pilot assumptions (r = 1, 150 reasoning
            # tokens): exactly what the pilot's measurements moved.
            pre_run, _, _ = run_oracle(task, regime, org, PRE_PILOT, info, constants)
            row[side]["pre_pilot_parts"] = fitness_parts(metrics_from_events(pre_run.log.events), pre_run.log.events, regime)
        rows.append(row)

    # Gate (f): the starved organizations, with the fixed-rule allocation and each child's need.
    starvation = []
    for f in lab["gate"]["failures"]:
        m = re.match(r"\(f\) (T\d\d)/(\w+)/(\S+) at", f)
        if not m:
            continue
        task, regime = TASKS_BY_ID[m.group(1)], constants.regimes[m.group(2)]
        org = next(o for o in organizations(task, constants.compute.max_concurrency - 1) if o.name == m.group(3))
        run, records, allocs = run_oracle(task, regime, org, BASE, info, constants)
        a = allocs[0]
        stops = [e for e in run.log.events if e["type"] == "AGENT_TERMINATED" and e["reason"] == "budget_exhausted"]
        need = min_child_allocation(task, regime, org, BASE, info, constants)
        per_child = []
        for aid in sorted((x for x in run.agents if x != rt.ROOT), key=lambda x: int(x.split(".")[-1])):
            recs = [r for r in records if r["agent"] == aid]
            starved = any(e["agent"] == aid for e in stops)
            # the START that failed is not in `records` (decide is never called); recompute its need from the log
            per_child.append({"child": aid, "starved": starved, "steps_taken": len(recs),
                              "spent": run.ledger.spent[aid]})
        root_first = next(r for r in records if r["agent"] == rt.ROOT)
        starvation.append({
            "cell": f"{task.id}|{regime.name}", "org": org.name, "children": a["k"],
            "B": to_usd(run.ledger.budget), "root_first_step_cost": run.ledger.budget - a["balance"] - 0,
            "parent_balance_before_spawn": a["balance"], "spawn_fees": a["fees"], "share": a["share"],
            "available_for_children": int(a["share"] * max(0, a["balance"] - a["fees"])),
            "allocation_per_child": a["per_child"], "min_viable_allocation": need["min_allocation"],
            "child_spend_unconstrained_max": need["child_spend_max"],
            "reserve_component": need["min_allocation"] - need["child_spend_max"],
            "shortfall_per_child": need["min_allocation"] - a["per_child"],
            "starved_children": sum(c["starved"] for c in per_child), "per_child": per_child,
            "min_step_output_reserve": constants.compute.min_step_tokens * (constants.compute.price_out + constants.coord.message_per_token),
            "root_first_step": root_first,
            # What single change makes the fixed rule cover the need (holding everything else at Experiment 0 values)?
            "share_needed_at_B": need["min_allocation"] * a["k"] / max(1, a["balance"] - a["fees"]),
            "k_max_affordable_at_share": int(a["share"] * (a["balance"] - a["fees"]) // need["min_allocation"]),
        })
    return {"gate": lab["gate"], "failing": failing, "rows": rows, "starvation": starvation,
            "persistence": persistence()}


def persistence() -> dict:
    """For each cell, in how many of the 343 pre-registered mechanical-repair candidates it violates the gate."""
    constants0 = pilot_adjusted(default_constants())
    counts, kinds, n = defaultdict(int), defaultdict(int), 0
    for doc in range(7):
        c_doc = replace(constants0, sources=replace(constants0.sources, doc_per_token_s=round(
            constants0.sources.doc_per_token_s + 0.005 * doc, 6)))
        meas = measure(c_doc, BASE)
        for u in range(7):
            for r in range(7):
                c = c_doc.with_value_of_time("urgent", round(c_doc.regimes["urgent"].value_of_time * 1.25 ** u, 8))
                c = c.with_value_of_time("relaxed", round(c.regimes["relaxed"].value_of_time * 0.8 ** r, 8))
                failing = gate_kinds(label(meas, c)["gate"]["failures"])
                n += 1
                for cell, ks in failing.items():
                    for k in ks:
                        counts[f"{cell} {k}"] += 1
                kinds[" ".join(sorted({k[0] for ks in failing.values() for k in ks}))] += 1
    return {"candidates": n, "by_cell": dict(sorted(counts.items())), "kind_combinations": dict(kinds)}


# --------------------------------------------------------------------------- step 3-5: candidates

def candidates() -> list[Candidate]:
    cs = [Candidate("E0 (as pre-registered)", "baseline")]
    cs += [Candidate(f"B={b:g}", "1 budget", budget=b) for b in (1.25, 1.5, 2.0, 2.5, 3.0)]
    cs += [Candidate(f"V={v:g}", "2 value", value=v) for v in (0.625, 0.75, 1.0, 1.25, 1.5)]
    cs += [Candidate(f"B,V x{s:g}", "3 joint", budget=s, value=0.5 * s) for s in (1.25, 1.5, 1.75, 2.0, 2.25, 2.5)]
    cs += [Candidate(f"B,V,VoT x{s:g}", "3' currency", budget=s, value=0.5 * s, vot_scale=s) for s in (1.5, 2.0, 2.5)]
    cs += [Candidate(f"share={a:g}", "4 share", share=a) for a in (0.6, 0.7, 0.8)]
    cs += [Candidate(f"K={k}", "5 K", k=k) for k in (7, 6, 4)]
    for s in (1.5, 2.0):
        cs += [Candidate(f"B,V x{s:g} + share={a:g}", "D joint+share", budget=s, value=0.5 * s, share=a) for a in (0.6, 0.7, 0.8)]
        cs += [Candidate(f"B,V x{s:g} + K={k}", "E joint+K", budget=s, value=0.5 * s, k=k) for k in (7, 6, 4)]
    # The measured money multiplier: the pilot's assumptions multiply each organization's money cost by a median of
    # 1.392 relative to the pre-pilot assumptions (see money_multiplier()). Options A-E at that one scale:
    m = MONEY_MULTIPLIER
    cs += [Candidate(f"A: B x{m:g}", "A at m", budget=m), Candidate(f"B: V x{m:g}", "B at m", value=0.5 * m),
           Candidate(f"C: B,V x{m:g}", "C at m", budget=m, value=0.5 * m),
           Candidate(f"C': B,V,VoT x{m:g}", "C' at m", budget=m, value=0.5 * m, vot_scale=m)]
    cs += [Candidate(f"D: B,V x{m:g} + share={a:g}", "D at m", budget=m, value=0.5 * m, share=a) for a in (0.6, 0.7)]
    cs += [Candidate(f"E: B,V x{m:g} + K={k}", "E at m", budget=m, value=0.5 * m, k=k) for k in (7, 6, 4)]
    cs += [Candidate(f"D': B,V,VoT x{m:g} + share={a:g}", "D' at m", budget=m, value=0.5 * m, vot_scale=m, share=a)
           for a in (0.6, 0.7)]
    cs += [Candidate(f"E': B,V,VoT x{m:g} + K={k}", "E' at m", budget=m, value=0.5 * m, vot_scale=m, k=k) for k in (7, 6, 4)]
    cs += [Candidate(f"B,V,VoT x{s:g}", "3' currency", budget=s, value=0.5 * s, vot_scale=s)
           for s in (1.25, 1.3, 1.35, 1.45, 1.6, 1.75)]
    # Minimal cross-mechanism combinations: V repairs (d), a different knob repairs (f).
    cs += [Candidate(f"V={v:g} + B={b:g}", "B x V", budget=b, value=v) for v in (0.75, 1.0) for b in (1.5, 2.0)
           if b != 2 * v]
    cs += [Candidate(f"V={v:g} + share={a:g}", "V+share", value=v, share=a) for v in (0.75, 1.0) for a in (0.7, 0.8)]
    cs += [Candidate(f"V={v:g} + K={k}", "V+K", value=v, k=k) for v in (0.75, 1.0) for k in (7, 6)]
    return cs


def evaluate(c: Candidate) -> dict:
    """The unchanged pre-registered freeze (SPEC §7.4) on a candidate environment, plus the unrepaired gate."""
    t0 = time.time()
    constants = candidate_constants(c)
    with allocation_share(c.share), sorted_bootstrap():
        adjusted = pilot_adjusted(constants)
        unrepaired = label(measure(adjusted, BASE), adjusted)
        saved = experiment.default_constants, experiment.pilot_stats
        experiment.default_constants = lambda compute="opus": constants
        experiment.pilot_stats = lambda _dir: dict(PILOT)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                res = experiment.freeze(Path("pilot-statistics-injected"), out=Path(tmp) / "frozen.json")
                frozen = json.loads((Path(tmp) / "frozen.json").read_text()) if res["ok"] else None
        finally:
            experiment.default_constants, experiment.pilot_stats = saved
    out = {"candidate": asdict(c), "seconds": round(time.time() - t0, 1),
           "unrepaired": summarize(unrepaired["cells"], unrepaired["gate"]), "freeze": res}
    if frozen:
        out["frozen"] = summarize(frozen["calibration"]["cells"], frozen["calibration"]["gate"])
        out["frozen"]["criteria_check"] = frozen["criteria_check"]
        out["frozen"]["constants"] = frozen["constants"]
        out["frozen"]["cells"] = frozen["calibration"]["cells"]
    return out


def summarize(cells: dict, gate: dict) -> dict:
    labels = [c["label"] for c in cells.values()]
    s = [c for c in cells.values() if c["label"] == "S"]
    p = [c for c in cells.values() if c["label"] == "P"]
    return {"gate_passed": gate["passed"], "gate_kinds": sorted({f[1] for f in gate["failures"]}),
            "n_failures": len(gate["failures"]), "S": labels.count("S"), "P": labels.count("P"),
            "ambiguous": labels.count("ambiguous"), **{f"|{k}|": len(v) for k, v in gate["sets"].items()},
            "min_S_margin": min((c["min_margin"] for c in s), default=None),
            "min_P_margin": min((-c["max_margin"] for c in p), default=None)}


def degeneracy(result: dict, asm: Assumptions = BASE) -> dict:
    """Step 5 checks on a frozen candidate (its repaired constants), at the base point."""
    c = Candidate(**result["candidate"])
    constants = Constants.from_json(result["frozen"]["constants"])
    cells = result["frozen"]["cells"]
    info = InformationEnvironment(load_world(), constants.sources)
    K = constants.compute.max_concurrency - 1
    out = {"K": K}
    # Division vs solo: how often each wins, and by how much.
    out["P_share"] = sum(x["label"] == "P" for x in cells.values()) / len(cells)
    out["S_share"] = sum(x["label"] == "S" for x in cells.values()) / len(cells)
    # Threshold placement: labels at other margins (diagnostic only; delta stays 0.03).
    for d in (0.015, 0.045, 0.06):
        out[f"labels_at_delta_{d}"] = {
            "S": sum(x["min_margin"] >= d for x in cells.values()), "P": sum(x["max_margin"] <= -d for x in cells.values())}
    out["S_or_P_within_2delta"] = sum(1 for x in cells.values() if (x["label"] == "S" and x["min_margin"] < 2 * DELTA)
                                      or (x["label"] == "P" and -x["max_margin"] < 2 * DELTA))
    # Resource efficiency relevance: fitness spread across feasible organizations, and cost share of the best one.
    spreads, cost_share = [], []
    for x in cells.values():
        f = [v["fitness"] for v in x["base"].values() if v["fitness"] != float("-inf")]
        spreads.append(max(f) - min(f))
        cost_share.append(1 - max(f))
    out["fitness_spread_median"] = statistics.median(spreads)
    out["fitness_spread_min"] = min(spreads)
    out["best_cost_fraction_of_V_median"] = statistics.median(cost_share)  # money and time
    out["best_cost_fraction_of_V_range"] = [min(cost_share), max(cost_share)]
    money_share = []
    for x in cells.values():
        best = max((v for v in x["base"].values() if v["fitness"] != float("-inf")), key=lambda v: v["fitness"])
        money_share.append(best["money_usd"] / constants.regimes[x["regime"]].task_value)
    out["best_money_fraction_of_V_median"] = statistics.median(money_share)
    out["best_money_fraction_of_V_range"] = [min(money_share), max(money_share)]
    # Topology: in P cells, which k wins and what choosing a wrong k costs.
    ks = []
    for x in cells.values():
        if x["label"] != "P":
            continue
        fan = {int(re.match(r"fanout(\d+)@", n).group(1)): v["fitness"] for n, v in x["base"].items()
               if n.startswith("fanout") and n.endswith(f"@r{x['div'].split('@r')[1]}")}
        best_k = max(fan, key=fan.get)
        ks.append({"cell": f"{x['task']}|{x['regime']}", "best": x["div"], "best_fanout_k": best_k,
                   "k_range": [min(fan), max(fan)],
                   "loss_k1": round(fan[best_k] - fan[min(fan)], 4), "loss_kmax": round(fan[best_k] - fan[max(fan)], 4)})
    out["P_cells_topology"] = ks
    # Money: how binding is the budget? Minimum viable per-child allocation vs what the budget allows.
    budget = {}
    with allocation_share(c.share):
        for x in cells.values():
            if x["regime"] != "urgent" or x["task_class"] == "solo":
                continue
            task, regime = TASKS_BY_ID[x["task"]], constants.regimes[x["regime"]]
            orgs = {o.name: o for o in organizations(task, K)}
            org = orgs[x["div"]]
            need = min_child_allocation(task, regime, org, asm, info, constants)
            run, records, allocs = run_oracle(task, regime, org, asm, info, constants, share=c.share)
            m = metrics_from_events(run.log.events)
            kmax = [o for o in orgs.values() if o.kind != "solo" and o.k == max(oo.k for oo in orgs.values() if oo.kind == o.kind)]
            budget[f"{x['task']}|{x['regime']}"] = {
                "div": org.name, "k": org.k, "B": regime.budget_usd, "div_money": m["money_usd"],
                "min_viable_child_allocation": to_usd(need["min_allocation"]),
                "fixed_rule_allocation": to_usd(allocs[0]["per_child"]) if allocs else None,
                "children_affordable_at_min_allocation": int((usd(regime.budget_usd) - (records[0]["required"] if records else 0))
                                                             // max(1, need["min_allocation"])),
                "child_lifetime_used_fraction": max(
                    (e["t"] - next(c2["t"] for c2 in run.log.events if c2["type"] == "AGENT_CREATED" and c2["agent"] == e["agent"]))
                    for e in run.log.events if e["type"] == "AGENT_TERMINATED" and e["agent"] != rt.ROOT) / (
                    0.6 * regime.deadline_s) if org.kind != "solo" else None,
            }
    out["budget"] = budget
    # Which organizations are infeasible at the base point (starved or invalid)?
    out["infeasible_orgs_at_base"] = sorted(f"{x['task']}|{x['regime']}|{n}" for x in cells.values()
                                            for n, v in x["base"].items() if v["fitness"] == float("-inf"))
    return out


def geometry(cells: dict, reference: dict) -> dict:
    """How closely a calibration reproduces the pre-pilot one (the environment Experiment 0 was designed as)."""
    keys = sorted(cells)
    same = sum(cells[k]["label"] == reference[k]["label"] for k in keys)
    d = {f: statistics.fmean(abs(cells[k][f] - reference[k][f]) for k in keys)
         for f in ("solo_fitness", "div_fitness", "min_margin", "max_margin")}
    gap = statistics.fmean(abs((cells[k]["solo_fitness"] - cells[k]["div_fitness"])
                               - (reference[k]["solo_fitness"] - reference[k]["div_fitness"])) for k in keys)
    return {"label_agreement": f"{same}/{len(keys)}", "mean_abs_diff": {**{k: round(v, 4) for k, v in d.items()},
                                                                      "solo_minus_div": round(gap, 4)}}


def money_multiplier() -> dict:
    """How much the pilot's measured token accounting changed each organization's money and time, relative to the
    pre-pilot assumptions, over all base-point oracle organizations at Experiment 0's constants."""
    c = pilot_adjusted(default_constants())
    pil, pre = measure(c, BASE, with_grid=False)["data"], measure(c, PRE_PILOT, with_grid=False)["data"]
    q = lambda xs: {"min": min(xs), "p10": statistics.quantiles(xs, n=10)[0], "median": statistics.median(xs),  # noqa: E731
                    "p90": statistics.quantiles(xs, n=10)[-1], "max": max(xs)}
    money = [pil[k]["money_usd"] / pre[k]["money_usd"] for k in pil]
    out = {"orgs": len(pil), "money_ratio": q(money), "elapsed_ratio": q([pil[k]["elapsed_s"] / pre[k]["elapsed_s"] for k in pil]),
           "solo_money_ratio": q([v for k, v in zip(pil, money) if k[2].startswith("solo")]),
           "division_money_ratio": q([v for k, v in zip(pil, money) if not k[2].startswith("solo")])}
    assert round(out["money_ratio"]["median"], 3) == MONEY_MULTIPLIER, out["money_ratio"]["median"]
    return out


def observation_sizes() -> dict:
    """Observation sizes for the reserve audit (proposal section 2): the largest single new observation (characters,
    after an agent's first step) the oracle meets in the main and pilot tasks, and a reference size: one QUERY of the
    ten largest distinct documents, followed by a status block listing K children, as the runtime renders them."""
    c = pilot_adjusted(default_constants())
    info = InformationEnvironment(load_world(), c.sources)
    K = c.compute.max_concurrency - 1

    class Sizes(ScriptedPolicy):
        def decide(self, agent, allowed, max_tokens, run):
            if agent.prev_in_tokens:
                self.sizes.append(agent.new_chars)
            return super().decide(agent, allowed, max_tokens, run)

    out = {}
    for name, tasks in (("main", TASKS), ("pilot", PILOT_TASKS)):
        best = (0, "")
        for t in tasks:
            for reg in c.regimes.values():
                for org in organizations(t, K):
                    pol = Sizes(oracle_script(t, t.routes[org.route], org, 0), reasoning_tokens=BASE.reasoning_tokens,
                                input_scale=BASE.input_scale)
                    pol.sizes = []
                    rt.Run(rt.RunConfig(t, reg, "developmental", compute=c.compute, coord=c.coord, fixed_rule_spawns=True),
                           pol, info).execute()
                    for n in pol.sizes:
                        best = max(best, (n, f"{t.id}/{reg.name}/{org.name}"))
        out[f"largest_oracle_observation_{name}"] = {"chars": best[0], "where": best[1]}
    docs = sorted((d for d in info.source_ids if d != SQL_SOURCE), key=lambda d: -len(info.query("doc", d).text))[:10]
    ten = {"rationale": "read", "action": "QUERY", "requests": [{"kind": "doc", "target": d} for d in docs]}
    spawn = {"rationale": "divide", "action": "SPAWN", "wait_for_children": False,
             "children": [{"objective": f"wait {i}", "context": "", "budget_usd": 0.03, "lifetime_s": 1400}
                          for i in range(K)]}
    wait = {"rationale": "wait", "action": "WAIT", "wait_for": "all", "max_wait_s": 1000}
    plan = {rt.ROOT: [spawn, ten, {"rationale": "done", "action": "TERMINATE", "answer": "x"}]}
    pol = Sizes(lambda a, run, allowed: (plan.get(a.id) or [wait])[min(a.steps, len(plan.get(a.id) or [wait]) - 1)],
                reasoning_tokens=BASE.reasoning_tokens, input_scale=BASE.input_scale)
    pol.sizes = []
    task = TASKS[0]
    rt.Run(rt.RunConfig(task, c.regimes["relaxed"], "developmental", compute=c.compute, coord=c.coord), pol, info).execute()
    out["ten_largest_documents_plus_status_block"] = {"chars": max(pol.sizes), "documents": len(docs),
                                                      "children_listed": K}
    return out


def reference_summary() -> dict:
    """The provisional pre-pilot freeze (data/frozen.json, r = 1): the geometry Experiment 0 was designed to have."""
    frozen = load_frozen()
    cells = frozen["calibration"]["cells"]
    out = summarize(cells, frozen["calibration"]["gate"])
    out["R_stored"] = frozen["R"]  # computed at accuracy 0.9 (no pilot) and an unsorted bootstrap
    with sorted_bootstrap():
        cc = analysis.criteria_check(cells, frozen["calibration"]["gate"]["sets"], {t.id: t.max_doc_route for t in TASKS},
                                     accuracy=dict(PILOT["single_accuracy"]), cost_cv=max(0.25, PILOT["cost_cv"]), n_sims=200)
    out["R"] = cc["R"]
    out["criteria_check"] = {"R": cc["R"], "table": {str(k): v for k, v in cc["table"].items()}}
    out["degeneracy"] = degeneracy({"candidate": asdict(Candidate("reference (pre-pilot)", "reference")),
                                    "frozen": {"constants": frozen["constants"], "cells": cells}}, PRE_PILOT)
    out["S_or_P_within_2delta"] = sum(1 for x in cells.values() if (x["label"] == "S" and x["min_margin"] < 2 * DELTA)
                                      or (x["label"] == "P" and -x["max_margin"] < 2 * DELTA))
    for d in (0.015, 0.045, 0.06):
        out[f"labels_at_delta_{d}"] = {"S": sum(x["min_margin"] >= d for x in cells.values()),
                                       "P": sum(x["max_margin"] <= -d for x in cells.values())}
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", choices=["failure", "candidates"])
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--resume", action="store_true", help="keep candidates already in candidates.json; evaluate the rest")
    a = p.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.only in (None, "failure"):
        t0 = time.time()
        fa = failure_analysis()
        fa["money_multiplier"] = money_multiplier()
        fa["observation_sizes"] = observation_sizes()
        (out / "failure.json").write_text(json.dumps(fa, indent=1, default=str))
        print(f"failure analysis -> {out / 'failure.json'} ({time.time() - t0:.0f}s)", flush=True)
    if a.only in (None, "candidates"):
        cs = candidates()
        t0 = time.time()
        done = {}
        if a.resume and (out / "candidates.json").exists():
            done = {r["candidate"]["name"]: r for r in json.loads((out / "candidates.json").read_text())}
        todo = [c for c in cs if c.name not in done]
        with Pool(a.workers) as pool:
            results = [done[c.name] for c in cs if c.name in done]
            for r in pool.imap(evaluate, todo):
                results.append(r)
                f = r.get("frozen")
                print(f"[{len(results)}/{len(cs)}] {r['candidate']['name']:<34} unrepaired gate "
                      f"{'PASS' if r['unrepaired']['gate_passed'] else 'fail ' + ''.join(r['unrepaired']['gate_kinds'])}"
                      f" | freeze {'R=%s steps=%s' % (r['freeze']['R'], r['freeze']['steps']) if f else 'none'}"
                      f" ({r['seconds']}s)", flush=True)
        reference = load_frozen()["calibration"]["cells"]  # the provisional, pre-pilot calibration (r = 1)
        for r in results:
            if r.get("frozen"):
                r["geometry_vs_pre_pilot"] = geometry(r["frozen"]["cells"], reference)
        with Pool(a.workers) as pool:
            viable = [r for r in results if r.get("frozen") and "degeneracy" not in r]
            for r, d in zip(viable, pool.map(degeneracy, viable)):
                r["degeneracy"] = d
        order = {c.name: i for i, c in enumerate(cs)}
        results.sort(key=lambda r: order[r["candidate"]["name"]])
        (out / "candidates.json").write_text(json.dumps(results, indent=1, default=str))
        (out / "reference.json").write_text(json.dumps(reference_summary(), indent=1, default=str))
        print(f"candidates -> {out / 'candidates.json'} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
