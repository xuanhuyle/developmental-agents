"""Gate 0 (GATE_0_SPEC.md): worlds, plans, checks, classes, audit and power.

Every simulation here runs on small *fixture* instances whose parameters are not candidates (GATE_0_SPEC.md §6.3).
The round-1 candidate file is only built (structure checks), never simulated.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from devagents.config import Constants, EXPERIMENTS, load_frozen
from devagents.evals.calibrate import Assumptions
from devagents.gate0 import audit as audit_mod
from devagents.gate0.audit import Audit, AuditError, sha256_lf
from devagents.gate0.evaluate import View, analyze, conditions, instantiate, measure, rule_analysis, features, w0_library
from devagents.gate0.plans import Plan, clean, library, parse_plan, run_plan
from devagents.gate0.power import CellInput, power, total_runs
from devagents.gate0.run import base_constants, evaluate_round, verify
from devagents.gate0.worlds import G0Info, build_a, build_b, build_d, build_instances

ROOT = Path(__file__).resolve().parents[1]
ACC = json.loads((ROOT / "data" / "gate0" / "acceptance.json").read_text())
FIX_A = {"template": "A", "id": "FA", "domain": "incident", "n_candidates": 4, "first_number": 9001,
         "long_tokens": 150, "tiny_tokens": 20}
FIX_B = {"template": "B", "id": "FB", "domain": "lines", "heavy": ["Boreal", 320], "lights": [["Cedar", 60]],
         "phantom": "Spruce", "memo_tokens": 160}


@pytest.fixture(scope="module")
def constants() -> Constants:
    return base_constants(ACC)


@pytest.fixture(scope="module")
def asm() -> Assumptions:
    return Assumptions(**ACC["token_base"])


@pytest.fixture(scope="module")
def fa():
    return build_a(FIX_A)


@pytest.fixture(scope="module")
def fb():
    return build_b(FIX_B)


# --------------------------------------------------------------------------- worlds


def test_reveal_sets_share_everything_but_the_triage(fa, fb, constants):
    for inst in (fa, fb):
        x, y = inst.members
        assert inst.info(x, constants.sources).catalog() == inst.info(y, constants.sources).catalog()
        assert x.answer != y.answer and set(x.needed) != set(y.needed) and x.reveal != y.reveal
        diff = {d for d in x.world.docs if x.world.docs[d] != y.world.docs[d]}
        assert diff <= {t for k, t in inst.triage if k == "doc"}
    assert fa.members[0].world.sql_script != fa.members[1].world.sql_script  # A reveals through SQL
    assert fb.members[0].world.sql_script == fb.members[1].world.sql_script  # B through the memo


def test_catalog_format_matches_the_base_environment(constants):
    from devagents.environment.sources import InformationEnvironment
    from devagents.environment.world import DOC_TITLES, SQL_SCHEMA_SUMMARY, load_world
    w = load_world()
    assert G0Info(w, constants.sources, DOC_TITLES, tuple(SQL_SCHEMA_SUMMARY)).catalog() == \
        InformationEnvironment(w, constants.sources).catalog()


def test_template_a_sizes_and_answers(fa):
    x, y = fa.members
    sizes = {d: len(t) for d, t in x.world.docs.items()}
    assert min(sizes[d] for d in x.needed) > 3 * max(sizes[d] for d in y.needed)  # X reads long, Y tiny documents
    assert len(x.needed) == len(y.needed) == 2


def test_d_twin_is_t01_with_short_reports(constants):
    d = build_d({"template": "D", "id": "D", "base_task": "T01"})
    from devagents.environment.world import load_world
    base = load_world()
    m = d.members[0]
    assert set(m.world.docs) == set(base.docs) and d.task(m).id == "T01"
    for doc in m.needed:
        assert len(m.world.docs[doc]) < len(base.docs[doc]) / 4


def test_round1_candidates_build_and_keep_reveal_sets_identical_before_the_reveal(constants):
    cand = json.loads((ROOT / "data" / "gate0" / "candidates_round1.json").read_text())
    insts = build_instances(cand)  # structure only: nothing is simulated
    assert {i.template for i in insts} == {"A", "B", "D"}
    for inst in insts:
        if len(inst.members) == 2:
            x, y = inst.members
            assert inst.info(x, constants.sources).catalog() == inst.info(y, constants.sources).catalog()
            assert len(x.needed) == len(y.needed) or inst.template == "B"


# --------------------------------------------------------------------------- plans and checks


def test_every_fixture_plan_runs_clean_and_complete(fa, fb, constants, asm):
    for inst in (fa, fb):
        for m in inst.members:
            for plan in library(inst, m, 8):
                rec = run_plan(inst, m, plan, constants.regimes["urgent"], asm, constants)
                assert clean(rec), (inst.id, m.key, plan.name, rec["outcome"], rec["termination_reasons"])
                assert rec["t_reveal"] is not None


def test_pre_reveal_logs_are_identical_across_members_and_within_groups(fa, fb, constants, asm):
    for inst in (fa, fb):
        digests = {}
        for m in inst.members:
            for plan in library(inst, m, 8):
                rec = run_plan(inst, m, plan, constants.regimes["urgent"], asm, constants)
                digests.setdefault(("plan", plan.name), set()).add(rec["pre_reveal"])
                digests.setdefault(("group", m.key, plan.group), set()).add(rec["pre_reveal"])
        assert all(len(v) == 1 for v in digests.values()), [k for k, v in digests.items() if len(v) > 1]


def test_signatures_record_division_and_dissolution(fa, fb, constants, asm):
    x, y = fa.members
    rec = run_plan(fa, x, Plan("triage", 2, "fan"), constants.regimes["urgent"], asm, constants)
    assert rec["signature"] == [0, 2, 0]
    bx, by = fb.members  # X: the heavy unit is dead
    d = run_plan(fb, bx, Plan("spec", 2, "dissolve"), constants.regimes["urgent"], asm, constants)
    w = run_plan(fb, bx, Plan("spec", 2, "wait"), constants.regimes["urgent"], asm, constants)
    assert d["signature"][2] == 1 and w["signature"][2] == 0
    assert d["elapsed_s"] < w["elapsed_s"]
    dy = run_plan(fb, by, Plan("spec", 2, "dissolve"), constants.regimes["urgent"], asm, constants)
    assert dy["signature"][2] == 0  # nothing is dead in Y


def test_information_completeness_is_checked_from_the_log(fb, constants, asm):
    """Regression for the checker: a root that stops waiting for a child holding a needed unit must not count."""
    bx, by = fb.members
    wrong = replace(by, live_units=(1,))  # pretend the heavy unit is dead while it is still needed
    rec = run_plan(fb, wrong, Plan("spec", 2, "dissolve"), constants.regimes["urgent"], asm, constants)
    assert not rec["info_complete"] and not clean(rec)


def test_cancel_sends_stop_and_stays_clean(fb, constants, asm):
    bx = fb.members[0]
    rec = run_plan(fb, bx, Plan("spec", 2, "cancel"), constants.regimes["urgent"], asm, constants)
    assert clean(rec) and rec["llm_calls"] >= 4


def test_plan_names_round_trip(fa, fb):
    for inst in (fa, fb):
        for m in inst.members:
            for p in library(inst, m, 8):
                assert parse_plan(p.name) == p


def test_instantiate_maps_every_pipeline(fa, fb):
    for inst in (fa, fb):
        for m in inst.members:
            names = {p.name for p in library(inst, m, 8)}
            for pipe in w0_library(8):
                assert instantiate(pipe, inst, m, 8) in names, pipe


# --------------------------------------------------------------------------- classes


@pytest.fixture(scope="module")
def small_measure(fa, fb, constants):
    acc = copy.deepcopy(ACC)
    conds, base = conditions(acc, constants)
    keep = [c for c in conds if c[0] in (base, "g0")] + [c for c in conds if c[0].startswith("p:")][:1]
    recs = measure([fa, fb], keep, 8)
    return recs, keep, base


def test_oracle_dominates_router_and_clairvoyant_dominates_oracle(small_measure, fa, fb, constants):
    recs, conds, base = small_measure
    v = View(recs, [fa, fb], base, constants, 8, 0.03)
    for cell in v.cells:
        r = v.cell(cell)
        assert parse_plan(r["rt_plan"]).fixed and r["rt_plan"] in r["common"]
        assert r["astar"] >= r["rt"] - 1e-12 and r["hstar"] >= r["astar"] - 1e-12
        assert r["adv_w"] <= r["astar"] - v.w_star_value + 10  # defined
        groups = {parse_plan(p).group for p in r["astar_plans"].values()}
        assert len(groups) == 1  # non-anticipating: one prefix for every member


def test_rule_analysis_and_criteria_run_on_fixtures(small_measure, fa, fb, constants):
    recs, conds, base = small_measure
    v = View(recs, [fa, fb], base, constants, 8, 0.03)
    feats = {w: features(v.by_id[w[0]], v._member(w[0], w[2]), v.regimes[w[1]], constants.sources) for w in v.worlds}
    out = rule_analysis(v, feats, ACC["rule_families"], 0.03)
    assert set(out) == set(ACC["rule_families"])
    assert all(isinstance(x["min_cells_short"], int) for x in out.values())
    res = analyze(recs, [fa, fb], conds, base, ACC, 8)
    assert {"G1_integrity", "G2_sanity", "G3_G4_qualifying", "G5_uneconomic_division", "G6_dissociation",
            "G7_dissolution", "G8_robustness"} <= set(res["criteria"])
    assert res["criteria"]["G1_integrity"]["pass"], res["criteria"]["G1_integrity"]["failures"][:5]


# --------------------------------------------------------------------------- audit


def _audit(tmp_path) -> tuple[Audit, Path]:
    acc = tmp_path / "acceptance.json"
    acc.write_text(json.dumps(ACC))
    spec = tmp_path / "spec.md"
    spec.write_text("spec")
    a = Audit(tmp_path / "audit.jsonl")
    a.write_genesis(acc, spec, "test")
    return a, acc


def test_audit_chain_detects_edits(tmp_path):
    a, _ = _audit(tmp_path)
    a.append("note", {"x": 1})
    assert a.verify() == []
    lines = a.path.read_text().splitlines()
    lines[1] = lines[1].replace('"x":1', '"x":2')
    a.path.write_text("\n".join(lines) + "\n")
    assert a.verify()
    with pytest.raises(AuditError):
        a.append("note", {})


def test_round_guard(tmp_path):
    a, acc = _audit(tmp_path)
    with pytest.raises(AuditError):
        a.begin_evaluation(3, "c1", acc, ACC, {}, require_clean=False)
    with pytest.raises(AuditError):
        a.begin_evaluation(2, "c2", acc, ACC, {}, require_clean=False)  # round 1 has not failed
    a.begin_evaluation(1, "c1", acc, ACC, {}, require_clean=False)
    with pytest.raises(AuditError):
        a.begin_evaluation(1, "c1", acc, ACC, {}, require_clean=False)  # no defect logged
    with pytest.raises(AuditError):
        a.begin_evaluation(1, "other", acc, ACC, {}, require_clean=False)  # another candidate set
    a.log_defect(1, "bug", "abc", "test_x")
    a.begin_evaluation(1, "c1", acc, ACC, {}, require_clean=False)
    a.log_defect(1, "bug2", "abd", "test_y")
    a.begin_evaluation(1, "c1", acc, ACC, {}, require_clean=False)
    a.log_defect(1, "bug3", "abe", "test_z")
    with pytest.raises(AuditError):  # max_reevaluations = 2
        a.begin_evaluation(1, "c1", acc, ACC, {}, require_clean=False)
    a.complete_evaluation(1, "r", {"decision": "FAIL"})
    a.decide(1, "FAIL", "")
    with pytest.raises(AuditError):
        a.begin_evaluation(1, "c1", acc, ACC, {}, require_clean=False)  # closed
    a.begin_evaluation(2, "c2", acc, ACC, {}, require_clean=False)  # allowed after a FAIL


def test_round_guard_refuses_changed_acceptance_and_dirty_tree(tmp_path, monkeypatch):
    a, acc = _audit(tmp_path)
    monkeypatch.setattr(audit_mod, "git_state", lambda root=None: {"head": "x", "dirty": ["devagents/x.py"]})
    with pytest.raises(AuditError):
        a.begin_evaluation(1, "c1", acc, ACC, {})
    acc.write_text(json.dumps({**ACC, "delta": 0.01}))
    with pytest.raises(AuditError):
        a.begin_evaluation(1, "c1", acc, ACC, {}, require_clean=False)


def test_audit_requires_genesis(tmp_path):
    a = Audit(tmp_path / "audit.jsonl")
    acc = tmp_path / "acceptance.json"
    acc.write_text(json.dumps(ACC))
    with pytest.raises(AuditError):
        a.begin_evaluation(1, "c1", acc, ACC, {}, require_clean=False)


def test_end_to_end_round_on_fixtures_is_logged_and_not_repeatable(tmp_path, monkeypatch):
    acc_data = copy.deepcopy(ACC)
    acc_data["env_perturbations"] = acc_data["env_perturbations"][:1]
    acc_data["power"]["search"] = {"R_M": [6], "R_B": [4], "R_S": [2], "n_sim": 20, "n_boot": 30}
    acc_data["power"]["final"] = {"n_sim": 20, "n_boot": 30, "sens_n_sim": 10}
    acc = tmp_path / "acceptance.json"
    acc.write_text(json.dumps(acc_data))
    spec = tmp_path / "spec.md"
    spec.write_text("spec")
    a = Audit(tmp_path / "audit.jsonl")
    a.write_genesis(acc, spec, "fixture test")
    cand = tmp_path / "candidates_round1.json"
    cand.write_text(json.dumps({"round": 1, "instances": [FIX_A, FIX_B]}))
    import devagents.gate0.evaluate as ev
    monkeypatch.setattr(ev, "grid", lambda base: [base])  # one token point keeps the fixture test fast
    res = evaluate_round(1, cand, acc_path=acc, audit=a, out_dir=tmp_path / "out", require_clean=False,
                         progress=None)
    assert res["decision"] in ("PASS", "FAIL", "INDETERMINATE")
    kinds = [e["kind"] for e in a.entries()]
    assert kinds == ["genesis", "round_registered", "evaluation_started", "evaluation_completed"]
    assert a.entries()[-1]["payload"]["results_sha"] == sha256_lf(tmp_path / "out" / "results.json")
    with pytest.raises(AuditError):
        evaluate_round(1, cand, acc_path=acc, audit=a, out_dir=tmp_path / "out2", require_clean=False, progress=None)


# --------------------------------------------------------------------------- power


def _cells(effect: float) -> list[CellInput]:
    out = []
    for i, t in enumerate(("A", "A", "B", "B")):
        out.append(CellInput(f"c{i}", t, {"X": 0.6 + effect, "Y": 0.8 + effect}, {"X": 0.6, "Y": 0.8},
                             {"X": 1, "Y": 0}, {"X": 0, "Y": 0}, "X", {}))
    return out


def test_power_is_high_for_a_large_effect_and_low_under_the_null():
    a = dict(ACC["power"]["primary"])
    alloc = {"R_M": 10, "R_B": 8, "R_N": 8, "R_A": 1, "R_S": 2}
    big = power(_cells(0.3), alloc, {**a, "pi": 1.0, "s_ctl": 0.0}, 60, 100, 1)
    assert big["all"] > 0.9
    null = power(_cells(0.3), alloc, {**a, "pi": 0.0, "tau_sim": 0.0, "eta": 0.0}, 100, 100, 2)
    assert null["F2"] < 0.2 and null["F1"] < 0.2


def test_total_runs_counts_every_arm():
    alloc = {"R_M": 10, "R_B": 6, "R_N": 6, "R_A": 1, "R_S": 2}
    assert total_runs(4, alloc) == 2 * 4 * (10 + 6 + 6 + 1) + 2 * 4 * 2


def test_verify_reports_a_missing_genesis(tmp_path):
    assert not verify(Audit(tmp_path / "none.jsonl"))["ok"]
