"""The §8 evaluator, a pure function over run records, and the §7.3 criteria check (power and specificity).

A run record is a dict with these keys: task_id, task_class, subtype, regime, mode, repeat,
fitness (frozen weights), quality, outcome, spawned, parallel, cap_hits, coordination_usd and
infra_error. `evaluate()` never reads the event logs, so the criteria check can feed it synthetic
records.
"""

from __future__ import annotations

import random
import statistics
from collections import defaultdict

THRESHOLD_COLLAPSE = 0.50
THRESHOLD_CONTRAST = 0.30
N_BOOT = 10_000
BOOT_SEED = 0
ALPHA = 0.05


def cell_key(r: dict) -> str:
    return f"{r['task_id']}|{r['regime']}"


class Runs:
    """Completed (non-infrastructure-error) runs indexed by mode and cell."""

    def __init__(self, records: list[dict], cells: dict):
        self.cells = cells  # frozen calibration cells: key -> {task, task_class, subtype, regime, label, ...}
        self.by = defaultdict(list)
        for r in records:
            if not r.get("infra_error"):
                self.by[(r["mode"], cell_key(r))].append(r)

    def get(self, mode: str, cell: str) -> list[dict]:
        return self.by.get((mode, cell), [])

    def cell_rate(self, mode: str, cell: str, indicator: str) -> float | None:
        runs = self.get(mode, cell)
        return sum(bool(r[indicator]) for r in runs) / len(runs) if runs else None

    def rate(self, cells: set, indicator: str, mode: str = "developmental") -> float | None:
        """Unweighted mean over (class, regime) strata of the mean cell rate within each stratum."""
        strata = defaultdict(list)
        for c in cells:
            v = self.cell_rate(mode, c, indicator)
            if v is not None:
                strata[(self.cells[c]["task_class"], self.cells[c]["regime"])].append(v)
        if not strata:
            return None
        return statistics.fmean(statistics.fmean(v) for v in strata.values())


def metric_value(r: dict, metric: str) -> float:
    """fitness; neg_cost = -(quality - fitness), the negated penalty terms; quality."""
    if metric == "neg_cost":
        return r["fitness"] - r["quality"]
    return r[metric]


def contrast_ci(runs: Runs, cells: set, comparator: str, metric: str = "fitness", n_boot: int = N_BOOT,
                seed: int = BOOT_SEED) -> dict:
    """θ = mean over classes of the mean over tasks of d_task, where d_task is the mean over the task's cells of
    (mean developmental metric - mean comparator metric). The CI comes from a two-level percentile bootstrap:
    tasks are resampled within classes, then runs within each (cell, mode). The two levels make it conservative."""
    tasks = defaultdict(lambda: defaultdict(list))  # class -> task -> [(dev values, comparator values)]
    for c in cells:
        dev = [metric_value(r, metric) for r in runs.get("developmental", c)]
        comp = [metric_value(r, metric) for r in runs.get(comparator, c)]
        if dev and comp:
            meta = runs.cells[c]
            tasks[meta["task_class"]][meta["task"]].append((dev, comp))
    if not tasks:
        return {"theta": None, "lo": None, "hi": None, "n_tasks": 0}

    def theta(sample_cell) -> float:
        class_means = []
        for cls, per_task in tasks.items():
            d_tasks = [statistics.fmean(sample_cell(d) - sample_cell(k) for d, k in pairs) for pairs in per_task.values()]
            class_means.append(statistics.fmean(d_tasks))
        return statistics.fmean(class_means)

    point = theta(statistics.fmean)
    rng = random.Random(seed)
    boots = []
    task_lists = {cls: list(per_task.values()) for cls, per_task in tasks.items()}
    for _ in range(n_boot):
        class_means = []
        for cls, lists in task_lists.items():
            picked = rng.choices(lists, k=len(lists))
            d_tasks = []
            for pairs in picked:
                diffs = []
                for d, k in pairs:
                    diffs.append(statistics.fmean(rng.choices(d, k=len(d))) - statistics.fmean(rng.choices(k, k=len(k))))
                d_tasks.append(statistics.fmean(diffs))
            class_means.append(statistics.fmean(d_tasks))
        boots.append(statistics.fmean(class_means))
    boots.sort()
    lo = boots[int(ALPHA / 2 * n_boot)]
    hi = boots[min(n_boot - 1, int((1 - ALPHA / 2) * n_boot))]
    return {"theta": point, "lo": lo, "hi": hi, "n_tasks": sum(len(v) for v in tasks.values())}


