"""Experiment 0b diagnostic, part 1: everything answerable without the live logs. LLM-free; no API call.

- the frozen P cells and their oracle organizations (data/exp0b/frozen.json);
- the offline counterfactual for the realized manipulation check: each B-urgent cell simulated in the real runtime,
  in the real modes, at the frozen 0b constants and the frozen (pilot-measured) token assumptions: `single` with the
  oracle's solo plan, and `central` with every fan-out k = 1..#docs (k = 1 is one child doing all the reading);
- the same comparison on the pilot's parallel task X2 at the pilot's own (Experiment 0) constants.

    python analysis/exp0b_diagnostic/offline.py [--input-scale R --reasoning-tokens N]   # -> stdout (JSON)

`--input-scale/--reasoning-tokens` rerun the counterfactual at other token assumptions, for example the live main
run's (traces.py prints them).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from devagents.agents.policies import ScriptedPolicy  # noqa: E402
from devagents.config import EXPERIMENTS, Constants, default_constants, load_frozen  # noqa: E402
from devagents.environment.sources import InformationEnvironment  # noqa: E402
from devagents.environment.tasks import TASKS_BY_ID  # noqa: E402
from devagents.environment.world import load_world  # noqa: E402
from devagents.evals.calibrate import Assumptions, Org, _fitness, grid, oracle_script  # noqa: E402
from devagents.evals.metrics import metrics_from_events  # noqa: E402
from devagents.runtime.runtime import Run, RunConfig  # noqa: E402


def simulate(task, regime, mode: str, org: Org, asm: Assumptions, constants: Constants, info) -> dict:
    """One oracle organization in a real mode (central applies its own fixed allocation rule)."""
    policy = ScriptedPolicy(oracle_script(task, task.routes[org.route], org, asm.extra_work_steps),
                            reasoning_tokens=asm.reasoning_tokens, input_scale=asm.input_scale)
    run = Run(RunConfig(task, regime, mode, compute=constants.compute, coord=constants.coord), policy, info)
    run.execute()
    m = metrics_from_events(run.log.events)
    clean = m["quality"] == 1.0 and m["outcome"] == "answered" and "budget_exhausted" not in m["termination_reasons"]
    return {"fitness": round(_fitness(m, regime), 4) if clean else None, "money_usd": m["money_usd"],
            "elapsed_s": round(m["elapsed_s"], 1), "agents": m["agents"], "llm_calls": m["llm_calls"],
            "parallel": m["parallel"]}


def p_cells(frozen: dict) -> list[dict]:
    rows = []
    for key, c in sorted(frozen["calibration"]["cells"].items()):
        if c["label"] != "P":
            continue
        task = TASKS_BY_ID[c["task"]]
        route = task.routes[int(c["div"].split("@r")[1])]
        best = c["base"][c["div"]]
        rows.append({
            "cell": key, "task": c["task"], "regime": c["regime"], "class": c["task_class"],
            "solo_org": c["solo"], "solo_fitness": c["solo_fitness"], "div_org": c["div"], "div_fitness": c["div_fitness"],
            "one_shot_org": c["router_div"], "one_shot_fitness": c["router_div_fitness"],
            "fan_out": int(c["div"].split("@")[0].lstrip("fanoutatstr")),
            "divides": "at start (first action is SPAWN)" if not route.sql else "after the root's SQL query",
            "route_docs": len(route.docs), "expected_agents": best["agents"], "expected_money_usd": best["money_usd"],
            "expected_elapsed_s": best["elapsed_s"], "expected_llm_calls": best["llm_calls"],
            "solo_money_usd": c["base"][c["solo"]]["money_usd"], "solo_elapsed_s": c["base"][c["solo"]]["elapsed_s"],
        })
    return rows


def counterfactual(frozen: dict, asm: Assumptions) -> dict:
    constants = Constants.from_json(frozen["constants"])
    info = InformationEnvironment(load_world(), constants.sources)
    cells = frozen["calibration"]["cells"]
    b_urgent = sorted(k for k, c in cells.items() if c["task_class"] == "parallel" and c["regime"] == "urgent")
    per_cell = {}
    for key in b_urgent:
        c = cells[key]
        task, regime = TASKS_BY_ID[c["task"]], constants.regimes[c["regime"]]
        row = {"single_solo": simulate(task, regime, "single", Org("solo", 0), asm, constants, info)}
        for k in range(1, len(task.routes[0].docs) + 1):
            row[f"central_k{k}"] = simulate(task, regime, "central", Org("fanout", 0, k), asm, constants, info)
        row["frozen_one_shot"] = c["router_div"]
        per_cell[key] = row

    def mean(name):
        vals = [r[name]["fitness"] for r in per_cell.values() if name in r and r[name]["fitness"] is not None]
        return round(statistics.fmean(vals), 4) if len(vals) == len(per_cell) else None
    best = [r[f"central_k{int(r['frozen_one_shot'].split('@')[0][6:])}"]["fitness"] for r in per_cell.values()]
    return {"assumptions": vars(asm), "b_urgent_cells": b_urgent, "per_cell": per_cell,
            "mean_single": mean("single_solo"), "mean_central_k1": mean("central_k1"),
            "mean_central_k2": mean("central_k2"), "mean_central_frozen_one_shot": round(statistics.fmean(best), 4)}


def grid_check(frozen: dict) -> dict:
    """Over the 18-point perturbation grid: does central (frozen one-shot) beat single, and does central (k = 1)?"""
    base = Assumptions(**frozen["assumptions"])
    out = []
    for asm in grid(base):
        cf = counterfactual(frozen, asm)
        out.append({"assumptions": vars(asm), "single": cf["mean_single"], "central_k1": cf["mean_central_k1"],
                    "central_one_shot": cf["mean_central_frozen_one_shot"]})
    return {"points": out,
            "one_shot_beats_single_everywhere": all(p["central_one_shot"] > p["single"] for p in out),
            "k1_beats_single_anywhere": any(p["central_k1"] is not None and p["central_k1"] > p["single"] for p in out)}


def pilot_x2(asm: Assumptions) -> dict:
    """The pilot's parallel task X2 at the pilot's own constants (Experiment 0 defaults)."""
    constants = default_constants()
    info = InformationEnvironment(load_world(), constants.sources)
    task = TASKS_BY_ID["X2"]
    out = {}
    for name, regime in constants.regimes.items():
        row = {"single_solo": simulate(task, regime, "single", Org("solo", 0), asm, constants, info)}
        for k in range(1, len(task.routes[0].docs) + 1):
            row[f"central_k{k}"] = simulate(task, regime, "central", Org("fanout", 0, k), asm, constants, info)
        out[name] = row
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input-scale", type=float)
    p.add_argument("--reasoning-tokens", type=int)
    p.add_argument("--no-grid", action="store_true")
    a = p.parse_args(argv)
    frozen = load_frozen(EXPERIMENTS["0b"].frozen)
    asm = Assumptions(**frozen["assumptions"])
    if a.input_scale is not None or a.reasoning_tokens is not None:
        asm = Assumptions(a.input_scale or asm.input_scale,
                          a.reasoning_tokens if a.reasoning_tokens is not None else asm.reasoning_tokens)
    res = {"p_cells": p_cells(frozen), "counterfactual": counterfactual(frozen, asm)}
    if not a.no_grid:
        res["grid"] = grid_check(frozen)
    res["pilot_x2"] = pilot_x2(Assumptions(**frozen["assumptions"]))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
