"""Post-hoc analysis of Gate-0 round 1, evaluation 1, from its logged records only (nothing is simulated).

Descriptive, not gated: the frozen decision is the one in data/gate0/round1/eval1/results.json and the audit. This
script (1) re-derives the frozen analysis from records.json and checks that it reproduces results.json, (2) computes
the disclosures that the frozen code left vacuous because no cell qualified (typed one-line rules against A* in every
urgent template cell), (3) re-reads G3/G4 under weaker comparators, and (4) runs the frozen follow-up power model on
the urgent template cells as if they had qualified.

    python -m analysis.gate0.posthoc_round1            # writes analysis/gate0/posthoc_round1.json
"""

from __future__ import annotations

import json
import statistics
from dataclasses import replace
from pathlib import Path

import devagents.gate0.evaluate as ev
from devagents.config import ROOT
from devagents.gate0.audit import Audit, sha256_lf
from devagents.gate0.power import control_worlds, feasibility, followup_inputs
from devagents.gate0.run import base_constants, load_json, validate_candidates

EVAL = ROOT / "data" / "gate0" / "round1" / "eval1"
OUT = Path(__file__).with_suffix(".json")
URGENT = ["A1|urgent", "A2|urgent", "A3|urgent", "B1|urgent", "B2|urgent", "B3|urgent"]


def load_records() -> dict:
    done = Audit().rounds()[1]["completed"][-1]
    if sha256_lf(EVAL / "records.json") != done["records_sha"]:
        raise SystemExit("records.json does not match the audit")
    raw = load_json(EVAL / "records.json")
    cols = raw["columns"]
    recs = {}
    for row in raw["rows"]:
        r = dict(zip(cols, row))
        r["root_brief"] = ""  # not in the compact records; G1's brief comparison cannot be re-checked from them
        r["elapsed_s"] = float(r["elapsed_s"])
        recs[(r["instance"], r["regime"], r["member"], r["plan"], r["cond"])] = r
    return recs


def qualifying_under(views, grid, delta, cells, use_rt=True, use_w=True) -> dict:
    out = {}
    for k in cells:
        cell = tuple(k.split("|"))
        rows = [views[g].cell(cell) for g in grid]
        ok = all((not use_rt or r["adv_rt"] >= delta) and (not use_w or r["adv_w"] >= delta) and r["divergent"]
                 for r in rows)
        out[k] = {"qualifies": ok, "min_adv_rt": min(r["adv_rt"] for r in rows),
                  "min_adv_w": min(r["adv_w"] for r in rows)}
    return out


def count(q: dict) -> dict:
    per = {}
    for k, v in q.items():
        if v["qualifies"]:
            per[k[0]] = per.get(k[0], 0) + 1
    return {"qualifying": sorted(k for k, v in q.items() if v["qualifies"]), "per_template": per,
            "g4_would_pass": sum(per.values()) >= 4 and sum(1 for n in per.values() if n >= 2) >= 2}


