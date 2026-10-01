"""Gate-0 calibration (GATE_0_SPEC.md §2, §5): measure every plan in every world under every condition, derive the
comparison classes, and check the frozen acceptance criteria. LLM-free.

Comparison classes, per cell (instance × regime; the cell's members form its reveal set, uniform prior):
- `Rt`, the one-shot router: the best plan of the library whose organizational structure is fixed at t0, chosen per
  cell to maximize the mean fitness over the reveal set (it may not condition on the reveal).
- `W*`, the best fixed generic workflow, chosen per regime: one workflow applied unchanged to every template world of
  that regime. The class holds every W0 pipeline and every one-line rule (one feature, one global threshold) that
  chooses between two W0 pipelines; a rule on a post-reveal feature may only choose between triage-first pipelines,
  which share their pre-reveal actions.
- `A*`, the adaptive oracle: the best non-anticipating policy over the plan library. All members share the actions
  before the reveal (a prefix group, verified from the logs); after it, each member gets its best continuation.
- `H*`, the clairvoyant: the best plan per world. Within the library, the fully optimal contingent policy C* equals
  A* (the reveal identifies the member), so library coverage is the only bound on C* - A*.
- disclosures: W_typed (the best W0 pipeline per cell) and typed one-line rules (fitted per template and regime).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import replace

from devagents.config import Constants
from devagents.environment.sources import SourceCosts
from devagents.evals.calibrate import Assumptions, grid
from devagents.gate0.plans import clean, fitness, library, parse_plan, run_plan
from devagents.gate0.worlds import Instance, Member
from devagents.runtime.resources import estimate_tokens

NEG = float("-inf")
T0_FEATURES = ("n_units", "n_catalog_docs", "cand_read_s")
POST_FEATURES = ("n_needed", "needed_read_s", "max_needed_s")


# --------------------------------------------------------------------------- conditions


def perturb(constants: Constants, p: dict) -> Constants:
    c = constants
    if "doc_latency" in p:  # both the base latency and the per-token latency
        f = p["doc_latency"]
        c = replace(c, sources=replace(c.sources, doc_base_s=c.sources.doc_base_s * f,
                                       doc_per_token_s=c.sources.doc_per_token_s * f))
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


# --------------------------------------------------------------------------- W0 pipelines and features


def w0_library(k_max: int) -> list[str]:
    names = ["W:blind", "W:solo", "W:fan_all"] + [f"W:fan{k}" for k in range(1, k_max + 1)]
    names += [f"W:self+{k}" for k in range(1, k_max + 1)]
    names += [f"W:fan_if_n>={m}" for m in range(2, k_max + 1)]
    names += [f"W:spec{k}" for k in range(1, k_max + 1)] + [f"W:spec{k}+dissolve" for k in range(1, k_max + 1)]
    names += [f"W:spectop{m}" for m in (1, 2)] + [f"W:spectop{m}+dissolve" for m in (1, 2)]
    return names


def triage_first(pipeline: str) -> bool:
    """Pipelines whose first action is the triage read: they share every pre-reveal action, so a rule on a feature
    revealed by the triage may choose between them without anticipating."""
    return pipeline in ("W:solo", "W:fan_all") or pipeline.startswith(("W:fan", "W:self+"))


def instantiate(pipeline: str, inst: Instance, member: Member, k_max: int) -> str:
    """The plan a generic pipeline runs in one world."""
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
    if pipeline.startswith("W:self+"):
        k = min(int(pipeline[7:]), n_needed - 1)
        return f"triage>self+{k}" if k >= 1 else "triage>solo"
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


def doc_latency(member: Member, doc: str, sources: SourceCosts) -> float:
    return sources.doc_base_s + sources.doc_per_token_s * estimate_tokens(member.world.docs[doc])


def features(inst: Instance, member: Member, sources: SourceCosts) -> dict[str, float]:
    lat = {d: doc_latency(member, d, sources) for d in member.world.docs}
    return {"n_units": len(inst.units), "n_catalog_docs": len(member.world.docs),
            "cand_read_s": sum(lat[d] for d in inst.unit_docs), "n_needed": len(member.needed),
            "needed_read_s": sum(lat[d] for d in member.needed), "max_needed_s": max(lat[d] for d in member.needed)}


# --------------------------------------------------------------------------- one-line workflows (generic or typed)


def _splits(feats: dict, worlds: list, names) -> list[tuple[str, str, frozenset]]:
    """(name, feature, hi-worlds) for every midpoint threshold of each feature over `worlds`."""
    out = []
    for name in names:
        values = sorted({feats[w][name] for w in worlds})
        for lo_v, hi_v in zip(values, values[1:]):
            th = (lo_v + hi_v) / 2
            out.append((f"{name}>={th:g}", name, frozenset(w for w in worlds if feats[w][name] >= th)))
    return out


def best_one_line(val: dict, pipes: list[str], fit_worlds: list, threshold_worlds: list, feats: dict) -> dict:
    """The best workflow, by mean fitness over `fit_worlds`, among single pipelines and one-line rules (thresholds at
    the midpoints of the features over `threshold_worlds`). Returns its description and its plan value per world."""
    def side_best(cands, ws):
        if not ws:
            return None, 0.0
        best = max(cands, key=lambda p: sum(val[(p, w)] for w in ws))
        return best, sum(val[(best, w)] for w in ws)

    p0, s0 = side_best(pipes, fit_worlds)
    best = {"rule": p0, "total": s0, "assign": {w: p0 for w in fit_worlds}}
    tf = [p for p in pipes if triage_first(p)]
    for names, cands in ((T0_FEATURES, pipes), (POST_FEATURES, tf)):
        for split, _, hi in _splits(feats, threshold_worlds, names):
            hi_w = [w for w in fit_worlds if w in hi]
            lo_w = [w for w in fit_worlds if w not in hi]
            lo_p, lo_s = side_best(cands, lo_w)
            hi_p, hi_s = side_best(cands, hi_w)
            if lo_s + hi_s > best["total"] + 1e-12:
                best = {"rule": f"{split} ? {hi_p} : {lo_p}", "total": lo_s + hi_s,
                        "assign": {**{w: lo_p for w in lo_w}, **{w: hi_p for w in hi_w}}}
    best["mean"] = best["total"] / len(fit_worlds)
    return best


# --------------------------------------------------------------------------- analysis of one condition


class View:
    """Everything derived from the records of one condition."""

    def __init__(self, recs: dict, instances: list[Instance], cond: str, constants: Constants, k_max: int,
                 delta: float, feats: dict):
        self.instances, self.cond, self.k_max, self.delta, self.feats = instances, cond, k_max, delta, feats
        self.regimes = constants.regimes
        self.fit: dict = {}
        self.rec: dict = {}
        self.plans: dict = {}
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
        self.pipes = w0_library(k_max)
        self.val = {(p, w): self.pipeline_value(p, w) for p in self.pipes for w in self.worlds}
        self._cell_cache: dict = {}
        self.wstar = {r: best_one_line(self.val, self.pipes, [w for w in self.template_worlds if w[1] == r],
                                       self.template_worlds, feats) for r in self.regimes}

    def f(self, world, plan) -> float:
        v = self.fit.get((*world, plan))
        return NEG if v is None else v

    def member(self, inst_id: str, key: str) -> Member:
        return next(m for m in self.by_id[inst_id].members if m.key == key)

    def members(self, cell) -> list[str]:
        return [m.key for m in self.by_id[cell[0]].members]

    def pipeline_value(self, pipeline: str, world) -> float:
        return self.f(world, instantiate(pipeline, self.by_id[world[0]], self.member(world[0], world[2]), self.k_max))

    def _groups(self, cell) -> dict[str, dict[str, list[str]]]:
        i, _ = cell
        groups: dict = {}
        for m in self.members(cell):
            for p in self.plans[(i, m)]:
                groups.setdefault(parse_plan(p).group, {}).setdefault(m, []).append(p)
        return groups

    def oracle(self, cell, weights: dict) -> tuple[float, str, dict]:
        """A* under a prior: the prefix group with the highest weighted value, each member's best continuation."""
        i, r = cell
        ms = self.members(cell)
        best = (NEG, None, {})
        for g, per in self._groups(cell).items():
            if set(per) != set(ms):
                continue
            choice = {m: max(per[m], key=lambda p, m=m: self.f((i, r, m), p)) for m in ms}
            val = sum(weights[m] * self.f((i, r, m), choice[m]) for m in ms)
            if val > best[0]:
                best = (val, g, choice)
        return best

    def router(self, cell, weights: dict) -> tuple[float, str]:
        i, r = cell
        ms = self.members(cell)
        common = [p for p in self.plans[(i, ms[0])] if all(p in self.plans[(i, m)] for m in ms)]
        fixed = [p for p in common if parse_plan(p).fixed]
        best = max(fixed, key=lambda p: sum(weights[m] * self.f((i, r, m), p) for m in ms))
        return sum(weights[m] * self.f((i, r, m), best) for m in ms), best

    def cell(self, cell) -> dict:
        if cell in self._cell_cache:
            return self._cell_cache[cell]
        i, r = cell
        ms = self.members(cell)
        uni = {m: 1 / len(ms) for m in ms}
        astar, group, plans = self.oracle(cell, uni)
        rt, rt_plan = self.router(cell, uni)
        h = {m: max(self.plans[(i, m)], key=lambda p, m=m: self.f((i, r, m), p)) for m in ms}
        out = {"rt": rt, "rt_plan": rt_plan, "astar": astar, "astar_group": group, "astar_plans": plans,
               "hstar": statistics.fmean(self.f((i, r, m), h[m]) for m in ms), "hstar_plans": h,
               "adv_rt": astar - rt}
        sigs = [tuple(self.rec[(i, r, m, plans[m])]["signature"]) for m in ms] if plans else []
        out["divergent"] = len(set(sigs)) > 1
        out["signatures"] = {m: list(s) for m, s in zip(ms, sigs)}
        if self.by_id[i].template in ("A", "B"):
            ws = self.wstar[r]
            out["w_value"] = statistics.fmean(self.val[(ws["assign"][(i, r, m)], (i, r, m))] for m in ms)
            out["w_plans"] = {m: instantiate(ws["assign"][(i, r, m)], self.by_id[i], self.member(i, m), self.k_max)
                              for m in ms}
            out["adv_w"] = astar - out["w_value"]
            typed = max(self.pipes, key=lambda p: statistics.fmean(self.val[(p, (i, r, m))] for m in ms))
            out["w_typed"] = typed
            out["adv_w_typed"] = astar - statistics.fmean(self.val[(typed, (i, r, m))] for m in ms)
            if len(ms) == 2:
                out["prior"] = {}
                for wx in (0.25, 0.75):
                    wts = {ms[0]: wx, ms[1]: 1 - wx}
                    out["prior"][f"p_{ms[0]}={wx}"] = self.oracle(cell, wts)[0] - self.router(cell, wts)[0]
        self._cell_cache[cell] = out
        return out

    def astar_world(self, world) -> float:
        c = self.cell(world[:2])
        return self.f(world, c["astar_plans"][world[2]]) if c["astar_plans"] else NEG

    def no_child_vs_child(self, world) -> tuple[float, float]:
        i, r, m = world
        solo = max((self.f(world, p) for p in self.plans[(i, m)] if not parse_plan(p).has_children), default=NEG)
        div = max((self.f(world, p) for p in self.plans[(i, m)] if parse_plan(p).has_children), default=NEG)
        return solo, div


