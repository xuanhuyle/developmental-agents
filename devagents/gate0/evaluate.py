"""Gate-0 calibration (GATE_0_SPEC.md §3, §5): measure every plan in every world under every condition, derive the
comparison classes, and check the frozen acceptance criteria. LLM-free.

Comparison classes, per cell (instance × regime; a cell's members form its reveal set, uniform prior):
- `Rt`, the one-shot router: the best plan whose organizational structure is fixed at t0, chosen per cell to maximize
  the mean fitness over the reveal set (it may not condition on the reveal).
- `W*`, the best fixed generic workflow: one pipeline from the W0 library, applied unchanged to every template world,
  chosen per condition to maximize the mean fitness over all template worlds.
- `A*`, the adaptive oracle: the best non-anticipating policy over the plan library. All members share the actions
  before the reveal (a prefix group, verified from the logs); after it, each member gets its best continuation.
- `H*`, the clairvoyant: the best plan per world, ignoring non-anticipation. The fully optimal contingent policy lies
  between A* and H*.
- rules: one-feature threshold rules choosing between two W0 pipelines (global thresholds), in the families of
  acceptance.json; and the D twin of T01.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import replace

from devagents.config import Constants
from devagents.environment.sources import SourceCosts
from devagents.evals.calibrate import Assumptions, grid
from devagents.gate0.plans import Plan, clean, fitness, library, parse_plan, run_plan
from devagents.gate0.worlds import Instance, Member

NEG = float("-inf")


# --------------------------------------------------------------------------- conditions


def perturb(constants: Constants, p: dict) -> Constants:
    c = constants
    if "doc_per_token_s" in p:
        c = replace(c, sources=replace(c.sources, doc_per_token_s=c.sources.doc_per_token_s * p["doc_per_token_s"]))
    if "value_of_time" in p:
        c = replace(c, regimes={k: replace(r, value_of_time=r.value_of_time * p["value_of_time"])
                                for k, r in c.regimes.items()})
    if "coord_fees" in p:
        f = p["coord_fees"]
        c = replace(c, coord=replace(c.coord, spawn_fee=round(c.coord.spawn_fee * f),
                                     transfer_per_token=round(c.coord.transfer_per_token * f),
                                     message_fee=round(c.coord.message_fee * f),
                                     message_per_token=round(c.coord.message_per_token * f)))
    if "message_latency_s" in p:
        c = replace(c, coord=replace(c.coord, message_latency_s=c.coord.message_latency_s * p["message_latency_s"]))
    return c


def conditions(acc: dict, constants: Constants) -> tuple[list[tuple[str, Assumptions, Constants]], str]:
    base = Assumptions(**acc["token_base"])
    pts = grid(base)
    conds = [(f"g{i}", a, constants) for i, a in enumerate(pts)]
    conds += [(f"p:{p['name']}", base, perturb(constants, p)) for p in acc["env_perturbations"]]
    return conds, f"g{pts.index(base)}"


# --------------------------------------------------------------------------- measurement


def measure(instances: list[Instance], conds, k_max: int, progress=None) -> dict:
    """recs[(inst, regime, member, plan, cond)] -> run record (metrics + checks)."""
    recs = {}
    for inst in instances:
        for member in inst.members:
            plans = library(inst, member, k_max)
            for cname, asm, constants in conds:
                for regime in constants.regimes.values():
                    for plan in plans:
                        recs[(inst.id, regime.name, member.key, plan.name, cname)] = run_plan(
                            inst, member, plan, regime, asm, constants)
            if progress:
                progress(f"{inst.id}/{member.key}: {len(plans)} plans x {len(conds)} conditions x 2 regimes")
    return recs


# --------------------------------------------------------------------------- W0 pipelines and rule features


def w0_library(k_max: int) -> list[str]:
    names = ["W:blind", "W:solo", "W:fan_all"] + [f"W:fan{k}" for k in range(1, k_max + 1)]
    names += [f"W:fan_if_n>={m}" for m in range(2, k_max + 1)]
    names += [f"W:spec{k}" for k in range(1, k_max + 1)] + [f"W:spec{k}+dissolve" for k in range(1, k_max + 1)]
    names += [f"W:spectop{m}" for m in (1, 2)] + [f"W:spectop{m}+dissolve" for m in (1, 2)]
    return names


TRIAGE_PREFIXED = ("W:solo", "W:fan_all", "W:fan", "W:fan_if")


def instantiate(pipeline: str, inst: Instance, member: Member, k_max: int) -> str | None:
    """The plan a generic pipeline runs in one world (None if the pipeline has no meaning there)."""
    n_needed, n_units = len(member.needed), len(inst.units)
    fan_all = f"triage>fan{min(k_max, n_needed)}"
    if pipeline == "W:blind":
        return "blind" if inst.triage else "triage>solo"
    if pipeline == "W:solo":
        return "triage>solo"
    if pipeline == "W:fan_all":
        return fan_all
    if pipeline.startswith("W:fan_if_n>="):
        return fan_all if n_needed >= int(pipeline.split(">=")[1]) else "triage>solo"
    if pipeline.startswith("W:fan"):
        return f"triage>fan{min(int(pipeline[5:]), n_needed)}"
    dissolve = pipeline.endswith("+dissolve")
    head = pipeline[2:].replace("+dissolve", "")
    for pre in ("spectop", "spec"):
        if head.startswith(pre):
            k = min(int(head[len(pre):]), n_units if pre == "spec" else max(1, n_units - 1))
            if not inst.triage:
                return f"triage>fan{min(k, n_needed)}" if pre == "spec" else f"spectop{k}>wait"
            cont = "dissolve" if dissolve and not inst.triage_filters_units else "wait"
            return f"{pre}{k}>{cont}"
    raise ValueError(pipeline)


def doc_latency(inst: Instance, member: Member, doc: str, sources: SourceCosts) -> float:
    from devagents.runtime.resources import estimate_tokens
    return sources.doc_base_s + sources.doc_per_token_s * estimate_tokens(member.world.docs[doc])


def features(inst: Instance, member: Member, regime, sources: SourceCosts) -> dict[str, float]:
    lat = {d: doc_latency(inst, member, d, sources) for d in member.world.docs}
    cand = sum(lat[d] for d in inst.unit_docs)
    needed = sum(lat[d] for d in member.needed)
    return {"urgent": regime.value_of_time, "n_units": len(inst.units), "n_catalog_docs": len(member.world.docs),
            "cand_read_s": cand, "n_needed": len(member.needed), "needed_read_s": needed,
            "max_needed_s": max(lat[d] for d in member.needed), "vot_x_cand_read": regime.value_of_time * cand,
            "vot_x_needed_read": regime.value_of_time * needed}


# --------------------------------------------------------------------------- analysis of one condition


class View:
    """Everything derived from the records of one condition."""

    def __init__(self, recs: dict, instances: list[Instance], cond: str, constants: Constants, k_max: int,
                 delta: float):
        self.instances, self.cond, self.k_max, self.delta = instances, cond, k_max, delta
        self.regimes = constants.regimes
        self.fit: dict = {}  # (inst, regime, member, plan) -> fitness | None
        self.rec: dict = {}
        self.plans: dict = {}  # (inst, member) -> [plan names]
        for (i, r, m, p, c), rec in recs.items():
            if c == cond:
                self.fit[(i, r, m, p)] = fitness(rec, self.regimes[r])
                self.rec[(i, r, m, p)] = rec
                self.plans.setdefault((i, m), [])
                if p not in self.plans[(i, m)]:
                    self.plans[(i, m)].append(p)
        self.by_id = {inst.id: inst for inst in instances}
        self.cells = [(inst.id, r) for inst in instances for r in self.regimes]
        self.worlds = [(inst.id, r, m.key) for inst in instances for r in self.regimes for m in inst.members]
        self.template_worlds = [w for w in self.worlds if self.by_id[w[0]].template in ("A", "B")]
        self._cell_cache: dict = {}
        self.w_star, self.w_star_value = self._w_star()

    def f(self, world, plan) -> float:
        v = self.fit.get((*world, plan))
        return NEG if v is None else v

    def members(self, cell) -> list[str]:
        return [m.key for m in self.by_id[cell[0]].members]

    def cell(self, cell) -> dict:
        if cell in self._cell_cache:
            return self._cell_cache[cell]
        i, r = cell
        ms = self.members(cell)
        common = [p for p in self.plans[(i, ms[0])] if all(p in self.plans[(i, m)] for m in ms)]
        mean = lambda p: statistics.fmean(self.f((i, r, m), p) for m in ms)  # noqa: E731
        fixed = [p for p in common if parse_plan(p).fixed]
        rt_plan = max(fixed, key=mean)
        groups: dict[str, dict[str, list[str]]] = {}
        for m in ms:
            for p in self.plans[(i, m)]:
                groups.setdefault(parse_plan(p).group, {}).setdefault(m, []).append(p)
        best_group, best_val, best_plans = None, NEG, {}
        group_values = {}
        for g, per in groups.items():
            if set(per) != set(ms):
                continue
            choice = {m: max(per[m], key=lambda p, m=m: self.f((i, r, m), p)) for m in ms}
            val = statistics.fmean(self.f((i, r, m), choice[m]) for m in ms)
            group_values[g] = (val, choice)
            if val > best_val:
                best_group, best_val, best_plans = g, val, choice
        h_star = {m: max(self.plans[(i, m)], key=lambda p, m=m: self.f((i, r, m), p)) for m in ms}
        out = {"rt_plan": rt_plan, "rt": mean(rt_plan), "astar": best_val, "astar_group": best_group,
               "astar_plans": best_plans, "group_values": group_values,
               "hstar": statistics.fmean(self.f((i, r, m), h_star[m]) for m in ms), "hstar_plans": h_star,
               "common": common}
        out["adv_rt"] = out["astar"] - out["rt"]
        if self.by_id[i].template in ("A", "B"):
            wp = {m: instantiate(self.w_star, self.by_id[i], self._member(i, m), self.k_max) for m in ms}
            out["w_value"] = statistics.fmean(self.f((i, r, m), wp[m]) for m in ms)
            out["adv_w"] = out["astar"] - out["w_value"]
        sigs = [tuple(self.rec[(i, r, m, best_plans[m])]["signature"]) for m in ms] if best_plans else []
        out["divergent"] = len(set(sigs)) > 1
        out["signatures"] = {m: list(s) for m, s in zip(ms, sigs)}
        self._cell_cache[cell] = out
        return out

    def _member(self, inst_id: str, key: str) -> Member:
        return next(m for m in self.by_id[inst_id].members if m.key == key)

    def astar_world(self, world) -> float:
        c = self.cell(world[:2])
        return self.f(world, c["astar_plans"][world[2]]) if c["astar_plans"] else NEG

    def pipeline_value(self, pipeline: str, world) -> float:
        plan = instantiate(pipeline, self.by_id[world[0]], self._member(world[0], world[2]), self.k_max)
        return NEG if plan is None else self.f(world, plan)

    def _w_star(self) -> tuple[str, float]:
        best, best_v = None, NEG
        for p in w0_library(self.k_max):
            v = statistics.fmean(self.pipeline_value(p, w) for w in self.template_worlds)
            if v > best_v:
                best, best_v = p, v
        return best, best_v

    def no_child_vs_child(self, world) -> tuple[float, float]:
        i, r, m = world
        solo = max((self.f(world, p) for p in self.plans[(i, m)] if not parse_plan(p).has_children), default=NEG)
        div = max((self.f(world, p) for p in self.plans[(i, m)] if parse_plan(p).has_children), default=NEG)
        return solo, div


# --------------------------------------------------------------------------- rules (dissociation and disclosure)


def rule_analysis(view: View, feats: dict, families: dict, delta: float) -> dict:
    """For each family: the minimum number of cells in which a rule falls >= delta short of A* (over all rules of the
    family), the rule achieving it, and the smallest mean shortfall over the rule worlds (with its rule)."""
    worlds = view.template_worlds + [w for w in view.worlds if view.by_id[w[0]].template == "D"]
    cells = sorted({w[:2] for w in worlds})
    cell_bit = {c: 1 << i for i, c in enumerate(cells)}
    astar = {w: view.astar_world(w) for w in worlds}
    pipes = w0_library(view.k_max)
    val = {(p, w): view.pipeline_value(p, w) for p in pipes for w in worlds}
    out = {}
    for fam, spec in families.items():
        best_count, best_rule, best_short, best_short_rule = math.inf, None, math.inf, None
        allowed = pipes if not spec["post_reveal"] else [p for p in pipes if p.startswith(TRIAGE_PREFIXED)]
        for split_name, hi_worlds in _splits(spec, feats, worlds):
            lo_worlds = [w for w in worlds if w not in hi_worlds]
            lo_mask, hi_mask, lo_short, hi_short = {}, {}, {}, {}
            for p in allowed:
                lo_mask[p] = _cells_short(p, lo_worlds, val, astar, delta, cell_bit)
                hi_mask[p] = _cells_short(p, hi_worlds, val, astar, delta, cell_bit)
                lo_short[p] = sum(astar[w] - val[(p, w)] for w in lo_worlds)
                hi_short[p] = sum(astar[w] - val[(p, w)] for w in hi_worlds)
            for lo in allowed:
                for hi in allowed:
                    n = bin(lo_mask[lo] | hi_mask[hi]).count("1")
                    if n < best_count:
                        best_count, best_rule = n, (split_name, lo, hi)
            lo_b = min(allowed, key=lo_short.get)
            hi_b = min(allowed, key=hi_short.get)
            short = (lo_short[lo_b] + hi_short[hi_b]) / len(worlds)
            if short < best_short:
                best_short, best_short_rule = short, (split_name, lo_b, hi_b)
        out[fam] = {"min_cells_short": best_count, "rule": best_rule, "min_mean_shortfall": best_short,
                    "shortfall_rule": best_short_rule}
    return out


def _cells_short(p, ws, val, astar, delta, cell_bit) -> int:
    mask = 0
    for w in ws:
        if astar[w] - val[(p, w)] >= delta:
            mask |= cell_bit[w[:2]]
    return mask


def _splits(spec: dict, feats: dict, worlds: list):
    """(name, hi-worlds) for every threshold of the family's features (and the constant split)."""
    yield "constant", []
    for name in spec["features"]:
        values = sorted({feats[w][name] for w in worlds})
        for lo_v, hi_v in zip(values, values[1:]):
            th = (lo_v + hi_v) / 2
            yield f"{name}>={th:g}", [w for w in worlds if feats[w][name] >= th]
    if spec.get("conjunction"):
        units = sorted({feats[w]["n_units"] for w in worlds})
        for m in units:
            yield f"urgent&n_units>={m}", [w for w in worlds if feats[w]["urgent"] >= spec["urgent_threshold"]
                                           and feats[w]["n_units"] >= m]