def main() -> dict:
    acc = load_json(ROOT / "data/gate0/acceptance.json")
    constants = base_constants(acc)
    _, instances, digests = validate_candidates(1, ROOT / "data/gate0/candidates_round1.json", acc)
    frozen = load_json(EVAL / "results.json")
    if digests != frozen["instances"]:
        raise SystemExit("the worlds differ from the evaluated ones")
    recs = load_records()
    k_max = constants.compute.max_concurrency - 1
    conds, base_cond = ev.conditions(acc, constants)
    delta = acc["delta"]
    out: dict = {"source": {"results_sha": sha256_lf(EVAL / "results.json"),
                            "records_sha": sha256_lf(EVAL / "records.json")}}

    # (1) reproduction of the frozen analysis
    re = ev.analyze(recs, instances, conds, base_cond, acc, k_max)
    same = {c: re["criteria"][c]["pass"] == frozen["criteria"][c]["pass"] for c in re["criteria"]}
    same_cells = all(abs(re["cells"][k]["min_adv_rt"] - frozen["cells"][k]["min_adv_rt"]) < 1e-12
                     and abs(re["cells"][k]["min_adv_w"] - frozen["cells"][k]["min_adv_w"]) < 1e-12
                     for k in re["cells"])
    out["reproduction"] = {"criteria_equal": same, "cells_equal": same_cells,
                           "note": "G1's root-brief comparison is not in records.json; t0_state, pre-reveal logs and "
                                   "reveal times are"}

    grid = [c for c, _, _ in conds if c.startswith("g")]
    const_of = {c: k for c, _, k in conds}
    feats = {(inst.id, r, m.key): ev.features(inst, m, constants.sources)
             for inst in instances for r in constants.regimes for m in inst.members}

    def views_with(t0, post):
        old = ev.T0_FEATURES, ev.POST_FEATURES
        ev.T0_FEATURES, ev.POST_FEATURES = t0, post
        try:
            return {g: ev.View(recs, instances, g, const_of[g], k_max, delta, feats) for g in grid}
        finally:
            ev.T0_FEATURES, ev.POST_FEATURES = old
    views = views_with(ev.T0_FEATURES, ev.POST_FEATURES)
    base = views[base_cond]

    # (2) typed one-line rules against A* in every urgent template cell, at every grid point
    typed = {}
    for g in grid:
        t = ev.typed_rules(views[g], URGENT)
        for key in ("A|urgent", "B|urgent"):
            typed.setdefault(key, {})[g] = {"rule": t[key]["rule"],
                                            "max_shortfall": max(t[key]["shortfall_by_qualifying_cell"].values())}
    out["typed_rules_vs_oracle"] = {
        k: {"rules": sorted({v["rule"] for v in per.values()}),
            "max_shortfall_over_grid_and_cells": max(v["max_shortfall"] for v in per.values()),
            "reproduces_oracle_within_delta_at_every_grid_point": all(v["max_shortfall"] < delta
                                                                     for v in per.values())}
        for k, per in typed.items()}

    # (3) G3/G4 under weaker comparators (descriptive)
    cells = [k for k in frozen["cells"]]
    out["g3_g4_counterfactual"] = {
        "frozen (Rt and W*)": count(qualifying_under(views, grid, delta, cells)),
        "router only": count(qualifying_under(views, grid, delta, cells, use_w=False)),
        "W* only": count(qualifying_under(views, grid, delta, cells, use_rt=False)),
    }
    for label, t0, post in (("W* without t0 features (post-reveal rules and single pipelines)", (), ev.POST_FEATURES),
                            ("W* as a single pipeline per regime (no rule)", (), ())):
        vs = views_with(t0, post)
        out["g3_g4_counterfactual"][label] = {
            **count(qualifying_under(vs, grid, delta, cells)),
            "w_star_rules": sorted({vs[g].wstar["urgent"]["rule"] for g in grid})}

    # absolute fitness at the base point
    table = {}
    for k in URGENT + [c.replace("urgent", "relaxed") for c in URGENT] + ["D|urgent", "D|relaxed"]:
        cell = tuple(k.split("|"))
        r = base.cell(cell)
        ms = base.members(cell)

        def mean(p):
            vals = [base.f((*cell, m), p) for m in ms]
            return statistics.fmean(vals) if all(v > ev.NEG for v in vals) else None
        table[k] = {"blind": mean("blind") if cell[0] != "D" else None, "triage>solo": mean("triage>solo"),
                    "Rt": r["rt"], "Rt_plan": r["rt_plan"], "W*": r.get("w_value"), "A*": r["astar"],
                    "A*_plans": r["astar_plans"], "H*": r["hstar"]}
    out["base_point_fitness"] = table

    # G5 detail: urgent template worlds that need >= 2 documents, worst margin of solo over division on the grid
    g5 = {}
    for w in base.template_worlds:
        if w[1] == "urgent" and len(base.member(w[0], w[2]).needed) >= 2:
            g5["/".join(w)] = min(views[g].no_child_vs_child(w)[0] - views[g].no_child_vs_child(w)[1] for g in grid)
    out["g5_min_solo_minus_division"] = g5

    # (4) the frozen follow-up model on the urgent template cells, as if they had qualified
    cost = acc["power"]["cost"]
    fu = followup_inputs(recs, base, URGENT, constants, cost)
    per_grid = {g: {c.key: c for c in followup_inputs(recs, v, URGENT, constants, cost)} for g, v in views.items()}
    grid_min = [min((per_grid[g][c.key] for g in per_grid), key=lambda x: sum(x.a[m] - x.b[m] for m in x.a))
                for c in fu]
    valid, rejected = control_worlds(base, URGENT, delta)
    spec = acc["power"]
    out["followup_if_urgent_cells_qualified"] = {"control_worlds": valid, "control_worlds_rejected": rejected}
    for label, cs, gm in (("baseline = better of Rt and W* (frozen)", fu, grid_min),
                          ("baseline = Rt only", [replace(c, b=c.r, b_label=c.r_label) for c in fu],
                           [replace(c, b=c.r, b_label=c.r_label) for c in grid_min])):
        f = feasibility(cs, len(valid), spec, constants, gm)
        out["followup_if_urgent_cells_qualified"][label] = f
    return out


def _finite(obj):
    if isinstance(obj, float) and obj != obj:
        return "nan"
    if isinstance(obj, float) and obj in (float("inf"), float("-inf")):
        return "inf" if obj > 0 else "-inf"
    if isinstance(obj, dict):
        return {str(k): _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


if __name__ == "__main__":
    res = main()
    OUT.write_text(json.dumps(_finite(res), indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
