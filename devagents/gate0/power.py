"""Gate-0 follow-up feasibility (GATE_0_SPEC.md §7): a pre-declared follow-up design within the run ceiling, its cost,
and the Monte-Carlo power of its primary analysis.

Nothing here is evidence about any LLM. No policy has ever adapted in this environment, so its behaviour and variance
are unknown: every number is *conditional* on declared assumptions (acceptance.json "power.primary"), and the
sensitivity and pessimistic tables show how the conclusion moves with them.

Generative model, per qualifying cell c (a reveal set, both members) and run:
- the mechanism arm M takes the adaptive oracle's plan for its member with probability pi_c; otherwise it falls back to
  the 0b/0c default (triage, then read alone) with probability q_default, and to the cell's best precommitted plan B
  otherwise; logit(pi_c) = logit(pi) + s*(sqrt(rho)*z_template + sqrt(1-rho)*z_cell);
- the ablation arm ABL (M with the revealed state hidden) never takes the oracle's plan; it falls back to the default
  with probability q_default and otherwise to the router's plan, which is fixed at t0;
- a run's fitness is the simulated base-point fitness of its plan, plus N(0, sigma^2); M's and ABL's runs also carry a
  cell bias N(0, tau_sim^2) and an overhead eta, and, for the deliberation mechanism, one priced high-effort checkpoint
  per general event of the plan it ran (t0, the reveal, each child's termination); a run answers wrongly with
  probability p_fail (B and N) or p_fail_M (M and ABL), which costs 1.0 (quality 0);
- the baseline B and the no-LLM controller N run plan B; on control worlds (validated relaxed twins) M spawns with
  probability s_ctl.

Analysis, with the qualifying cells as fixed cells (no population claim), all required:
F1 per template: adaptation contrast >= 0.30, with a normal lower bound > 0; F2: raw fitness M - B over cells and
members, lower bound > 0, and every template's estimate > 0; F3: spawn rate on controls <= 0.20; F4: F2 against N;
F5: M's adaptation contrast exceeds the ablation arm's, lower bound > 0.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field, replace

from devagents.gate0.evaluate import View

Z = 1.959964


def _logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


ROLES = ("a", "b", "d", "r")  # the oracle's plan, the best precommitted plan, the 0b/0c default, the router's plan


@dataclass
class CellInput:
    key: str
    template: str
    regime: str
    a: dict  # member -> fitness of the oracle's plan
    b: dict  # member -> fitness of the best precommitted plan (Rt or W*, whichever is higher in expectation)
    d: dict  # member -> fitness of the 0b/0c default plan (triage, then read alone)
    r: dict  # member -> fitness of the router's plan (structure fixed at t0)
    a_label: dict  # member -> 1 if the plan reorganizes in the oracle's X direction after the reveal
    b_label: dict
    d_label: dict
    r_label: dict
    checkpoints: dict = field(default_factory=dict)  # role -> member -> high-effort checkpoints of that plan
    ck_eta: float = 0.0  # fitness cost of one high-effort checkpoint
    costs: dict = field(default_factory=dict)

    def value(self, role: str, m: str) -> float:
        return getattr(self, role)[m]

    def label(self, role: str, m: str) -> int:
        return getattr(self, f"{role}_label")[m]


def _axis_label(sig, sx, sy) -> int:
    axis = [j for j in range(3) if sx[j] != sy[j]]
    return int(bool(axis) and all((sig[j] - sy[j]) * (sx[j] - sy[j]) > 0 for j in axis))


def checkpoint_eta(regime, constants, spec_cost: dict, out_tokens: int | None = None) -> float:
    """Fitness cost of one high-effort checkpoint (its own tokens), priced by the runtime's money and latency model."""
    c = constants.compute
    out_t = spec_cost["checkpoint_output_tokens"] if out_tokens is None else out_tokens
    in_t = spec_cost["checkpoint_input_tokens"]
    money = (out_t * c.price_out + in_t * c.price_in) / 1e6
    secs = out_t * c.latency_out_s + in_t * c.latency_in_s
    return (money + regime.value_of_time * secs) / regime.task_value