def evaluate(records: list[dict], cells: dict, sets: dict, n_boot: int = N_BOOT, short_circuit: bool = False) -> dict:
    """Evaluate the §8 criteria. `sets` maps S, P, S_urgent, P_urgent, S_relaxed, P_relaxed, twin and D_urgent to
    lists of cell keys. With short_circuit=True, the bootstrap criteria are skipped once any cheaper criterion
    fires (the criteria check uses this)."""
    runs = Runs(records, cells)
    S, P = set(sets["S"]), set(sets["P"])
    crit = {}

    v = runs.rate(S, "spawned")
    crit["1_always_spawn"] = {"fires": v is None or v > THRESHOLD_COLLAPSE, "spawned_rate_S": v}
    v = runs.rate(P, "parallel")
    crit["2_never_spawn"] = {"fires": v is None or v < THRESHOLD_COLLAPSE, "parallel_rate_P": v}

    contrasts = {}
    for regime in ("urgent", "relaxed"):
        p_r, s_r = set(sets[f"P_{regime}"]), set(sets[f"S_{regime}"])
        if p_r and s_r:
            a, b = runs.rate(p_r, "parallel"), runs.rate(s_r, "spawned")
            contrasts[regime] = None if a is None or b is None else a - b
    crit["3a_within_regime"] = {"fires": not contrasts or any(v is None or v < THRESHOLD_CONTRAST for v in contrasts.values()),
                                "contrasts": contrasts}
    twin = set(sets["twin"])
    a = runs.rate({c for c in twin if c.endswith("|urgent")}, "parallel")
    b = runs.rate({c for c in twin if c.endswith("|relaxed")}, "spawned")
    crit["3b_twin"] = {"fires": a is None or b is None or a - b < THRESHOLD_CONTRAST,
                       "contrast": None if a is None or b is None else a - b}
    a, b = runs.rate(set(sets["P_urgent"]), "parallel"), runs.rate(set(sets["D_urgent"]), "spawned")
    crit["3c_dissociation"] = {"fires": a is None or b is None or a - b < THRESHOLD_CONTRAST,
                               "contrast": None if a is None or b is None else a - b}

    cheap_fired = any(c["fires"] for c in crit.values())
    if short_circuit and cheap_fired:
        return {"criteria": crit, "verdict": "not supported", "fired": [k for k, c in crit.items() if c["fires"]]}

    # Criteria 4 and 5 test the frontier components separately: cost (the penalty terms of fitness) and quality.
    #   4a: a cost gain over single where division pays (P);
    #   4b: no significant quality loss against single;
    #   4c: no significant cost loss against single where division does not pay.
    #   5:  a fixed central decomposition matches developmental where the designs differ (S, where fixed division is
    #       overhead): developmental is not significantly better on cost, and not significantly better on quality.
    def ci(cells_, comparator, metric):
        return contrast_ci(runs, set(cells_), comparator, metric, n_boot)

    def fired_so_far():
        return short_circuit and any(c["fires"] for c in crit.values())

    c = ci(P, "single", "neg_cost")
    crit["4a_no_cost_gain_vs_single_on_P"] = {"fires": c["theta"] is None or c["theta"] <= 0 or c["lo"] <= 0, **c}
    if not fired_so_far():
        c = ci(cells, "single", "quality")
        crit["4b_quality_loss_vs_single"] = {"fires": c["theta"] is None or c["hi"] < 0, **c}
    if not fired_so_far():
        c = ci(set(cells) - P, "single", "neg_cost")
        crit["4c_cost_loss_vs_single_elsewhere"] = {"fires": c["theta"] is None or c["hi"] < 0, **c}
    if not fired_so_far():
        cost, qual = ci(S, "central", "neg_cost"), ci(S, "central", "quality")
        matched = (cost["theta"] is None or cost["lo"] <= 0) and (qual["theta"] is None or qual["lo"] <= 0)
        crit["5_central_matches_on_S"] = {"fires": matched, "cost": cost, "quality": qual}
    fired = [k for k, c in crit.items() if c["fires"]]
    return {"criteria": crit, "verdict": "not supported" if fired else "supported", "fired": fired}