# --------------------------------------------------------------------------- criteria


def _integrity(recs: dict, instances: list[Instance], base_cond: str, grid_conds: list[str]) -> dict:
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
            fails.append(f"(a) a plan without children, {i}/{r}/{m}/{p} at {c}, is not clean")
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
        if a.world.sql_script != b.world.sql_script and not any(k == "sql" for k, _ in inst.triage):
            fails.append(f"(d) {inst.id}: the structured source differs but is not the triage source")
    return {"pass": not fails, "failures": fails[:200], "n_failures": len(fails)}


def _dissolution(view: View, cell) -> float:
    """G7 value at one condition: A*'s policy must stop waiting for a child that is still running in at least one
    member; the value is A* minus the best plan of the same prefix group that dissolves nothing (0 otherwise)."""
    r = view.cell(cell)
    g, plans = r["astar_group"], r["astar_plans"]
    if not g or not g.startswith("spec"):
        return 0.0
    i, reg = cell
    if not any(view.rec[(i, reg, m, plans[m])]["signature"][2] > 0 for m in plans):
        return 0.0
    base = []
    for m in plans:
        keep = [p for p in view.plans[(i, m)] if parse_plan(p).group == g
                and view.rec[(i, reg, m, p)]["signature"][2] == 0]
        if not keep:
            return 0.0
        base.append(max(view.f((i, reg, m), p) for p in keep))
    return r["astar"] - statistics.fmean(base)