def followup_inputs(recs: dict, view: View, qualifying: list[str], constants, spec_cost: dict) -> list[CellInput]:
    out = []
    for key in qualifying:
        cell = tuple(key.split("|"))
        r = view.cell(cell)
        ms = view.members(cell)
        inst = view.by_id[cell[0]]
        rec = lambda m, p: recs[(cell[0], cell[1], m, p, view.cond)]  # noqa: E731
        b_plans = ({m: r["rt_plan"] for m in ms} if r["rt"] >= r["w_value"] else r["w_plans"])
        d_plans = {m: "triage>solo" for m in ms}
        plans = {"a": r["astar_plans"], "b": b_plans, "d": d_plans, "r": {m: r["rt_plan"] for m in ms}}
        sx, sy = r["signatures"]["X"], r["signatures"]["Y"]
        lab = lambda m, p: _axis_label(rec(m, p)["signature"], sx, sy)  # noqa: E731

        def cost(m, p):
            x = rec(m, p)
            return {"calls": x["llm_calls"], "in_tokens": x["in_tokens"], "out_tokens": x["out_tokens"],
                    "api_usd": (x["in_tokens"] * constants.compute.price_in
                                + x["out_tokens"] * constants.compute.price_out) / 1e6}
        def events(m, p):
            sig = rec(m, p)["signature"]
            return spec_cost["checkpoints_base"] + spec_cost["checkpoints_per_child"] * (sig[0] + sig[1])
        val = {role: {m: view.f((*cell, m), plans[role][m]) for m in ms} for role in ROLES}
        labels = {role: {m: lab(m, plans[role][m]) for m in ms} for role in ROLES}
        out.append(CellInput(
            key, inst.template, cell[1], val["a"], val["b"], val["d"], val["r"],
            labels["a"], labels["b"], labels["d"], labels["r"],
            {role: {m: events(m, plans[role][m]) for m in ms} for role in ROLES},
            checkpoint_eta(view.regimes[cell[1]], constants, spec_cost),
            {"M": {m: cost(m, plans["a"][m]) for m in ms}, "B": {m: cost(m, b_plans[m]) for m in ms},
             "D": {m: cost(m, d_plans[m]) for m in ms}}))
    return out


def control_worlds(view: View, qualifying: list[str], delta: float) -> tuple[list, list]:
    """The relaxed twins of the qualifying cells' instances, kept only if division clearly does not pay there."""
    valid, rejected = [], []
    for inst_id in sorted({k.split("|")[0] for k in qualifying}):
        for m in view.members((inst_id, "relaxed")):
            w = (inst_id, "relaxed", m)
            solo, div = view.no_child_vs_child(w)
            (valid if solo - div >= delta else rejected).append("/".join(w))
    return valid, rejected


# --------------------------------------------------------------------------- one simulated follow-up


def _mv(xs: list[float]) -> tuple[int, float, float]:
    n = len(xs)
    m = sum(xs) / n if n else 0.0
    v = sum((x - m) ** 2 for x in xs) / (n - 1) if n > 1 else 0.0
    return n, m, v


def _p_var(k: int, n: int) -> tuple[float, float]:
    """Proportion and its variance, with one pseudo-success and one pseudo-failure (never zero variance)."""
    p = (k + 1) / (n + 2)
    return k / n if n else 0.0, p * (1 - p) / (n + 2)


def simulate_once(rng: random.Random, cells: list[CellInput], alloc: dict, a: dict, variant: str,
                  n_controls: int) -> dict:
    templates = sorted({c.template for c in cells})
    z_t = {t: rng.gauss(0, 1) for t in templates}
    rows = []
    for c in cells:
        if 0 < a["pi"] < 1:
            pi_c = _sigmoid(_logit(a["pi"]) + a["logit_sd"] * (math.sqrt(a["rho"]) * z_t[c.template]
                                                              + math.sqrt(1 - a["rho"]) * rng.gauss(0, 1)))
        else:
            pi_c = a["pi"]
        bias = rng.gauss(0, a["tau_sim"]) if a["tau_sim"] > 0 else 0.0
        row = {}
        for m in c.a:
            arms = {}
            for arm, n in (("M", alloc["R_M"]), ("ABL", alloc["R_ABL"]), ("B", alloc["R_B"]), ("N", alloc["R_N"])):
                vals, labels = [], []
                for _ in range(n):
                    if arm in ("M", "ABL"):
                        if arm == "M" and rng.random() < pi_c:
                            role = "a"
                        elif rng.random() < a["q_default"]:
                            role = "d"
                        else:
                            role = "b" if arm == "M" else "r"
                        base = c.value(role, m) + bias - a["eta"]
                        if variant == "deliberation":
                            base -= c.ck_eta * c.checkpoints[role][m]
                        p_fail = a["p_fail_M"]
                    else:
                        role, base, p_fail = "b", c.b[m], a["p_fail"]
                    vals.append(base + rng.gauss(0, a["sigma"]) - (1.0 if rng.random() < p_fail else 0.0))
                    labels.append(c.label(role, m))
                arms[arm] = (vals, labels)
            row[m] = arms
        rows.append((c, row))
    spawns = sum(rng.random() < a["s_ctl"] for _ in range(n_controls))
    return evaluate_followup(rows, spawns, n_controls, a)