def secondary_router(records: list[dict], cells: dict, sets: dict, n_boot: int = N_BOOT) -> dict:
    """H2 (pre-registered, secondary): developmental − router on fitness, cost and quality, over all cells and over
    the I cells. It is reported, and it never changes the §8 verdict (SPEC §8, §10)."""
    runs = Runs(records, cells)
    metrics = ("fitness", "neg_cost", "quality")
    i_cells = set(sets.get("I", [])) & set(cells)
    return {"all": {m: contrast_ci(runs, set(cells), "router", m, n_boot) for m in metrics},
            "I": {m: contrast_ci(runs, i_cells, "router", m, n_boot) for m in metrics}}


def validity(records: list[dict], cells: dict, planned_per_mode: dict[str, int], repeats: int,
             audit_ok: bool, frozen_ok: bool) -> dict:
    """SPEC §8 validity conditions (i)–(vi). If any fails, the run is uninformative."""
    runs = Runs(records, cells)
    out = {"i_frozen_gate": frozen_ok, "iii_audit_parity": audit_ok}
    acc = {}
    for cls in sorted({c["task_class"] for c in cells.values()}):
        rs = [r for k in cells if cells[k]["task_class"] == cls for r in runs.get("single", k)]
        acc[cls] = statistics.fmean(r["quality"] for r in rs) if rs else None
    out["ii_single_accuracy"] = all(v is not None and v >= 0.75 for v in acc.values())
    out["ii_detail"] = acc
    completion, min_cell = {}, {}
    for mode, planned in planned_per_mode.items():
        done = sum(len(runs.get(mode, k)) for k in cells)
        completion[mode] = done / planned if planned else 0.0
        min_cell[mode] = min((len(runs.get(mode, k)) for k in cells), default=0)
    out["iv_completion"] = all(v >= 0.9 for v in completion.values()) and all(v >= repeats - 1 for v in min_cell.values())
    out["iv_detail"] = {"completion": completion, "min_runs_per_cell": min_cell}

    def mean_fit(mode, pred):
        rs = [r for k, c in cells.items() if pred(c) for r in runs.get(mode, k)]
        return statistics.fmean(r["fitness"] for r in rs) if rs else None

    b_u = lambda c: c["task_class"] == "parallel" and c["regime"] == "urgent"
    b_r = lambda c: c["task_class"] == "parallel" and c["regime"] == "relaxed"
    a_all = lambda c: c["task_class"] == "solo"
    m = {k: (mean_fit("central", f), mean_fit("single", f)) for k, f in (("B_urgent", b_u), ("B_relaxed", b_r), ("A", a_all))}
    ok = (None not in m["B_urgent"] and m["B_urgent"][0] > m["B_urgent"][1]
          and None not in m["B_relaxed"] and m["B_relaxed"][0] < m["B_relaxed"][1]
          and None not in m["A"] and m["A"][1] >= m["A"][0])
    out["v_manipulation_check"] = ok
    out["v_detail"] = {k: {"central": v[0], "single": v[1]} for k, v in m.items()}
    caps = {}
    for cls in sorted({c["task_class"] for c in cells.values()}):
        rs = [r for k in cells if cells[k]["task_class"] == cls for r in runs.get("single", k)]
        caps[cls] = sum(r["cap_hits"] > 0 for r in rs) / len(rs) if rs else None
    out["vi_single_caps"] = all(v is not None and v <= 0.05 for v in caps.values())
    out["vi_detail"] = caps
    out["valid"] = all(out[k] for k in ("i_frozen_gate", "ii_single_accuracy", "iii_audit_parity", "iv_completion",
                                         "v_manipulation_check", "vi_single_caps"))
    return out


# --------------------------------------------------------------------------- criteria check (SPEC §7.3)

