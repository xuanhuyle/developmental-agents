"""LLM-free calibration (SPEC §7.1–7.2): oracle organizations, perturbation-stable labels, and the validity gate.
Mechanical gate repair (§7.4) lives in `experiment.freeze`.

The oracle knows each task's solution routes and reasons perfectly: quality = 1 and the minimum
number of steps. It runs through the same runtime and the same `developmental` prompts as the
experiment. So its costs are exactly what the environment charges for each organization under
the stated token assumptions. The calibration measures the environment; it is not a competitor.

Organizations:
- `solo`: one agent queries the route's sources, with the SQL first when the docs depend on it.
- `fanout-k`: the root runs any SQL itself, then spawns k children over the route's docs. This is
  "divide after looking".
- `atstart-k`: on dependent routes, the root spawns k children immediately, over all candidate
  docs. Each child runs the SQL and reads only its qualifying docs. This is "divide before looking",
  the only division available to a one-shot `router` or `central`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from devagents.agents.policies import ScriptedPolicy
from devagents.config import Constants, default_constants
from devagents.environment.sources import InformationEnvironment
from devagents.environment.tasks import TASKS, Regime, Route, Task
from devagents.environment.world import load_world
from devagents.evals.metrics import metrics_from_events
from devagents.runtime.resources import estimate_tokens, to_usd
from devagents.runtime.runtime import Run, RunConfig, fixed_allocation, sec

DELTA = 0.03  # SPEC §7.2 label margin (fitness units)
MIN_BEST_FITNESS = 0.5  # gate (d)
MIN_SOLO_FITNESS = 0.3  # gate (d): answering alone always beats a guess


@dataclass(frozen=True)
class Assumptions:
    input_scale: float = 1.0  # r = API input tokens / estimator tokens
    reasoning_tokens: int = 150  # hidden reasoning tokens per step
    extra_work_steps: int = 0  # additional WORK steps per agent (imperfect, longer real runs)


def grid(base: Assumptions) -> list[Assumptions]:
    return [Assumptions(round(r * base.input_scale, 4), max(0, round(m * base.reasoning_tokens)), e)
            for r in (0.75, 1.0, 1.25) for m in (0.5, 1.0, 2.0) for e in (0, 1)]


@dataclass(frozen=True)
class Org:
    kind: str  # "solo" | "fanout" | "atstart"
    route: int
    k: int = 0

    @property
    def name(self) -> str:
        return f"solo@r{self.route}" if self.kind == "solo" else f"{self.kind}{self.k}@r{self.route}"


def spawns_first(org: Org, route: Route) -> bool:
    """True if the organization's first action is SPAWN, i.e. it is reachable by `router` and `central`."""
    return org.kind == "atstart" or (org.kind == "fanout" and not (route.sql and route.docs))


def organizations(task: Task, max_children: int) -> list[Org]:
    orgs = []
    for i, route in enumerate(task.routes):
        orgs.append(Org("solo", i))
        orgs.extend(Org("fanout", i, k) for k in range(1, min(max_children, max(len(route.docs), 1)) + 1))
        if route.docs_depend_on_sql:
            orgs.extend(Org("atstart", i, k) for k in range(1, min(max_children, len(route.candidates)) + 1))
    return orgs


def _work(i: int) -> dict:
    return {"rationale": "Double-check the facts gathered so far.", "action": "WORK",
            "notes": f"Check {i + 1}: the gathered values are consistent with the question."}


def _query(reqs: list[tuple[str, str]]) -> dict:
    return {"rationale": "Read the sources needed.", "action": "QUERY",
            "requests": [{"kind": k, "target": t} for k, t in reqs]}