def typed_rules(view: View, qualifying: list[str]) -> dict:
    """D5: per template and regime, the best one-line workflow fitted on that template's worlds alone, and its
    expected shortfall against A* in each of the template's qualifying cells."""
    out = {}
    for t in ("A", "B"):
        for r in view.regimes:
            ws = [w for w in view.template_worlds if view.by_id[w[0]].template == t and w[1] == r]
            if not ws:
                continue
            best = best_one_line(view.val, view.pipes, ws, view.template_worlds, view.feats)
            short = {}
            for k in qualifying:
                cell = tuple(k.split("|"))
                if view.by_id[cell[0]].template == t and cell[1] == r:
                    ms = view.members(cell)
                    short[k] = view.cell(cell)["astar"] - statistics.fmean(
                        view.val[(best["assign"][(*cell, m)], (*cell, m))] for m in ms)
            out[f"{t}|{r}"] = {"rule": best["rule"], "shortfall_by_qualifying_cell": short,
                               "reproduces_oracle_within_delta": bool(short) and all(v < view.delta
                                                                                    for v in short.values())}
    return out


def analyze(recs: dict, instances: list[Instance], conds, base_cond: str, acc: dict, k_max: int) -> dict:
    delta = acc["delta"]
    grid_conds = [c for c, _, _ in conds if c.startswith("g")]
    pert_conds = [c for c, _, _ in conds if c.startswith("p:")]
    const_of = {c: k for c, _, k in conds}
    by_id = {inst.id: inst for inst in instances}
    feats = {(inst.id, r, m.key): features(inst, m, const_of[base_cond].sources)
             for inst in instances for r in const_of[base_cond].regimes for m in inst.members}
    views = {c: View(recs, instances, c, const_of[c], k_max, delta, feats) for c, _, _ in conds}
    base = views[base_cond]
    templ_cells = [c for c in base.cells if by_id[c[0]].template in ("A", "B")]
    crit: dict = {}

    crit["G1_integrity"] = _integrity(recs, instances, base_cond, grid_conds)

    s = acc["sanity"]
    g2 = []
    for w in base.worlds:
        solo, div = base.no_child_vs_child(w)
        if max(solo, div) < s["min_best"] or solo < s["min_solo"]:
            g2.append(f"{'/'.join(w)}: best {max(solo, div):.3f}, best without children {solo:.3f}")
    crit["G2_sanity"] = {"pass": not g2, "failures": g2}

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
    qualifying = sorted(k for k, c in cells.items() if c["qualifies"])
    per_t: dict = {}
    for k in qualifying:
        per_t[cells[k]["template"]] = per_t.get(cells[k]["template"], 0) + 1
    good_t = [t for t, n in per_t.items() if n >= q["min_cells_per_template"]]
    crit["G3_G4_qualifying"] = {"pass": len(qualifying) >= q["min_cells"] and len(good_t) >= q["min_templates"],
                                "qualifying": qualifying, "per_template": per_t}

    def solo_wins(view, w):
        solo, div = view.no_child_vs_child(w)
        return solo - div >= delta
    d_worlds = [w for w in base.worlds if by_id[w[0]].template == "D" and w[1] == "urgent"]
    d_ok = bool(d_worlds) and all(solo_wins(views[g], w) for g in grid_conds for w in d_worlds)
    ctrl = [w for w in base.template_worlds if w[1] == "urgent" and len(base.member(w[0], w[2]).needed) >= 2
            and all(solo_wins(views[g], w) for g in grid_conds)]
    u = acc["uneconomic_controls"]
    crit["G5_uneconomic_division"] = {
        "pass": d_ok and len(ctrl) >= u["min_worlds"] and len({w[0] for w in ctrl}) >= u["min_instances"],
        "D_urgent_solo_wins_everywhere": d_ok, "template_worlds": ["/".join(w) for w in ctrl]}

    dis = {"|".join(cell): min(_dissolution(views[g], cell) for g in grid_conds) for cell in templ_cells}
    dis_cells = sorted(k for k, v in dis.items() if v >= delta)
    crit["G7_dissolution"] = {"pass": len(dis_cells) >= acc["dissolution"]["min_cells"], "cells": dis_cells,
                              "min_value_by_cell": dis}

    frac = acc["robust_fraction"]
    rob = {}
    for pc in pert_conds:
        per: dict = {}
        for k in qualifying:
            r = views[pc].cell(tuple(k.split("|")))
            if r["adv_rt"] >= frac * delta and r["adv_w"] >= frac * delta and r["divergent"]:
                per[cells[k]["template"]] = per.get(cells[k]["template"], 0) + 1
        ok = (sum(per.values()) >= q["min_cells"]
              and sum(1 for n in per.values() if n >= q["min_cells_per_template"]) >= q["min_templates"])
        rob[pc] = {"pass": ok, "per_template": per}
    crit["G8_robustness"] = {"pass": bool(rob) and all(v["pass"] for v in rob.values()), "perturbations": rob}

    table = {}
    for cell in base.cells:
        r = base.cell(cell)
        row = {k: r.get(k) for k in ("rt_plan", "rt", "astar", "astar_group", "astar_plans", "hstar", "hstar_plans",
                                     "divergent", "signatures", "adv_rt", "adv_w", "w_plans", "w_typed",
                                     "adv_w_typed", "prior")}
        row["fitness"] = {m: {p: base.fit[(cell[0], cell[1], m, p)] for p in base.plans[(cell[0], m)]}
                          for m in base.members(cell)}
        if by_id[cell[0]].template in ("A", "B"):
            row["attribution"] = attribution(base, cell)
        table["|".join(cell)] = row
    disclosures = {
        "typed_one_line_rules": {g: typed_rules(views[g], qualifying) for g in (base_cond,)},
        "typed_one_line_rules_reproduce_oracle_at_any_grid_point": {
            k: any(typed_rules(views[g], qualifying)[k]["reproduces_oracle_within_delta"] for g in grid_conds)
            for k in typed_rules(base, qualifying)},
        "w_star": {g: {r: views[g].wstar[r]["rule"] for r in base.regimes} for g in grid_conds + pert_conds},
        "w_star_value": {g: {r: views[g].wstar[r]["mean"] for r in base.regimes} for g in grid_conds + pert_conds},
        "c_star": "Within the plan library the fully optimal contingent policy equals A* (each reveal identifies its "
                  "member); H* - A* in the table bounds nothing beyond the library.",
    }
    return {"criteria": crit, "cells": cells, "base": table, "disclosures": disclosures,
            "grid_conds": grid_conds, "pert_conds": pert_conds, "base_cond": base_cond,
            "per_grid": {"|".join(c): {g: {k: views[g].cell(c)[k] for k in ("adv_rt", "adv_w", "astar_group",
                                                                              "rt_plan", "divergent")}
                                       for g in grid_conds + pert_conds} for c in templ_cells}}