# --------------------------------------------------------------------------- criteria


def _integrity(recs: dict, instances: list[Instance], conds, base_cond: str, grid_conds: list[str], regimes) -> dict:
    """G1: clean base runs, identical t0 states and pre-reveal logs across members and within prefix groups, and
    members that differ only in the triage source."""
    fails = []
    by_key: dict = {}
    for (i, r, m, p, c), rec in recs.items():
        by_key.setdefault((i, r, c, p), {})[m] = rec
        if c == base_cond and not clean(rec):
            fails.append(f"(a) {i}/{r}/{m}/{p} at base is not clean: outcome={rec['outcome']} q={rec['quality']} "
                         f"info={rec['info_complete']} invalid={rec['invalid_actions']} reasons={rec['termination_reasons']}")
        if c in grid_conds and not parse_plan(p).has_children and not clean(rec):
            fails.append(f"(a) solo-type {i}/{r}/{m}/{p} at {c} is not clean")
    by_id = {inst.id: inst for inst in instances}
    for (i, r, c, p), per in by_key.items():
        inst = by_id[i]
        if inst.template == "D":
            continue
        if len({rec["t0_state"] for rec in per.values()}) > 1 or len({rec["root_brief"] for rec in per.values()}) > 1:
            fails.append(f"(b) {i}/{r}/{c}/{p}: the t0 state differs between members")
        if any(rec["t_reveal"] is None for rec in per.values()):
            fails.append(f"(c) {i}/{r}/{c}/{p}: the triage source was never read")
        if len(per) == len(inst.members):
            if len({rec["pre_reveal"] for rec in per.values()}) > 1:
                fails.append(f"(c) {i}/{r}/{c}/{p}: the logs differ between members before the reveal")
            if len({rec["t_reveal"] for rec in per.values()}) > 1:
                fails.append(f"(c) {i}/{r}/{c}/{p}: the reveal happens at different times")
    groups: dict = {}
    for (i, r, m, p, c), rec in recs.items():
        if by_id[i].template != "D":
            groups.setdefault((i, r, m, c, parse_plan(p).group), set()).add(rec["pre_reveal"])
    fails += [f"(c) {k}: plans of one prefix group differ before the reveal" for k, v in groups.items() if len(v) > 1]
    for inst in instances:
        if len(inst.members) < 2:
            continue
        a, b = inst.members[0], inst.members[1]
        if a.reveal == b.reveal or set(a.needed) == set(b.needed):
            fails.append(f"(d) {inst.id}: the members do not differ in what the triage reveals")
        if set(a.world.docs) != set(b.world.docs):
            fails.append(f"(d) {inst.id}: the members' catalogs differ")
        triage_docs = {t for k, t in inst.triage if k == "doc"}
        diff_docs = {d for d in a.world.docs if a.world.docs[d] != b.world.docs[d]}
        if diff_docs - triage_docs:
            fails.append(f"(d) {inst.id}: documents other than the triage source differ: {sorted(diff_docs - triage_docs)}")
        sql_triage = any(k == "sql" for k, _ in inst.triage)
        if a.world.sql_script != b.world.sql_script and not sql_triage:
            fails.append(f"(d) {inst.id}: the structured source differs but is not the triage source")
    return {"pass": not fails, "failures": fails[:200], "n_failures": len(fails)}