def evaluate_followup(rows, spawns: int, n_controls: int, a: dict) -> dict:
    """The follow-up's pre-declared analysis on one data set (rows: [(CellInput, {member: {arm: (values, labels)}})])."""
    def contrast(row, arm):
        px, vx = _p_var(sum(row["X"][arm][1]), len(row["X"][arm][1]))
        py, vy = _p_var(sum(row["Y"][arm][1]), len(row["Y"][arm][1]))
        return px - py, vx + vy

    f = {}
    ok1 = True
    for t in sorted({c.template for c, _ in rows}):
        sub = [contrast(row, "M") for c, row in rows if c.template == t]
        est = statistics.fmean(e for e, _ in sub)
        se = math.sqrt(sum(v for _, v in sub)) / len(sub)
        ok1 = ok1 and est >= a["contrast_min"] and est - Z * se > 0
    f["F1"] = ok1

    def diff(arm):
        terms, by_t = [], {}
        for c, row in rows:
            for m in row:
                nm, mm, vm = _mv(row[m]["M"][0])
                nb, mb, vb = _mv(row[m][arm][0])
                terms.append((mm - mb, vm / nm + vb / nb))
                by_t.setdefault(c.template, []).append(mm - mb)
        est = statistics.fmean(d for d, _ in terms)
        se = math.sqrt(sum(v for _, v in terms)) / len(terms)
        return est, est - Z * se, all(statistics.fmean(v) > 0 for v in by_t.values())

    d_est, d_lb, d_each = diff("B")
    _, n_lb, n_each = diff("N")
    f["F2"] = d_lb > 0 and d_each
    f["F3"] = (spawns / n_controls if n_controls else 1.0) <= a["spawn_rate_max"]
    f["F4"] = n_lb > 0 and n_each
    cm = [contrast(row, "M") for _, row in rows]
    ca = [contrast(row, "ABL") for _, row in rows]
    gap = statistics.fmean(e for e, _ in cm) - statistics.fmean(e for e, _ in ca)
    se = math.sqrt(sum(v for _, v in cm) + sum(v for _, v in ca)) / len(rows)
    f["F5"] = gap - Z * se > 0
    f["all"] = all(f.values())
    f["d_est"] = d_est
    return f


def power(cells: list[CellInput], alloc: dict, a: dict, n_sim: int, seed: int, variant: str = "presentation",
          n_controls: int = 0) -> dict:
    rng = random.Random(seed)
    runs = [simulate_once(rng, cells, alloc, a, variant, n_controls) for _ in range(n_sim)]
    out = {k: sum(r[k] for r in runs) / n_sim for k in ("F1", "F2", "F3", "F4", "F5", "all")}
    out["mc_se"] = math.sqrt(out["all"] * (1 - out["all"]) / n_sim)
    out["mean_d_est"] = statistics.fmean(r["d_est"] for r in runs)
    return out


def total_runs(n_cells: int, n_control_worlds: int, alloc: dict) -> int:
    per_member = alloc["R_M"] + alloc["R_ABL"] + alloc["R_B"] + alloc["R_N"] + alloc["R_A"]
    return 2 * n_cells * per_member + n_control_worlds * alloc["R_S"]


def choose_allocation(cells: list[CellInput], n_ctl_worlds: int, spec: dict,
                      variant: str = "presentation") -> tuple[dict, list[dict]]:
    """The pre-declared search over the grid in acceptance.json: every allocation within the run ceiling is scored by
    a Monte Carlo with the search seed. Among allocations whose search power reaches min_power, the one with the most
    control replication, then the fewest runs, wins; if none does, the highest power wins (then the fewest runs)."""
    a, s = spec["primary"], spec["search"]
    tried = []
    for r_m in s["R_M"]:
        for r_b in s["R_B"]:
            for r_abl in s["R_ABL"]:
                for r_s in s["R_S"]:
                    alloc = {"R_M": r_m, "R_B": r_b, "R_N": r_b, "R_ABL": r_abl, "R_A": spec["R_A"], "R_S": r_s}
                    n = total_runs(len(cells), n_ctl_worlds, alloc)
                    if n > spec["max_runs"]:
                        continue
                    p = power(cells, alloc, a, s["n_sim"], spec["seed"], variant, n_ctl_worlds * r_s)
                    tried.append({**alloc, "runs": n, "power": p["all"], "mc_se": p["mc_se"]})
    if not tried:
        return {}, tried
    enough = [t for t in tried if t["power"] >= spec["min_power"]]
    best = (max(enough, key=lambda t: (t["R_S"], -t["runs"], t["power"])) if enough
            else max(tried, key=lambda t: (t["power"], -t["runs"])))
    return {k: best[k] for k in ("R_M", "R_B", "R_N", "R_ABL", "R_A", "R_S")}, tried