def _synthetic_policies(cells: dict, tasks_max_docs: dict[str, int]) -> dict:
    """Organization choice for the developmental mode: a cell -> "solo" | "div". RANDOM is re-drawn per run."""
    def ideal(c, rng):
        return "div" if c["div_fitness"] > c["solo_fitness"] else "solo"
    return {
        "IDEAL": ideal,
        "NEVER": lambda c, rng: "solo",
        "ALWAYS": lambda c, rng: "div",
        "RANDOM": lambda c, rng: "div" if rng.random() < 0.5 else "solo",
        "SPAWN_IFF_URGENT": lambda c, rng: "div" if c["regime"] == "urgent" else "solo",
        "SPAWN_IFF_MULTIDOC": lambda c, rng: "div" if tasks_max_docs[c["task"]] >= 4 else "solo",
        # organizes correctly but wastes as much as a fixed decomposition where division does not pay (targets 4c, 5)
        "WASTEFUL": lambda c, rng: "div" if c["div_fitness"] > c["solo_fitness"] else "wasteful",
    }


def synthetic_records(cells: dict, dev_policy, repeats: int, accuracy: dict[str, float], rng: random.Random,
                      cost_cv: float = 0.25) -> list[dict]:
    """One synthetic run set. For each run, quality ~ Bernoulli(accuracy of the class) and
    fitness = quality - cost_org × N(1, cost_cv), where cost_org = 1 - calibrated fitness of the organization.
    single always stays solo, central uses the best division reachable before looking, and router uses the better
    of solo and that division."""
    out = []
    for key, c in cells.items():
        for mode in ("developmental", "single", "central", "router"):
            for rep in range(repeats):
                org = {"developmental": dev_policy(c, rng), "single": "solo", "central": "router_div",
                       "router": "router_div" if c["router_div_fitness"] > c["solo_fitness"] else "solo"}[mode]
                fit = {"solo": c["solo_fitness"], "div": c["div_fitness"], "router_div": c["router_div_fitness"],
                       "wasteful": c["router_div_fitness"]}[org]
                par = {"solo": False, "div": c["div_parallel"], "router_div": c["router_div_parallel"],
                       "wasteful": False}[org]
                q = 1.0 if rng.random() < accuracy[c["task_class"]] else 0.0
                f = q - (1.0 - fit) * max(0.0, rng.gauss(1.0, cost_cv))
                out.append({"task_id": c["task"], "task_class": c["task_class"], "subtype": c["subtype"],
                            "regime": c["regime"], "mode": mode, "repeat": rep, "fitness": f, "quality": q,
                            "outcome": "answered", "spawned": org not in ("solo", "wasteful"), "parallel": par,
                            "cap_hits": 0,
                            "coordination_usd": 0.0, "infra_error": False})
    return out


def criteria_check(cells: dict, sets: dict, tasks_max_docs: dict[str, int], accuracy: dict[str, float] | None = None,
                   cost_cv: float = 0.25, repeats_options=(3, 5, 8, 10), n_sims: int = 200, n_boot: int = 400,
                   seed: int = 0) -> dict:
    """Pick the smallest R such that IDEAL is judged 'supported' in ≥ 80% of simulations and every other synthetic
    policy is judged 'not supported' in ≥ 95%. The evaluator is the real §8 `evaluate`; only n_boot is reduced."""
    accuracy = accuracy or {cls: 0.9 for cls in {c["task_class"] for c in cells.values()}}
    policies = _synthetic_policies(cells, tasks_max_docs)
    table, chosen = {}, None
    for R in repeats_options:
        row = {}
        for name, pol in policies.items():
            rng = random.Random(f"{seed}-{R}-{name}")
            supported = 0
            for _ in range(n_sims):
                res = evaluate(synthetic_records(cells, pol, R, accuracy, rng, cost_cv), cells, sets, n_boot=n_boot,
                               short_circuit=name != "IDEAL")
                supported += res["verdict"] == "supported"
            row[name] = supported / n_sims
        ok = row["IDEAL"] >= 0.80 and all(v <= 0.05 for k, v in row.items() if k != "IDEAL")
        table[R] = {"supported_rate": row, "ok": ok}
        if ok:
            chosen = R
            break
    return {"R": chosen, "table": table, "accuracy": accuracy, "cost_cv": cost_cv, "n_sims": n_sims, "n_boot": n_boot}