def attribution(view: View, cell) -> dict:
    """Where the adaptive oracle's value comes from (expected over the reveal set, base point). Undefined terms are
    left out."""
    ms = view.members(cell)

    def mean(p):
        vals = [view.f((*cell, m), p) for m in ms]
        return statistics.fmean(vals) if all(v > NEG for v in vals) else None
    r = view.cell(cell)
    out = {}
    if mean("blind") is not None and mean("triage>solo") is not None:
        out["information_use"] = mean("triage>solo") - mean("blind")
    common = [p for p in view.plans[(cell[0], ms[0])] if all(p in view.plans[(cell[0], m)] for m in ms)]
    fixed_div = [p for p in common if parse_plan(p).fixed and parse_plan(p).has_children and mean(p) is not None]
    if fixed_div and mean("triage>solo") is not None:
        best = max(fixed_div, key=mean)
        out["precommitted_division"] = mean(best) - mean("triage>solo")
        out["precommitted_division_plan"] = best
    out["adaptive_vs_router"] = r["adv_rt"]
    g = r["astar_group"]
    if g == "triage":
        fans = sorted({p for p in common if p.startswith(("triage>fan", "triage>self+"))})
        if fans:
            one = max(statistics.fmean(max(view.f((*cell, m), "triage>solo"), view.f((*cell, m), p)) for m in ms)
                      for p in fans)
            out["divide_or_not_with_one_shape"] = one - r["rt"]
            out["choice_of_shape"] = r["astar"] - one
    elif g and g.startswith("spec"):
        wait = mean(f"{g}>wait")
        if wait is not None:
            out["speculation_vs_router"] = wait - r["rt"]
            out["dead_branch_release"] = _dissolution(view, cell)
        dis, can = mean(f"{g}>dissolve"), mean(f"{g}>cancel")
        if dis is not None and can is not None:
            out["explicit_cancel_vs_release"] = can - dis
    out["clairvoyance_gap"] = r["hstar"] - r["astar"]
    return out
