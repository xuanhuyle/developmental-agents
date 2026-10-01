"""Gate-0 follow-up feasibility (GATE_0_SPEC.md §7): a pre-declared follow-up design within the run ceiling, its cost,
and the Monte-Carlo power of its primary analysis.

Nothing here is evidence about any LLM. No policy has ever adapted in this environment, so its behaviour and variance
are unknown: every number below is *conditional* on declared assumptions (acceptance.json "power.primary"), and the
sensitivity tables show how the conclusion moves with them.

Generative model, per qualifying cell c (a reveal set, both members) and run:
- the mechanism arm M picks the adaptive oracle's plan for that member with probability pi_c, otherwise the cell's
  best precommitted baseline plan B; logit(pi_c) = logit(pi) + s*(sqrt(rho)*z_template + sqrt(1-rho)*z_cell);
- a run's cost-fitness (fitness with quality fixed at 1) is the simulated base-point value of the chosen plan, plus
  N(0, sigma^2) noise; M's runs also carry a cell bias N(0, tau_sim^2) (simulator-to-live discrepancy) and a fixed
  organizational overhead eta; every run answers wrongly with probability p_fail;
- the baseline arm B and the no-LLM-controller arm N run plan B (N is modelled exactly like B: conservative);
- on control worlds (the relaxed twins), M spawns with probability s_ctl.

Analysis (all must pass): F1 adaptation contrast >= 0.30 with a two-level bootstrap lower bound > 0; F2 cost-fitness
M - B on correct runs, two-level bootstrap 95% lower bound > 0; F2a accuracy M - B, Agresti-Caffo lower bound > -margin; F3
spawn rate on controls <= 0.20; F4 as F2 against N. The two-level bootstrap resamples cells exactly and approximates
the within-cell resampled means by normal draws with the cell's sample variance (stated in the report).
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

from devagents.gate0.evaluate import View, instantiate
from devagents.gate0.plans import parse_plan


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


@dataclass
class CellInput:
    key: str
    template: str
    a: dict  # member -> base cost-fitness of the adaptive oracle's plan
    b: dict  # member -> base cost-fitness of the best precommitted baseline's plan
    a_label: dict  # member -> 1 if the oracle's plan reorganizes in member X's direction after the reveal
    b_label: dict
    x_member: str
    costs: dict  # arm -> member -> {"calls", "api_usd", "critical_calls"}


def _label(template: str, sig: list) -> int:
    """Post-reveal reorganization in the X direction: A divides after the reveal, B dissolves running work."""
    return int(sig[1] > 0) if template == "A" else int(sig[2] > 0)


def followup_inputs(recs: dict, view: View, qualifying: list[str], constants) -> list[CellInput]:
    out = []
    price_in, price_out = constants.compute.price_in, constants.compute.price_out
    for key in qualifying:
        cell = tuple(key.split("|"))
        r = view.cell(cell)
        ms = view.members(cell)
        inst = view.by_id[cell[0]]
        w_plans = {m: instantiate(view.w_star, inst, view._member(cell[0], m), view.k_max) for m in ms}
        rt_mean = r["rt"]
        w_mean = statistics.fmean(view.f((*cell, m), w_plans[m]) for m in ms)
        b_plans = {m: r["rt_plan"] for m in ms} if rt_mean >= w_mean else w_plans
        rec = lambda m, p: recs[(cell[0], cell[1], m, p, view.cond)]  # noqa: E731

        def cost(m, p):
            x = rec(m, p)
            return {"calls": x["llm_calls"], "api_usd": (x["in_tokens"] * price_in + x["out_tokens"] * price_out) / 1e6,
                    "critical_calls": x["root_calls"] + x["max_child_calls"], "elapsed_s": x["elapsed_s"]}
        out.append(CellInput(
            key, inst.template,
            {m: view.f((*cell, m), r["astar_plans"][m]) for m in ms}, {m: view.f((*cell, m), b_plans[m]) for m in ms},
            {m: _label(inst.template, rec(m, r["astar_plans"][m])["signature"]) for m in ms},
            {m: _label(inst.template, rec(m, b_plans[m])["signature"]) for m in ms}, "X",
            {"M_oracle_plan": {m: cost(m, r["astar_plans"][m]) for m in ms},
             "B": {m: cost(m, b_plans[m]) for m in ms}}))
    return out


# --------------------------------------------------------------------------- one simulated follow-up


def _pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    i = q * (len(xs) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def _summ(vals: list[float]) -> tuple[int, float, float]:
    n = len(vals)
    if n == 0:
        return 0, 0.0, 0.0
    m = sum(vals) / n
    v = sum((x - m) ** 2 for x in vals) / n if n > 1 else 0.0  # plug-in variance, as the bootstrap uses
    return n, m, v


def simulate_once(rng: random.Random, cells: list[CellInput], alloc: dict, a: dict, n_boot: int,
                  raw_fitness: bool = False) -> dict:
    templates = sorted({c.template for c in cells})
    z_t = {t: rng.gauss(0, 1) for t in templates}
    per_cell = []
    acc_m = [0, 0]
    acc_b = [0, 0]
    for c in cells:
        lp = _logit(a["pi"]) + a["logit_sd"] * (math.sqrt(a["rho"]) * z_t[c.template]
                                                + math.sqrt(1 - a["rho"]) * rng.gauss(0, 1))
        pi_c = _sigmoid(lp) if 0 < a["pi"] < 1 else a["pi"]
        bias = rng.gauss(0, a["tau_sim"]) if a["tau_sim"] > 0 else 0.0
        stats = {}
        for m in c.a:
            arms = {}
            for arm, n in (("M", alloc["R_M"]), ("B", alloc["R_B"]), ("N", alloc["R_N"])):
                vals, labels, correct = [], [], 0
                for _ in range(n):
                    if arm == "M":
                        pick = rng.random() < pi_c
                        base = c.a[m] if pick else c.b[m]
                        labels.append(c.a_label[m] if pick else c.b_label[m])
                        base += bias - a["eta"]
                    else:
                        base = c.b[m]
                    ok = rng.random() >= a["p_fail"]
                    v = base + rng.gauss(0, a["sigma"])
                    if raw_fitness:
                        vals.append(v if ok else v - 1.0)
                    elif ok:
                        vals.append(v)
                    correct += ok
                    if arm == "M":
                        acc_m[0] += ok
                        acc_m[1] += 1
                    elif arm == "B":
                        acc_b[0] += ok
                        acc_b[1] += 1
                arms[arm] = (_summ(vals), labels)
            stats[m] = arms
        per_cell.append(stats)
    n_ctl = alloc["R_S"] * 2 * len(cells)
    spawns = sum(rng.random() < a["s_ctl"] for _ in range(n_ctl))

    def boot(stat_fn) -> tuple[float, float]:
        point = statistics.fmean(stat_fn(s, None) for s in per_cell)
        draws = []
        for _ in range(n_boot):
            idx = [rng.randrange(len(per_cell)) for _ in per_cell]
            draws.append(statistics.fmean(stat_fn(per_cell[i], rng) for i in idx))
        return point, _pct(draws, 0.025)

    def resampled_mean(summ, r):
        n, mean, var = summ
        if r is None or n < 2:
            return mean
        return r.gauss(mean, math.sqrt(var / n))

    def diff(arm):
        def fn(s, r):
            ds = [resampled_mean(s[m]["M"][0], r) - resampled_mean(s[m][arm][0], r)
                  for m in s if s[m]["M"][0][0] and s[m][arm][0][0]]
            return statistics.fmean(ds) if ds else 0.0
        return fn

    def contrast(s, r):
        ps = {}
        for m in s:
            labels = s[m]["M"][1]
            p = sum(labels) / len(labels) if labels else 0.0
            if r is not None and labels:
                p = min(1.0, max(0.0, r.gauss(p, math.sqrt(max(p * (1 - p), 0.0) / len(labels)))))
            ps[m] = p
        others = [m for m in s if m != "X"]
        return ps["X"] - statistics.fmean(ps[m] for m in others)

    c_point, c_lb = boot(contrast)
    d_point, d_lb = boot(diff("B"))
    n_point, n_lb = boot(diff("N"))
    # Agresti-Caffo interval for the accuracy difference (one pseudo-success and one pseudo-failure per arm): the plain
    # Wald interval collapses when an arm makes no error.
    pm, pb = (acc_m[0] + 1) / (acc_m[1] + 2), (acc_b[0] + 1) / (acc_b[1] + 2)
    se = math.sqrt(pm * (1 - pm) / (acc_m[1] + 2) + pb * (1 - pb) / (acc_b[1] + 2))
    f = {"F1": c_point >= a["contrast_min"] and c_lb > 0, "F2": d_lb > 0,
         "F2a": (pm - pb) - 1.96 * se > -a["accuracy_margin"], "F3": spawns / max(1, n_ctl) <= a["spawn_rate_max"],
         "F4": n_lb > 0}
    f["all"] = all(f.values())
    f["d_point"], f["d_lb"] = d_point, d_lb
    return f


def power(cells: list[CellInput], alloc: dict, a: dict, n_sim: int, n_boot: int, seed: int,
          raw_fitness: bool = False) -> dict:
    rng = random.Random(seed)
    runs = [simulate_once(rng, cells, alloc, a, n_boot, raw_fitness) for _ in range(n_sim)]
    out = {k: sum(r[k] for r in runs) / n_sim for k in ("F1", "F2", "F2a", "F3", "F4", "all")}
    out["mean_d_point"] = statistics.fmean(r["d_point"] for r in runs)
    return out


def total_runs(n_cells: int, alloc: dict) -> int:
    return 2 * n_cells * (alloc["R_M"] + alloc["R_B"] + alloc["R_N"] + alloc["R_A"]) + 2 * n_cells * alloc["R_S"]


def choose_allocation(cells: list[CellInput], spec: dict) -> tuple[dict, list[dict]]:
    """The pre-declared search: every (R_M, R_B = R_N, R_S) on the grid that fits the run ceiling, scored by a fast
    Monte Carlo; the highest power wins (ties: fewer runs)."""
    a = spec["primary"]
    tried = []
    for r_m in spec["search"]["R_M"]:
        for r_b in spec["search"]["R_B"]:
            for r_s in spec["search"]["R_S"]:
                alloc = {"R_M": r_m, "R_B": r_b, "R_N": r_b, "R_A": spec["R_A"], "R_S": r_s}
                n = total_runs(len(cells), alloc)
                if n > spec["max_runs"]:
                    continue
                p = power(cells, alloc, a, spec["search"]["n_sim"], spec["search"]["n_boot"], spec["seed"])
                tried.append({**alloc, "runs": n, "power": p["all"]})
    if not tried:
        return {}, tried
    best = max(tried, key=lambda t: (t["power"], -t["runs"]))
    return {k: best[k] for k in ("R_M", "R_B", "R_N", "R_A", "R_S")}, tried


SENSITIVITY = {
    "pi": [0.6, 0.7, 0.8, 0.9, 1.0], "sigma": [0.02, 0.05, 0.08, 0.12], "p_fail": [0.0, 0.02, 0.05, 0.10],
    "rho": [0.0, 0.5, 0.9], "logit_sd": [0.0, 0.5, 1.0], "tau_sim": [0.0, 0.02, 0.05], "eta": [0.0, 0.01, 0.02, 0.04],
    "s_ctl": [0.05, 0.10, 0.20],
}


def feasibility(cells: list[CellInput], spec: dict, constants) -> dict:
    """Everything §7 reports: allocation, power at the primary assumptions, sensitivity, size, cost and runtime."""
    if not cells:
        return {"pass": False, "reason": "no qualifying cell"}
    alloc, tried = choose_allocation(cells, spec)
    if not alloc:
        return {"pass": False, "reason": "no allocation fits the run ceiling", "tried": tried}
    a, fin = spec["primary"], spec["final"]
    primary = power(cells, alloc, a, fin["n_sim"], fin["n_boot"], spec["seed"])
    sens = {}
    for k, values in SENSITIVITY.items():
        sens[k] = {str(v): power(cells, alloc, {**a, k: v}, fin["sens_n_sim"], fin["n_boot"], spec["seed"])["all"]
                   for v in values}
    grid2 = {f"pi={p},sigma={s}": power(cells, alloc, {**a, "pi": p, "sigma": s}, fin["sens_n_sim"], fin["n_boot"],
                                        spec["seed"])["all"]
             for p in SENSITIVITY["pi"] for s in SENSITIVITY["sigma"]}
    null = power(cells, alloc, {**a, "pi": 0.0, "tau_sim": 0.0, "eta": 0.0}, fin["n_sim"], fin["n_boot"], spec["seed"])
    raw = power(cells, alloc, a, fin["sens_n_sim"], fin["n_boot"], spec["seed"], raw_fitness=True)
    return {"pass": primary["all"] >= spec["min_power"], "allocation": alloc, "runs": total_runs(len(cells), alloc),
            "primary": primary, "allocation_search": tried, "sensitivity": sens, "pi_sigma_grid": grid2,
            "size_F2_under_null": null["F2"], "raw_fitness_F2_power": raw["F2"], "raw_fitness_all": raw["all"],
            "cost": cost_estimate(cells, alloc, spec["cost"]),
            "effects": {c.key: {"mean_oracle_minus_baseline": statistics.fmean(c.a[m] - c.b[m] for m in c.a),
                                "a": c.a, "b": c.b, "labels": {"oracle": c.a_label, "baseline": c.b_label}}
                        for c in cells}}


def cost_estimate(cells: list[CellInput], alloc: dict, assume: dict) -> dict:
    """API calls, list-price API spend and wall time for the follow-up (simulated tokens at the base point)."""
    def per(arm, f):
        return statistics.fmean(f(c.costs[arm][m]) for c in cells for m in c.costs[arm])
    m_calls, b_calls = per("M_oracle_plan", lambda x: x["calls"]), per("B", lambda x: x["calls"])
    m_usd, b_usd = per("M_oracle_plan", lambda x: x["api_usd"]), per("B", lambda x: x["api_usd"])
    m_crit, b_crit = per("M_oracle_plan", lambda x: x["critical_calls"]), per("B", lambda x: x["critical_calls"])
    n_i = 2 * len(cells)
    runs = {"M": n_i * alloc["R_M"], "B": n_i * alloc["R_B"], "N": n_i * alloc["R_N"], "A": n_i * alloc["R_A"],
            "M_controls": n_i * alloc["R_S"]}
    k, extra_tok, wall, extra_wall = (assume["checkpoints"], assume["checkpoint_output_tokens"],
                                      assume["wall_s_per_call"], assume["checkpoint_wall_s"])
    out = {}
    for variant, (dk, dt, dw) in {"presentation": (0, 0, 0), "deliberation": (k, k * extra_tok, k * extra_wall)}.items():
        m_cost = m_usd + dt * 20e-6
        calls = (runs["M"] + runs["M_controls"]) * (m_calls + dk) + (runs["B"] + runs["N"] + runs["A"]) * b_calls
        usd = (runs["M"] + runs["M_controls"]) * m_cost + (runs["B"] + runs["N"] + runs["A"]) * b_usd
        wall_s = ((runs["M"] + runs["M_controls"]) * (m_crit * wall + dw)
                  + (runs["B"] + runs["N"] + runs["A"]) * b_crit * wall)
        out[variant] = {"api_calls": round(calls), "api_usd": round(usd, 2), "sequential_wall_hours": round(wall_s / 3600, 1)}
    out["per_run"] = {"M_calls": m_calls, "B_calls": b_calls, "M_api_usd": m_usd, "B_api_usd": b_usd,
                      "M_critical_calls": m_crit, "B_critical_calls": b_crit}
    out["runs"] = runs
    out["assumptions"] = assume
    return out