def oracle_script(task: Task, route: Route, org: Org, extra_work: int):
    """Scripted policy for one organization. The plan is indexed by each agent's step count."""
    answer = {"rationale": "All needed facts are in hand.", "action": "TERMINATE", "answer": task.answer}
    sql = [("sql", s) for s in route.sql]
    root_plan: list = []
    assignments: list[list[dict]] = []  # per child: its QUERY actions
    if org.kind == "solo":
        if route.sql and route.docs and route.docs_depend_on_sql:
            root_plan += [_query(sql), _query([("doc", d) for d in route.docs])]
        else:
            root_plan += [_query(sql + [("doc", d) for d in route.docs])]
    elif org.kind == "fanout":
        if route.docs:
            if route.sql:
                root_plan.append(_query(sql))
            assignments = [[_query([("doc", d) for d in route.docs[i::org.k]])] for i in range(org.k)]
        else:  # a doc-free route: one child runs the SQL
            assignments = [[_query(sql)]]
        root_plan.append("SPAWN")
    else:  # atstart: each child runs the SQL, then reads only its qualifying candidates
        for i in range(org.k):
            mine = [d for d in route.candidates[i::org.k] if d in route.docs]
            assignments.append([_query(sql)] + ([_query([("doc", d) for d in mine])] if mine else []))
        root_plan.append("SPAWN")
    root_plan += [_work(i) for i in range(extra_work)] + [answer]
    objective = f"Find the facts needed for: {task.question} Read only the sources named in this objective: "

    def script(agent, run: Run, allowed):
        if agent.parent is None:
            step = root_plan[min(agent.steps, len(root_plan) - 1)]
            return _spawn(agent, run, assignments, objective) if step == "SPAWN" else step
        plan = assignments[int(agent.id.split(".")[-1]) - 1] + [_work(i) for i in range(extra_work)] + [
            {"rationale": "Report back.", "action": "TERMINATE",
             "answer": "Facts found: the requested value for each entity read, quoted from the source text."}]
        return plan[min(agent.steps, len(plan) - 1)]

    return script


def _spawn(agent, run: Run, assignments: list[list[dict]], objective: str) -> dict:
    coord, cfg = run.cfg.coord, run.cfg
    objectives = [objective + "; ".join(r["target"] for q in a for r in q["requests"]) for a in assignments]
    fees = sum(coord.spawn_fee + coord.transfer_per_token * estimate_tokens(o) for o in objectives)
    share, life = fixed_allocation(run.ledger.balance[agent.id], fees, len(assignments), agent.deadline - agent.clock,
                                   cfg.central_budget_share, cfg.central_lifetime_share)
    return {"rationale": "Split the work across agents.", "action": "SPAWN", "wait_for_children": True,
            "children": [{"objective": o, "context": "", "budget_usd": to_usd(share), "lifetime_s": sec(life)}
                         for o in objectives]}


def run_org(task: Task, regime: Regime, org: Org, asm: Assumptions, info: InformationEnvironment,
            constants: Constants) -> dict:
    policy = ScriptedPolicy(oracle_script(task, task.routes[org.route], org, asm.extra_work_steps),
                            reasoning_tokens=asm.reasoning_tokens, input_scale=asm.input_scale)
    cfg = RunConfig(task, regime, "developmental", compute=constants.compute, coord=constants.coord)
    run = Run(cfg, policy, info)
    run.execute()
    return metrics_from_events(run.log.events)


# --------------------------------------------------------------------------- measure, then label

def measure(constants: Constants, base: Assumptions, tasks: list[Task] = TASKS, with_grid: bool = True) -> dict:
    """Simulate every organization at every grid point in every regime. Money and time do not depend on the fitness
    weights, so labelling can be redone with other weights without re-simulating."""
    info = InformationEnvironment(load_world(), constants.sources)
    k_max = constants.compute.max_concurrency - 1
    points = grid(base) if with_grid else [base]
    data = {}
    for task in tasks:
        for regime in constants.regimes.values():
            for i, asm in enumerate(points):
                for org in organizations(task, k_max):
                    m = run_org(task, regime, org, asm, info, constants)
                    data[(task.id, regime.name, org.name, i)] = {
                        k: m[k] for k in ("money_usd", "elapsed_s", "quality", "outcome", "invalid_actions", "cap_hits",
                                          "parallel", "agents", "llm_calls", "termination_reasons")}
    return {"points": [asdict(p) for p in points], "base_index": points.index(base) if base in points else 0,
            "data": data, "k_max": k_max}


