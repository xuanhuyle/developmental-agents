"""Render the Experiment 0b proposal's tables from study.py's outputs (results/exp0b_analysis/*.json). Offline.

    python analysis/exp0b/study.py && python analysis/exp0b/tables.py > results/exp0b_analysis/tables.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "results" / "exp0b_analysis"


def usd(x):
    return f"${x / 1e6:.4f}"


def failure_tables(fa: dict) -> str:
    L = ["### Failing cells at the unrepaired post-pilot calibration (r = 2.0052, 36 reasoning tokens)", "",
         "Money and time are the two cost terms of the fitness, as fractions of V: fitness = quality − money/V − "
         "VoT·elapsed/V. Time is the critical path, so it sums to the elapsed time.", "",
         "| cell | class/subtype | label (pre-pilot design) | gate violated | best solo | solo fit | best division | div fit | "
         "div money/V | div time/V | div agents | div LLM calls | solo money/V | solo time/V |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in fa["rows"]:
        s, d = r["solo"], r["div"]
        money = lambda x: x["money_llm"] + x["money_query"] + x["money_coord"]  # noqa: E731
        time = lambda x: x["time_llm"] + x["time_doc"] + x["time_sql"] + x["time_coord"] + x["time_other"]  # noqa: E731
        L.append(f"| {r['cell']} | {r['class']}/{r['subtype'] or '-'} | {r['label']} ({r['pre_pilot_label']}) | "
                 f"{', '.join(r['violations'])} | {s['org']} | {s['fitness']:.3f} | {d['org']} | {d['fitness']:.3f} | "
                 f"{money(d):.3f} | {time(d):.3f} | {d['agents']} | {d['llm_calls']} | {money(s):.3f} | {time(s):.3f} |")
    L += ["", "### Gate (d): where 1 − fitness comes from (fractions of V; urgent cells)", "",
          "| cell | org | fitness (pre-pilot design) | LLM money | query fees | coordination fees | LLM latency × VoT | "
          "doc latency × VoT | other time × VoT | Δ fitness from the pilot (same constants) | of which LLM money |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in fa["rows"]:
        if not any(v.startswith("d") for v in r["violations"]):
            continue
        for side in ("solo", "div"):
            x, p = r[side], r[side]["pre_pilot_parts"]
            other = x["time_sql"] + x["time_coord"] + x["time_other"]
            parts = ("money_llm", "money_query", "money_coord", "time_llm", "time_doc", "time_sql", "time_coord", "time_other")
            dfit = sum(p[k] for k in parts) - sum(x[k] for k in parts)
            L.append(f"| {r['cell']} | {x['org']} | {x['fitness']:.3f} ({x['pre_pilot_fitness']:.3f}) | {x['money_llm']:.3f} | "
                     f"{x['money_query']:.3f} | {x['money_coord']:.3f} | {x['time_llm']:.3f} | {x['time_doc']:.3f} | "
                     f"{other:.3f} | {dfit:+.3f} | {-(x['money_llm'] - p['money_llm']):+.3f} |")
    L += ["", "### Gate (f): the starved organizations under the fixed allocation rule", "",
          "| cell | org | children | parent balance before SPAWN | spawn fees | available (share × (balance − fees)) | "
          "allocation per child | minimum viable per child | of which actual spend | of which step reserve | shortfall | "
          "starved children |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in fa["starvation"]:
        L.append(f"| {s['cell']} | {s['org']} | {s['children']} | {usd(s['parent_balance_before_spawn'])} | "
                 f"{usd(s['spawn_fees'])} | {usd(s['available_for_children'])} | {usd(s['allocation_per_child'])} | "
                 f"{usd(s['min_viable_allocation'])} | {usd(s['child_spend_unconstrained_max'])} | "
                 f"{usd(s['reserve_component'])} | ${s['shortfall_per_child'] / 1e6:.5f} "
                 f"({s['shortfall_per_child'] / s['min_viable_allocation']:.1%}) | {s['starved_children']}/{s['children']} |")
    L += ["", "What single change would cover the need, everything else at Experiment 0 values:", "",
          "| cell | B needed | share needed | children the rule can fund at share 0.5 | need without the step reserve / allocation |",
          "|---|---|---|---|---|"]
    for s in fa["starvation"]:
        root = s["B"] * 1e6 - s["parent_balance_before_spawn"]
        b_needed = s["children"] * s["min_viable_allocation"] / s["share"] + s["spawn_fees"] + root
        L.append(f"| {s['cell']} | {usd(b_needed)} | {s['share_needed_at_B']:.4f} | {s['k_max_affordable_at_share']} | "
                 f"{s['child_spend_unconstrained_max'] / s['allocation_per_child']:.1%} |")
    p = fa["persistence"]
    L += ["", f"### Persistence over the {p['candidates']} pre-registered mechanical-repair candidates", "",
          "| violation | candidates in which it occurs |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in p["by_cell"].items()]
    mm = fa["money_multiplier"]
    L += ["", "### What the pilot changed, over all 256 base-point oracle organizations (pilot ÷ pre-pilot assumptions)", "",
          "| quantity | min | p10 | median | p90 | max |", "|---|---|---|---|---|---|"]
    for k in ("money_ratio", "solo_money_ratio", "division_money_ratio", "elapsed_ratio"):
        v = mm[k]
        L.append(f"| {k.replace('_', ' ')} | {v['min']:.3f} | {v['p10']:.3f} | {v['median']:.4f} | {v['p90']:.3f} | {v['max']:.3f} |")
    return "\n".join(L)


def candidate_tables(rs: list[dict], ref: dict) -> str:
    L = ["### Every candidate: unrepaired gate and the unchanged pre-registered freeze", "",
         "`steps` = mechanical repair (doc steps, urgent VoT steps, relaxed VoT steps) of the first candidate that passes "
         "the gate and the criteria check.", "",
         "| candidate | family | B | V | VoT × | share | K | unrepaired gate | freeze | steps | R |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rs:
        c, u, f = r["candidate"], r["unrepaired"], r["freeze"]
        st = f.get("steps")
        L.append(f"| {c['name']} | {c['family']} | {c['budget']:g} | {c['value']:g} | {c['vot_scale']:g} | {c['share']:g} | "
                 f"{c['k']} | {'PASS' if u['gate_passed'] else 'fails ' + ','.join(u['gate_kinds'])} | "
                 f"{'frozen' if f['ok'] else 'none'} | "
                 f"{(st['doc_per_token'], st['urgent_vot'], st['relaxed_vot']) if st else '-'} | {f.get('R') or '-'} |")
    rr = ref["criteria_check"]["table"][str(ref["R"])]["supported_rate"]
    L += ["", "### Viable candidates (the freeze succeeds)", "",
          "Reference = the provisional pre-pilot freeze (r = 1), the geometry Experiment 0 was designed to have; its "
          "criteria check is recomputed here at the pilot's accuracy (1.0) like every candidate. Rates are the criteria "
          "check's 'supported' rates at the chosen R (200 simulations each), with the bootstrap's cells in sorted order "
          "(amendment 0b-0), so they do not depend on PYTHONHASHSEED.", "",
          "| candidate | S/P/amb | S_urg | P_urg | twin | D_urg | I | min S margin | min P margin | R | IDEAL | NEVER | ALWAYS | "
          "RANDOM | IFF-URGENT | IFF-MULTIDOC | WASTEFUL | labels = ref | mean abs Δ fitness vs ref |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
          f"| **reference (pre-pilot, r = 1)** | {ref['S']}/{ref['P']}/{ref['ambiguous']} | {ref['|S_urgent|']} | "
          f"{ref['|P_urgent|']} | {ref['|twin|']} | {ref['|D_urgent|']} | {ref['|I|']} | {ref['min_S_margin']:.3f} | "
          f"{ref['min_P_margin']:.3f} | {ref['R']} | {rr['IDEAL']:.3f} | {rr['NEVER']:.3f} | {rr['ALWAYS']:.3f} | "
          f"{rr['RANDOM']:.3f} | {rr['SPAWN_IFF_URGENT']:.3f} | {rr['SPAWN_IFF_MULTIDOC']:.3f} | {rr['WASTEFUL']:.3f} | - | - |"]
    for r in rs:
        f = r.get("frozen")
        if not f:
            continue
        R = r["freeze"]["R"]
        x = f["criteria_check"]["table"][str(R)]["supported_rate"]
        g = r["geometry_vs_pre_pilot"]
        dfit = (g["mean_abs_diff"]["solo_fitness"] + g["mean_abs_diff"]["div_fitness"]) / 2
        L.append(f"| {r['candidate']['name']} | {f['S']}/{f['P']}/{f['ambiguous']} | {f['|S_urgent|']} | {f['|P_urgent|']} | "
                 f"{f['|twin|']} | {f['|D_urgent|']} | {f['|I|']} | {f['min_S_margin']:.3f} | {f['min_P_margin']:.3f} | {R} | "
                 f"{x['IDEAL']:.3f} | {x['NEVER']:.3f} | {x['ALWAYS']:.3f} | {x['RANDOM']:.3f} | {x['SPAWN_IFF_URGENT']:.3f} | "
                 f"{x['SPAWN_IFF_MULTIDOC']:.3f} | {x['WASTEFUL']:.3f} | {g['label_agreement']} | {dfit:.4f} |")
    L += ["", "### Degeneracy checks (viable candidates, base point)", "",
          "| candidate | P cells | S cells | S/P margins < 2δ | S left at δ = 0.045 (diagnostic) | median fitness spread over orgs | "
          "median best money / V (range) | median best money + time / V | min fixed-rule allocation / child need | "
          "children fundable at the child need | best k in P cells | fitness lost at k = 1 / largest k on the route | "
          "max child lifetime used |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
          ]
    for r in [{"candidate": {"name": "**reference (pre-pilot, r = 1)**"}, "degeneracy": ref["degeneracy"]}] + rs:
        d = r.get("degeneracy")
        if not d:
            continue
        b = d["budget"].values()
        slack = min(v["fixed_rule_allocation"] / v["min_viable_child_allocation"] for v in b if v["fixed_rule_allocation"])
        fund = min(v["children_affordable_at_min_allocation"] for v in b)
        topo = d["P_cells_topology"]
        ks = sorted({t["best_fanout_k"] for t in topo})
        loss = f"{min(t['loss_k1'] for t in topo):.2f}–{max(t['loss_k1'] for t in topo):.2f} / " \
               f"{min(t['loss_kmax'] for t in topo):.2f}–{max(t['loss_kmax'] for t in topo):.2f}"
        life = max(v["child_lifetime_used_fraction"] or 0 for v in b)
        L.append(f"| {r['candidate']['name']} | {round(d['P_share'] * 30)} | {round(d['S_share'] * 30)} | "
                 f"{d['S_or_P_within_2delta']} | {d['labels_at_delta_0.045']['S']} | {d['fitness_spread_median']:.3f} | "
                 f"{d['best_money_fraction_of_V_median']:.3f} ({d['best_money_fraction_of_V_range'][0]:.3f}–"
                 f"{d['best_money_fraction_of_V_range'][1]:.3f}) | {d['best_cost_fraction_of_V_median']:.3f} | "
                 f"{slack:.2f} | {fund} | {ks} | {loss} | {life:.0%} |")
    return "\n".join(L)


def main() -> int:
    fa = json.loads((OUT / "failure.json").read_text())
    rs = json.loads((OUT / "candidates.json").read_text())
    ref = json.loads((OUT / "reference.json").read_text())
    print(failure_tables(fa))
    print()
    print(candidate_tables(rs, ref))
    return 0


if __name__ == "__main__":
    sys.exit(main())