def analyze(recs: dict, instances: list[Instance], conds, base_cond: str, acc: dict, k_max: int) -> dict:
    delta = acc["delta"]
    grid_conds = [c for c, _, _ in conds if c.startswith("g")]
    pert_conds = [c for c, _, _ in conds if c.startswith("p:")]
    const_of = {c: k for c, _, k in conds}
    views = {c: View(recs, instances, c, const_of[c], k_max, delta) for c, _, _ in conds}
    base = views[base_cond]
    by_id = base.by_id
    templ_cells = [c for c in base.cells if by_id[c[0]].template in ("A", "B")]
    crit: dict = {}

    crit["G1_integrity"] = _integrity(recs, instances, conds, base_cond, grid_conds, base.regimes)

    # G2 sanity (base)
    s = acc["sanity"]
    g2 = []
    for w in base.worlds:
        solo, div = base.no_child_vs_child(w)
        best = max(solo, div)
        if best < s["min_best"] or solo < s["min_solo"]:
            g2.append(f"{'/'.join(w)}: best {best:.3f}, best without children {solo:.3f}")
    crit["G2_sanity"] = {"pass": not g2, "failures": g2}

    # G3/G4 qualification
    cells = {}
    for cell in templ_cells:
        rows = [views[g].cell(cell) for g in grid_conds]
        cells["|".join(cell)] = {
            "template": by_id[cell[0]].template,
            "qualifies": all(r["adv_rt"] >= delta and r["adv_w"] >= delta and r["divergent"] for r in rows),
            "min_adv_rt": min(r["adv_rt"] for r in rows), "min_adv_w": min(r["adv_w"] for r in rows),
            "divergent_everywhere": all(r["divergent"] for r in rows),
            "astar_groups": sorted({r["astar_group"] for r in rows}),
        }
    q = acc["qualify"]
    per_t = {}
    for k, c in cells.items():
        if c["qualifies"]:
            per_t[c["template"]] = per_t.get(c["template"], 0) + 1
    n_q = sum(per_t.values())
    good_t = [t for t, n in per_t.items() if n >= q["min_cells_per_template"]]
    crit["G3_G4_qualifying"] = {"pass": n_q >= q["min_cells"] and len(good_t) >= q["min_templates"],
                                "qualifying": sorted(k for k, c in cells.items() if c["qualifies"]),
                                "per_template": per_t}

    # G5 uneconomic-division controls
    d_worlds = [w for w in base.worlds if by_id[w[0]].template == "D" and w[1] == "urgent"]
    d_ok = bool(d_worlds) and all(
        (lambda sd: sd[0] - sd[1] >= delta)(views[g].no_child_vs_child(w)) for g in grid_conds for w in d_worlds)
    ctrl = [w for w in base.template_worlds if w[1] == "urgent"
            and len(next(m for m in by_id[w[0]].members if m.key == w[2]).needed) >= 2
            and all((lambda sd: sd[0] - sd[1] >= delta)(views[g].no_child_vs_child(w)) for g in grid_conds)]
    u = acc["uneconomic_controls"]
    crit["G5_uneconomic_division"] = {
        "pass": d_ok and len(ctrl) >= u["min_worlds"] and len({w[0] for w in ctrl}) >= u["min_instances"],
        "D_urgent_solo_wins_everywhere": d_ok, "template_worlds": ["/".join(w) for w in ctrl]}

    # G6 dissociation from simple rules (and the economic disclosure)
    feats = {w: features(by_id[w[0]], next(m for m in by_id[w[0]].members if m.key == w[2]), base.regimes[w[1]],
                         const_of[base_cond].sources) for w in base.worlds}
    fams = acc["rule_families"]
    rule_rows = {g: rule_analysis(views[g], feats, fams, delta) for g in grid_conds}
    fam_summary = {}
    for fam, spec in fams.items():
        mins = [rule_rows[g][fam]["min_cells_short"] for g in grid_conds]
        worst_g = grid_conds[mins.index(min(mins))]
        fam_summary[fam] = {"gating": spec["gating"], "min_cells_short": min(mins),
                            "rule_at_min": rule_rows[worst_g][fam]["rule"], "at": worst_g,
                            "base_min_mean_shortfall": rule_rows[base_cond][fam]["min_mean_shortfall"],
                            "base_shortfall_rule": rule_rows[base_cond][fam]["shortfall_rule"]}
    need = acc["dissociation"]["min_cells"]
    crit["G6_dissociation"] = {"pass": all(v["min_cells_short"] >= need for v in fam_summary.values() if v["gating"]),
                               "families": fam_summary}

    # G7 dissolution opportunity
    dis = {}
    for cell in templ_cells:
        vals = []
        for g in grid_conds:
            r = views[g].cell(cell)
            grp = r["astar_group"]
            if grp and grp.startswith("spec"):
                wait = f"{grp}>wait"
                ms = views[g].members(cell)
                if all(wait in views[g].plans[(cell[0], m)] for m in ms):
                    vals.append(r["astar"] - statistics.fmean(views[g].f((*cell, m), wait) for m in ms))
                    continue
            vals.append(0.0)
        dis["|".join(cell)] = min(vals)
    dis_cells = sorted(k for k, v in dis.items() if v >= delta)
    crit["G7_dissolution"] = {"pass": len(dis_cells) >= acc["dissolution"]["min_cells"], "cells": dis_cells,
                              "min_value_by_cell": dis}

    # G8 robustness under environment perturbations
    frac = acc["robust_fraction"]
    rob = {}
    for pc in pert_conds:
        per = {}
        for k in crit["G3_G4_qualifying"]["qualifying"]:
            cell = tuple(k.split("|"))
            r = views[pc].cell(cell)
            if r["adv_rt"] >= frac * delta and r["adv_w"] >= frac * delta:
                per[cells[k]["template"]] = per.get(cells[k]["template"], 0) + 1
        ok = (sum(per.values()) >= q["min_cells"]
              and sum(1 for n in per.values() if n >= q["min_cells_per_template"]) >= q["min_templates"])
        rob[pc] = {"pass": ok, "per_template": per}
    crit["G8_robustness"] = {"pass": bool(rob) and all(v["pass"] for v in rob.values()), "perturbations": rob}

    # base-point tables and disclosures
    table = {}
    for cell in templ_cells + [c for c in base.cells if by_id[c[0]].template == "D"]:
        r = base.cell(cell)
        row = {k: r[k] for k in ("rt_plan", "rt", "astar", "astar_group", "astar_plans", "hstar", "hstar_plans",
                                 "divergent", "signatures")}
        row["adv_rt"], row["adv_w"] = r["adv_rt"], r.get("adv_w")
        row["fitness"] = {m: {p: base.fit[(cell[0], cell[1], m, p)] for p in base.plans[(cell[0], m)]}
                          for m in base.members(cell)}
        if by_id[cell[0]].template in ("A", "B"):
            row["attribution"] = attribution(base, cell)
            typed = max(w0_library(k_max), key=lambda p: statistics.fmean(
                base.pipeline_value(p, (*cell, m)) for m in base.members(cell)))
            row["w_typed"] = typed
            row["adv_w_typed"] = r["astar"] - statistics.fmean(base.pipeline_value(typed, (*cell, m))
                                                               for m in base.members(cell))
        table["|".join(cell)] = row
    return {"criteria": crit, "cells": cells, "base": table, "w_star": {g: views[g].w_star for g in grid_conds + pert_conds},
            "w_star_value": {g: views[g].w_star_value for g in grid_conds + pert_conds},
            "grid_conds": grid_conds, "pert_conds": pert_conds, "base_cond": base_cond,
            "per_grid": {"|".join(c): {g: {k: views[g].cell(c)[k] for k in ("adv_rt", "adv_w", "astar_group", "rt_plan")}
                                       for g in grid_conds + pert_conds} for c in templ_cells}}