def _fitness(m: dict, regime: Regime) -> float:
    failed = m["outcome"] != "answered"
    elapsed = regime.deadline_s if failed else m["elapsed_s"]
    return (m["quality"] - m["money_usd"] / regime.task_value - regime.value_of_time * elapsed / regime.task_value
            - regime.failure_penalty * failed)


def label(meas: dict, constants: Constants, tasks: list[Task] = TASKS) -> dict:
    """Label every cell and evaluate the gate, using `constants.regimes` as the fitness weights."""
    cells, problems = {}, []
    n_points, base_i = len(meas["points"]), meas["base_index"]
    for task in tasks:
        orgs = organizations(task, meas["k_max"])
        solo_n = [o.name for o in orgs if o.kind == "solo"]
        div_n = [o.name for o in orgs if o.kind != "solo"]
        first_n = [o.name for o in orgs if spawns_first(o, task.routes[o.route])]
        for regime in constants.regimes.values():
            margins, incr = [], []
            for i in range(n_points):
                res = {o.name: meas["data"][(task.id, regime.name, o.name, i)] for o in orgs}
                for n, m in res.items():
                    if m["invalid_actions"] or m["cap_hits"] or m["quality"] != 1.0 or m["outcome"] != "answered":
                        problems.append(f"(f) {task.id}/{regime.name}/{n} at {meas['points'][i]}: "
                                        f"invalid={m['invalid_actions']} caps={m['cap_hits']} outcome={m['outcome']} "
                                        f"reasons={m['termination_reasons']}")
                f = {n: _fitness(m, regime) for n, m in res.items()}
                s, d = max(f[n] for n in solo_n), max(f[n] for n in div_n)
                margins.append(s - d)
                incr.append(max(s, d) - max(s, max(f[n] for n in first_n)))
                if i == base_i:
                    base_f, base_res = f, res
            s = max(solo_n, key=base_f.get)
            d = max(div_n, key=base_f.get)
            r = max(first_n, key=base_f.get)
            lab = "S" if min(margins) >= DELTA else "P" if max(margins) <= -DELTA else "ambiguous"
            cells[f"{task.id}|{regime.name}"] = {
                "task": task.id, "task_class": task.task_class, "subtype": task.subtype, "regime": regime.name,
                "label": lab, "incremental": min(incr) >= DELTA and lab == "P",
                "min_margin": round(min(margins), 4), "max_margin": round(max(margins), 4),
                "min_incremental_gain": round(min(incr), 4),
                "solo": s, "div": d, "router_div": r,
                "solo_fitness": round(base_f[s], 6), "div_fitness": round(base_f[d], 6),
                "router_div_fitness": round(base_f[r], 6),
                "div_parallel": base_res[d]["parallel"], "router_div_parallel": base_res[r]["parallel"],
                "base": {n: {"fitness": round(base_f[n], 6), "money_usd": m["money_usd"], "elapsed_s": m["elapsed_s"],
                             "agents": m["agents"], "llm_calls": m["llm_calls"]} for n, m in base_res.items()},
            }
    return {"delta": DELTA, "cells": cells, "gate": gate(cells, problems)}


def calibrate(constants: Constants | None = None, base: Assumptions = Assumptions(), with_grid: bool = True,
              tasks: list[Task] = TASKS) -> dict:
    constants = constants or default_constants()
    cal = label(measure(constants, base, tasks, with_grid), constants, tasks)
    cal["assumptions"] = asdict(base)
    cal["constants"] = constants.to_json()
    return cal