SENSITIVITY = {
    "pi": [0.6, 0.7, 0.8, 0.9, 1.0], "sigma": [0.02, 0.05, 0.08, 0.12],
    "p_fail (B and N only)": [0.0, 0.02, 0.05, 0.12], "p_fail_M (M and ABL only)": [0.0, 0.02, 0.04, 0.06, 0.12],
    "p_fail and p_fail_M together": [0.0, 0.02, 0.05, 0.12], "rho": [0.0, 0.5, 0.9],
    "logit_sd": [0.0, 0.5, 1.0, 2.0, 3.0], "tau_sim": [0.0, 0.02, 0.05], "eta": [0.0, 0.01, 0.02, 0.04, 0.08],
    "s_ctl": [0.05, 0.10, 0.20], "q_default": [0.0, 0.5, 1.0],
}


def _set(a: dict, key: str, v) -> dict:
    if key == "p_fail and p_fail_M together":
        return {**a, "p_fail": v, "p_fail_M": v}
    return {**a, key.split(" ")[0]: v}


def scale_effects(cells: list[CellInput], k: float) -> list[CellInput]:
    return [replace(c, a={m: c.b[m] + k * (c.a[m] - c.b[m]) for m in c.a}) for c in cells]


def with_checkpoint_tokens(cells: list[CellInput], out_tokens: int, constants, spec_cost: dict) -> list[CellInput]:
    return [replace(c, ck_eta=checkpoint_eta(constants.regimes[c.regime], constants, spec_cost, out_tokens))
            for c in cells]


def _variant(cells, n_ctl_worlds, spec, constants, variant, grid_min_cells, full: bool) -> dict:
    alloc, tried = choose_allocation(cells, n_ctl_worlds, spec, variant)
    if not alloc:
        return {"pass": False, "reason": "no allocation fits the run ceiling", "tried": len(tried)}
    a, fin = spec["primary"], spec["final"]
    nc = n_ctl_worlds * alloc["R_S"]
    seed = spec["seed"] + 1

    def pw(cs, assume, n=fin["sens_n_sim"]):
        return power(cs, alloc, assume, n, seed, variant, nc)
    primary = pw(cells, a, fin["n_sim"])
    pess = dict(spec["pessimistic"])
    out = {"pass": primary["all"] >= spec["min_power"], "allocation": alloc,
           "runs": total_runs(len(cells), n_ctl_worlds, alloc), "primary": primary,
           "allocation_search_size": len(tried),
           "allocation_search_top": sorted(tried, key=lambda t: -t["power"])[:10],
           "pessimistic_joint": pw(scale_effects(cells, 0.8), {**a, **pess}),
           "pessimistic_one_at_a_time": {f"{k}={v}": pw(cells, {**a, k: v})["all"] for k, v in pess.items()}}
    out["pessimistic_one_at_a_time"]["effects_x0.8"] = pw(scale_effects(cells, 0.8), a)["all"]
    if grid_min_cells:
        out["pessimistic_one_at_a_time"]["grid_minimum_effects"] = pw(grid_min_cells, a)["all"]
    if variant == "deliberation":
        out["checkpoint_output_tokens"] = {
            str(t): pw(with_checkpoint_tokens(cells, t, constants, spec["cost"]), a)["all"]
            for t in spec["cost"]["checkpoint_output_tokens_sensitivity"]}
        out["checkpoints_per_run"] = {c.key: c.checkpoints for c in cells}
    if full:
        out["sensitivity"] = {k: {str(v): pw(cells, _set(a, k, v))["all"] for v in values}
                              for k, values in SENSITIVITY.items()}
        out["pi_sigma_grid"] = {f"pi={p},sigma={s}": pw(cells, {**a, "pi": p, "sigma": s})["all"]
                                for p in SENSITIVITY["pi"] for s in SENSITIVITY["sigma"]}
        out["effect_scale"] = {str(k): pw(scale_effects(cells, k), a)["all"] for k in (0.5, 0.8, 1.0, 1.5, 2.0, 3.0)}
        null = pw(cells, {**a, "pi": 0.0, "q_default": 0.0, "tau_sim": 0.0, "eta": 0.0}, fin["n_sim"])
        out["size_under_null"] = {k: null[k] for k in ("F2", "F4", "all")}
    return out