def attribution(view: View, cell) -> dict:
    """Where the adaptive oracle's value comes from (expected over the reveal set, base point)."""
    ms = view.members(cell)
    mean = lambda p: statistics.fmean(view.f((*cell, m), p) for m in ms)  # noqa: E731
    r = view.cell(cell)
    common = r["common"]
    out = {}
    if "blind" in common:
        out["information_use"] = mean("triage>solo") - mean("blind")  # reading only what the triage selects
    fixed_div = [p for p in common if parse_plan(p).fixed and parse_plan(p).has_children]
    if fixed_div:
        best = max(fixed_div, key=mean)
        out["precommitted_division"] = mean(best) - mean("triage>solo")
        out["precommitted_division_plan"] = best
    out["adaptive_vs_router"] = r["adv_rt"]
    g = r["astar_group"]
    if g == "triage":
        fans = sorted({int(p[10:]) for p in common if p.startswith("triage>fan")})
        one_k = max((statistics.fmean(max(view.f((*cell, m), "triage>solo"), view.f((*cell, m), f"triage>fan{k}"))
                                      for m in ms), k) for k in fans) if fans else (NEG, 0)
        out["divide_or_not_with_one_k"] = one_k[0] - r["rt"]
        out["choice_of_k"] = r["astar"] - one_k[0]
    elif g and g.startswith("spec"):
        wait = statistics.fmean(view.f((*cell, m), f"{g}>wait") for m in ms)
        out["speculation_vs_router"] = wait - r["rt"]
        out["dissolution"] = r["astar"] - wait
        out["explicit_cancel_vs_dissolve"] = (statistics.fmean(view.f((*cell, m), f"{g}>cancel") for m in ms)
                                              - statistics.fmean(view.f((*cell, m), f"{g}>dissolve") for m in ms))
    out["clairvoyance_gap"] = r["hstar"] - r["astar"]
    return out