def gate(cells: dict, problems: list[str]) -> dict:
    fails = list(problems)
    for c in cells.values():
        where = f"{c['task']}/{c['regime']}"
        if c["task_class"] == "solo" and c["label"] != "S":
            fails.append(f"(a) class-A cell {where} is {c['label']}, not S")
        if c["task_class"] == "parallel":
            want = "P" if c["regime"] == "urgent" else "S"
            if c["label"] != want:
                fails.append(f"(b) class-B cell {where} is {c['label']}, not {want}")
        if c["subtype"] == "shortcut" and c["label"] != "S":
            fails.append(f"(c) shortcut cell {where} is {c['label']}, not S")
        if max(c["solo_fitness"], c["div_fitness"]) < MIN_BEST_FITNESS:
            fails.append(f"(d) best fitness in {where} is below {MIN_BEST_FITNESS}")
        if c["solo_fitness"] < MIN_SOLO_FITNESS:
            fails.append(f"(d) solo fitness in {where} is below {MIN_SOLO_FITNESS}")
    sets = label_sets(cells)
    for name in ("S_urgent", "P_urgent", "twin", "D_urgent"):
        if not sets[name]:
            fails.append(f"(e) {name} is empty")
    return {"passed": not fails, "failures": fails, "sets": {k: sorted(v) for k, v in sets.items()}}


def label_sets(cells: dict) -> dict[str, set]:
    """Cell-key sets used by the §8 criteria (and I, used by the secondary H2 analysis)."""
    s = {k for k, c in cells.items() if c["label"] == "S"}
    p = {k for k, c in cells.items() if c["label"] == "P"}
    twin_tasks = {c["task"] for c in cells.values() if c["regime"] == "urgent" and c["label"] == "P"
                  and cells.get(f"{c['task']}|relaxed", {}).get("label") == "S"}
    return {
        "S": s, "P": p,
        "S_urgent": {k for k in s if k.endswith("|urgent")}, "P_urgent": {k for k in p if k.endswith("|urgent")},
        "S_relaxed": {k for k in s if k.endswith("|relaxed")}, "P_relaxed": {k for k in p if k.endswith("|relaxed")},
        "twin": {f"{t}|{r}" for t in twin_tasks for r in ("urgent", "relaxed")},
        "D_urgent": {k for k, c in cells.items() if c["subtype"] == "shortcut" and c["regime"] == "urgent" and k in s},
        "I": {k for k, c in cells.items() if c["incremental"]},
    }


def format_calibration(cal: dict) -> str:
    lines = [f"Calibration (base assumptions {cal.get('assumptions')}, delta={cal['delta']})",
             f"{'cell':<15}{'label':<10}{'I':<3}{'solo':<10}{'fit':>7}  {'best division':<14}{'fit':>7}  "
             f"{'one-shot div':<14}{'fit':>7}{'solo-div margin':>20}"]
    order = {"solo": 0, "parallel": 1, "cross": 2}
    for key, c in sorted(cal["cells"].items(), key=lambda kv: (order[kv[1]["task_class"]], kv[1]["subtype"], kv[0])):
        lines.append(f"{key:<15}{c['label']:<10}{'I' if c['incremental'] else '':<3}{c['solo']:<10}{c['solo_fitness']:>7.3f}  "
                     f"{c['div']:<14}{c['div_fitness']:>7.3f}  {c['router_div']:<14}{c['router_div_fitness']:>7.3f}"
                     f"{c['min_margin']:>+11.3f}..{c['max_margin']:+.3f}")
    g = cal["gate"]
    lines.append(f"GATE: {'PASSED' if g['passed'] else 'FAILED'}  sets: " +
                 ", ".join(f"{k}={len(v)}" for k, v in g["sets"].items()))
    lines += [f"  - {f}" for f in g["failures"][:40]]
    if len(g["failures"]) > 40:
        lines.append(f"  ... and {len(g['failures']) - 40} more")
    return "\n".join(lines)