def feasibility(cells: list[CellInput], n_ctl_worlds: int, spec: dict, constants, grid_min_cells=None) -> dict:
    """Everything §7 reports. G9 needs both mechanisms powered at the primary assumptions, each at its own best
    allocation: the deliberation mechanism (high-effort checkpoints, as postmortem §8 requires) and the presentation
    mechanism (the other follow-up stage B can select)."""
    if not cells:
        return {"pass": False, "reason": "no qualifying cell"}
    pres = _variant(cells, n_ctl_worlds, spec, constants, "presentation", grid_min_cells, True)
    delib = _variant(cells, n_ctl_worlds, spec, constants, "deliberation", grid_min_cells, False)
    ok = bool(pres.get("pass")) and bool(delib.get("pass"))
    return {"pass": ok, "reason": None if ok else "below min_power: " + ", ".join(
                v for v, r in (("presentation", pres), ("deliberation", delib)) if not r.get("pass")),
            "control_worlds": n_ctl_worlds, "presentation": pres, "deliberation": delib,
            "cost": {"presentation": cost_estimate(cells, pres["allocation"], n_ctl_worlds, spec["cost"], constants,
                                                   "presentation") if pres.get("allocation") else None,
                     "deliberation": cost_estimate(cells, delib["allocation"], n_ctl_worlds, spec["cost"], constants,
                                                   "deliberation") if delib.get("allocation") else None},
            "effects": {c.key: {"oracle_minus_baseline": statistics.fmean(c.a[m] - c.b[m] for m in c.a),
                                "oracle_minus_default": statistics.fmean(c.a[m] - c.d[m] for m in c.a),
                                "checkpoint_eta": c.ck_eta, "checkpoints": c.checkpoints,
                                "a": c.a, "b": c.b, "d": c.d, "r": c.r,
                                "labels": {"oracle": c.a_label, "baseline": c.b_label, "default": c.d_label,
                                           "router": c.r_label}}
                        for c in cells}}


def cost_estimate(cells: list[CellInput], alloc: dict, n_ctl_worlds: int, assume: dict, constants,
                  variant: str) -> dict:
    """API calls, list-price spend and sequential wall time for the follow-up (simulated tokens at the base point;
    the deliberation mechanism adds its checkpoints, counted on the oracle's plans, to every M, ABL and control run)."""
    def mean(arm, k):
        return statistics.fmean(c.costs[arm][m][k] for c in cells for m in c.costs[arm])
    n_i = 2 * len(cells)
    runs = {"M": n_i * alloc["R_M"], "ABL": n_i * alloc["R_ABL"], "B": n_i * alloc["R_B"], "N": n_i * alloc["R_N"],
            "A": n_i * alloc["R_A"], "controls": n_ctl_worlds * alloc["R_S"]}
    per_run = {"M": (mean("M", "calls"), mean("M", "api_usd")), "A": (mean("M", "calls"), mean("M", "api_usd")),
               "B": (mean("B", "calls"), mean("B", "api_usd")), "N": (mean("B", "calls"), mean("B", "api_usd")),
               "ABL": (mean("D", "calls"), mean("D", "api_usd")), "controls": (mean("D", "calls"), mean("D", "api_usd"))}
    c = constants.compute
    ck = statistics.fmean(x.checkpoints["a"][m] for x in cells for m in x.a) if variant == "deliberation" else 0.0
    ck_usd = (assume["checkpoint_output_tokens"] * c.price_out + assume["checkpoint_input_tokens"] * c.price_in) / 1e6
    llm_runs = runs["M"] + runs["ABL"] + runs["controls"]
    calls = sum(runs[k] * per_run[k][0] for k in runs) + ck * llm_runs
    usd = sum(runs[k] * per_run[k][1] for k in runs) + ck * ck_usd * llm_runs
    wall = sum(runs[k] * per_run[k][0] for k in runs) * assume["wall_s_per_call"] + ck * assume["checkpoint_wall_s"] * llm_runs
    return {"api_calls": round(calls), "api_usd": round(usd, 2), "sequential_wall_hours": round(wall / 3600, 1),
            "checkpoints_per_llm_run": ck, "runs": runs, "per_run_calls_and_usd": per_run, "assumptions": assume}
