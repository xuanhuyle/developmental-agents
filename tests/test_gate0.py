"""Gate 0 (GATE_0_SPEC.md): worlds, plans, checks, classes, audit and power.

Every simulation here runs on small *fixture* instances whose parameters are not candidates (GATE_0_SPEC.md §6).
The round-1 candidate file is only built (structure checks), never simulated.
"""

from __future__ import annotations

import copy
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from devagents.evals.calibrate import Assumptions
from devagents.gate0.audit import Audit, AuditError, checkout_problems, sha256_lf
from devagents.gate0.evaluate import (View, _dissolution, analyze, best_one_line, conditions, features, instantiate,
                                      measure, w0_library)
from devagents.gate0.plans import Plan, Program, balanced, clean, library, parse_plan, run_plan
from devagents.gate0.power import CellInput, choose_allocation, power, total_runs
from devagents.gate0.run import _finite, base_constants, cli, evaluate_round, verify
from devagents.gate0.worlds import G0Info, build_a, build_b, build_d, build_instances
from devagents.runtime.resources import estimate_tokens

ROOT = Path(__file__).resolve().parents[1]
ACC = json.loads((ROOT / "data" / "gate0" / "acceptance.json").read_text())
FIX_A = {"template": "A", "id": "FA", "domain": "incident", "n_candidates": 4, "first_number": 9001,
         "long_tokens": 150, "tiny_tokens": 20}
FIX_B = {"template": "B", "id": "FB", "domain": "lines", "heavy": ["Boreal", 320], "lights": [["Cedar", 60]],
         "phantom": "Spruce", "memo_tokens": 160}
FIX_B2 = {"template": "B", "id": "FB2", "domain": "tracks", "heavy": ["Boreal", 500],
          "lights": [["Cedar", 90], ["Aspen", 90]], "phantom": "Spruce", "memo_tokens": 300}


@pytest.fixture(scope="module")
def constants():
    return base_constants(ACC)


@pytest.fixture(scope="module")
def asm():
    return Assumptions(**ACC["token_base"])


@pytest.fixture(scope="module")
def fa():
    return build_a(FIX_A)


@pytest.fixture(scope="module")
def fb():
    return build_b(FIX_B)


@pytest.fixture(scope="module")
def fb2():
    return build_b(FIX_B2)


def urgent(constants):
    return constants.regimes["urgent"]


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
    assert "Spruce" in fb.members[0].world.sql_script  # the phantom is a real, report-less entity


def test_catalog_format_matches_the_base_environment(constants):
    from devagents.environment.sources import InformationEnvironment
    from devagents.environment.world import DOC_TITLES, SQL_SCHEMA_SUMMARY, load_world
    w = load_world()
    assert G0Info(w, constants.sources, DOC_TITLES, tuple(SQL_SCHEMA_SUMMARY)).catalog() == \
        InformationEnvironment(w, constants.sources).catalog()


def test_template_a_sizes_and_answers(fa):
    x, y = fa.members
    sizes = {d: len(t) for d, t in x.world.docs.items()}
    assert min(sizes[d] for d in x.needed) > 3 * max(sizes[d] for d in y.needed)
    assert len(x.needed) == len(y.needed) == 2


def test_d_twin_is_t01_with_short_reports():
    from devagents.environment.world import load_world
    d = build_d({"template": "D", "id": "D", "base_task": "T01"})
    base = load_world()
    m = d.members[0]
    assert set(m.world.docs) == set(base.docs) and d.task(m).id == "T01"
    for doc in m.needed:
        assert len(m.world.docs[doc]) < len(base.docs[doc]) / 4


def test_round1_candidates_build_without_simulation(constants):
    cand = json.loads((ROOT / "data" / "gate0" / "candidates_round1.json").read_text())
    insts = build_instances(cand)  # structure only: nothing is simulated
    assert {i.template for i in insts} == {"A", "B", "D"}
    for inst in insts:
        if len(inst.members) == 2:
            x, y = inst.members
            assert inst.info(x, constants.sources).catalog() == inst.info(y, constants.sources).catalog()


# --------------------------------------------------------------------------- plans and checks


def test_every_fixture_plan_runs_clean_and_complete(fa, fb, fb2, constants, asm):
    for inst in (fa, fb, fb2):
        for m in inst.members:
            for plan in library(inst, m, 8):
                rec = run_plan(inst, m, plan, urgent(constants), asm, constants)
                assert clean(rec), (inst.id, m.key, plan.name, rec["outcome"], rec["termination_reasons"])
                assert rec["t_reveal"] is not None


def test_pre_reveal_logs_are_identical_across_members_and_within_groups(fa, fb2, constants, asm):
    for inst in (fa, fb2):
        digests = {}
        for m in inst.members:
            for plan in library(inst, m, 8):
                rec = run_plan(inst, m, plan, urgent(constants), asm, constants)
                digests.setdefault(("plan", plan.name), set()).add(rec["pre_reveal"])
                digests.setdefault(("group", m.key, plan.group), set()).add(rec["pre_reveal"])
        assert all(len(v) == 1 for v in digests.values()), [k for k, v in digests.items() if len(v) > 1]


def test_signatures_record_division_and_dissolution(fa, fb, constants, asm):
    x = fa.members[0]
    assert run_plan(fa, x, Plan("triage", 2, "fan"), urgent(constants), asm, constants)["signature"] == [0, 2, 0]
    assert run_plan(fa, x, Plan("triage", 1, "self"), urgent(constants), asm, constants)["signature"] == [0, 1, 0]
    bx, by = fb.members  # X: the heavy unit is dead
    d = run_plan(fb, bx, Plan("spec", 2, "dissolve"), urgent(constants), asm, constants)
    w = run_plan(fb, bx, Plan("spec", 2, "wait"), urgent(constants), asm, constants)
    assert d["signature"][2] == 1 and w["signature"][2] == 0 and d["elapsed_s"] < w["elapsed_s"]
    assert run_plan(fb, by, Plan("spec", 2, "dissolve"), urgent(constants), asm, constants)["signature"][2] == 0


def test_wait_and_dissolve_are_identical_when_nothing_is_dead(fb, fb2, constants, asm):
    """Regression (review): `wait` used to spend a redundant WAIT step after every child had reported."""
    for inst in (fb, fb2):
        y = inst.members[1]
        for pre, k in (("spec", 2), ("spectop", 1)):
            w = run_plan(inst, y, Plan(pre, k, "wait"), urgent(constants), asm, constants)
            d = run_plan(inst, y, Plan(pre, k, "dissolve"), urgent(constants), asm, constants)
            assert (w["elapsed_s"], w["money_usd"], w["llm_calls"]) == (d["elapsed_s"], d["money_usd"], d["llm_calls"])


def test_assignments_are_size_balanced():
    sizes = {"a": 10, "b": 9, "c": 1, "d": 1}
    bins = balanced(["a", "c", "b", "d"], sizes.get, 2)
    assert sorted(sum(sizes[x] for x in b) for b in bins) == [10, 11]


def test_spec_children_share_the_long_documents_in_template_a(fa):
    """Regression (review): round-robin over interleaved units gave one child every long document."""
    for m in fa.members:
        prog = Program(fa, m, Plan("spec", 2, "wait"), 0)
        next(prog._root(SimpleNamespace(messages=[], agents={})))
        loads = [sum(estimate_tokens(m.world.docs[d]) for u in a if u in m.live_units for d in fa.units[u])
                 for a in prog.assign]
        assert max(loads) <= 2 * min(loads) + 50


def test_information_completeness_is_checked_from_the_log(fb, constants, asm):
    by = fb.members[1]
    wrong = replace(by, live_units=(1,))  # pretend the heavy unit is dead while it is still needed
    rec = run_plan(fb, wrong, Plan("spec", 2, "dissolve"), urgent(constants), asm, constants)
    assert not rec["info_complete"] and not clean(rec)


def test_cancel_sends_stop_and_stays_clean(fb, constants, asm):
    assert clean(run_plan(fb, fb.members[0], Plan("spec", 2, "cancel"), urgent(constants), asm, constants))


def test_plan_names_round_trip_and_pipelines_instantiate(fa, fb, fb2):
    for inst in (fa, fb, fb2):
        for m in inst.members:
            names = {p.name for p in library(inst, m, 8)}
            for p in library(inst, m, 8):
                assert parse_plan(p.name) == p
            for pipe in w0_library(8):
                assert instantiate(pipe, inst, m, 8) in names, pipe


# --------------------------------------------------------------------------- classes


@pytest.fixture(scope="module")
def small(fa, fb2, constants):
    conds, base = conditions(ACC, constants)
    keep = [c for c in conds if c[0] in (base, "g0")] + [c for c in conds if c[0].startswith("p:")][:1]
    recs = measure([fa, fb2], keep, 8)
    feats = {(i.id, r, m.key): features(i, m, constants.sources) for i in (fa, fb2) for r in constants.regimes
             for m in i.members}
    return recs, keep, base, feats


def test_oracle_dominates_router_and_clairvoyant_dominates_oracle(small, fa, fb2, constants):
    recs, conds, base, feats = small
    v = View(recs, [fa, fb2], base, constants, 8, 0.03, feats)
    for cell in v.cells:
        r = v.cell(cell)
        assert parse_plan(r["rt_plan"]).fixed
        assert r["astar"] >= r["rt"] - 1e-12 and r["hstar"] >= r["astar"] - 1e-12
        assert len({parse_plan(p).group for p in r["astar_plans"].values()}) == 1  # one prefix for every member


def test_generic_workflow_includes_one_line_rules():
    zero = {k: 0 for k in ("n_units", "n_catalog_docs", "cand_read_s", "n_needed", "max_needed_s")}
    worlds = [("i", "urgent", "X"), ("i", "urgent", "Y")]
    feats = {worlds[0]: {**zero, "needed_read_s": 300}, worlds[1]: {**zero, "needed_read_s": 50}}
    val = {("W:fan4", worlds[0]): 0.6, ("W:fan4", worlds[1]): 0.4, ("W:solo", worlds[0]): 0.3,
           ("W:solo", worlds[1]): 0.8}
    best = best_one_line(val, ["W:fan4", "W:solo"], worlds, worlds, feats)
    assert best["assign"] == {worlds[0]: "W:fan4", worlds[1]: "W:solo"} and abs(best["mean"] - 0.7) < 1e-9


def test_dissolution_counts_only_real_dissolution(small, fb2, fa, constants):
    recs, conds, base, feats = small
    v = View(recs, [fa, fb2], base, constants, 8, 0.03, feats)
    for cell in v.cells:
        if _dissolution(v, cell) > 0:
            plans = v.cell(cell)["astar_plans"]
            assert any(v.rec[(*cell, m, plans[m])]["signature"][2] > 0 for m in plans)


def test_criteria_run_on_fixtures(small, fa, fb2):
    recs, conds, base, _ = small
    res = analyze(recs, [fa, fb2], conds, base, ACC, 8)
    assert {"G1_integrity", "G2_sanity", "G3_G4_qualifying", "G5_uneconomic_division", "G7_dissolution",
            "G8_robustness"} <= set(res["criteria"])
    assert res["criteria"]["G1_integrity"]["pass"], res["criteria"]["G1_integrity"]["failures"][:5]


# --------------------------------------------------------------------------- audit


def _audit(tmp_path):
    acc, spec, cand = tmp_path / "acceptance.json", tmp_path / "spec.md", tmp_path / "candidates_round1.json"
    acc.write_text(json.dumps(ACC))
    spec.write_text("spec")
    cand.write_text(json.dumps({"round": 1, "instances": [FIX_A]}))
    a = Audit(tmp_path / "audit.jsonl", anchored=False)
    a.write_genesis(acc, spec, cand, "test")
    return a, acc, spec, cand


def _begin(a, acc, spec, n, sha, digests=None):
    return a.begin_evaluation(n, sha, acc, ACC, digests or {"FA": "d"}, spec_path=spec)


def _complete(a, n, decision, **kw):
    k = len(a.rounds()[n]["evaluations"])
    return a.complete_evaluation(n, "r", {"decision": decision, "evaluation": k, **kw})


def test_audit_chain_detects_edits_and_torn_lines(tmp_path):
    a, acc, spec, cand = _audit(tmp_path)
    _begin(a, acc, spec, 1, sha256_lf(cand))
    assert a.verify() == []
    lines = a.path.read_text().splitlines()
    lines[1] = lines[1].replace('"round":1', '"round":2')
    a.path.write_text("\n".join(lines) + "\n")
    assert a.verify()
    with pytest.raises(AuditError):
        _complete(a, 1, "FAIL")
    a.path.write_text("\n".join(lines[:1]) + "\n" + lines[1][:20])
    assert a.verify() and "incomplete" in a.verify()[0]


def test_round_guard_a_completed_fail_stands(tmp_path):
    a, acc, spec, cand = _audit(tmp_path)
    c1 = sha256_lf(cand)
    with pytest.raises(AuditError):
        _begin(a, acc, spec, 3, c1)
    with pytest.raises(AuditError):
        _begin(a, acc, spec, 2, "c2")  # round 1 has not failed
    with pytest.raises(AuditError):
        _begin(a, acc, spec, 1, "not-the-pinned-file")
    _begin(a, acc, spec, 1, c1)
    with pytest.raises(AuditError):
        _begin(a, acc, spec, 1, c1)  # evaluation 1 is pending
    with pytest.raises(AuditError):
        a.decide(1, "FAIL", "")  # pending
    _complete(a, 1, "FAIL")
    with pytest.raises(AuditError):
        a.log_defect(1, "bug", "abc", "tests/test_gate0.py::test_x")  # a completed FAIL stands
    with pytest.raises(AuditError):
        _begin(a, acc, spec, 1, c1)
    with pytest.raises(AuditError):
        a.decide(1, "PASS", "")  # must repeat the mechanical decision
    a.decide(1, "FAIL", "")
    with pytest.raises(AuditError):
        _begin(a, acc, spec, 1, c1)  # closed
    _begin(a, acc, spec, 2, "c2")  # allowed after a FAIL


def test_round_guard_reevaluation_only_after_indeterminate(tmp_path):
    a, acc, spec, cand = _audit(tmp_path)
    c1 = sha256_lf(cand)
    _begin(a, acc, spec, 1, c1)
    _complete(a, 1, "INDETERMINATE", aborted=True)
    with pytest.raises(AuditError):
        _begin(a, acc, spec, 1, c1)  # no defect logged
    a.log_defect(1, "crash", "abc", "")
    with pytest.raises(AuditError):
        _begin(a, acc, spec, 1, c1, {"FA": "other world"})  # a world change is a new round
    _begin(a, acc, spec, 1, c1)
    _complete(a, 1, "INDETERMINATE")
    a.log_defect(1, "bug", "abd", "tests/test_gate0.py::test_y")
    _begin(a, acc, spec, 1, c1)
    _complete(a, 1, "INDETERMINATE")
    a.log_defect(1, "bug3", "abe", "tests/test_gate0.py::test_z")
    with pytest.raises(AuditError):  # max_reevaluations = 2
        _begin(a, acc, spec, 1, c1)
    with pytest.raises(AuditError):
        a.decide(1, "FAIL", "")
    a.decide(1, "INDETERMINATE", "")


def test_round_guard_refuses_changed_acceptance_or_spec(tmp_path):
    a, acc, spec, cand = _audit(tmp_path)
    spec.write_text("changed")
    with pytest.raises(AuditError):
        _begin(a, acc, spec, 1, sha256_lf(cand))
    spec.write_text("spec")
    acc.write_text(json.dumps({**ACC, "delta": 0.01}))
    with pytest.raises(AuditError):
        _begin(a, acc, spec, 1, sha256_lf(cand))


def test_audit_requires_genesis(tmp_path):
    a = Audit(tmp_path / "audit.jsonl", anchored=False)
    acc = tmp_path / "acceptance.json"
    acc.write_text(json.dumps(ACC))
    with pytest.raises(AuditError):
        a.begin_evaluation(1, "c1", acc, ACC, {}, spec_path=None)


def test_cli_refuses_a_private_audit_for_writing_actions(tmp_path):
    for action in ("genesis", "calibrate", "defect", "decide"):
        with pytest.raises(AuditError):
            cli(SimpleNamespace(action=action, audit=str(tmp_path / "x.jsonl"), round=1, note="", fix_commit="",
                                regression_test="", decision="FAIL"))


# ------------------------------------------------------------------ the anchored trail, on a scratch git repository


def _repo(tmp_path):
    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)

    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout

    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    git("remote", "add", "origin", str(remote))
    (repo / "data" / "gate0").mkdir(parents=True)
    paths = (repo / "data/gate0/acceptance.json", repo / "GATE_0_SPEC.md", repo / "data/gate0/candidates_round1.json")
    paths[0].write_text(json.dumps(ACC))
    paths[1].write_text("spec")
    paths[2].write_text(json.dumps({"round": 1, "instances": [FIX_A]}))
    (repo / ".gitignore").write_text("data/gate0/audit.lock\n__pycache__/\n")
    (repo / "code.py").write_text("x = 1\n")

    def publish(msg="commit"):
        git("add", "-A")
        git("commit", "-q", "-m", msg)
        git("push", "-q", "origin", "main")
    publish("init")
    return repo, paths, git, publish


def test_anchored_genesis_needs_a_clean_pushed_checkout_and_is_written_once(tmp_path):
    repo, (acc, spec, cand), git, publish = _repo(tmp_path)
    a = Audit(repo / "data/gate0/audit.jsonl", anchored=True, root=repo)
    (repo / "stray.py").write_text("")
    with pytest.raises(AuditError, match="not clean"):
        a.write_genesis(acc, spec, cand, "", instances={"FA": "d"})
    (repo / "stray.py").unlink()
    (repo / "code.py").write_text("x = 2\n")
    git("commit", "-qam", "unpushed")
    with pytest.raises(AuditError, match="push first"):
        a.write_genesis(acc, spec, cand, "", instances={"FA": "d"})
    git("push", "-q", "origin", "main")
    with pytest.raises(AuditError, match="world digests"):
        a.write_genesis(acc, spec, cand, "")
    g = a.write_genesis(acc, spec, cand, "", instances={"FA": "d"})
    assert len(g["payload"]["git"]["head"]) == 40 and g["payload"]["git"]["branch"] == "main"
    publish("genesis")
    git("rm", "-q", "data/gate0/audit.jsonl")
    publish("delete the audit")
    with pytest.raises(AuditError, match="audit"):
        Audit(repo / "data/gate0/audit.jsonl", anchored=True, root=repo).write_genesis(
            acc, spec, cand, "", instances={"FA": "d"})


def test_anchored_evaluation_is_published_before_it_runs(tmp_path):
    repo, (acc, spec, cand), git, publish = _repo(tmp_path)
    a = Audit(repo / "data/gate0/audit.jsonl", anchored=True, root=repo)
    digests, c1 = {"FA": "d"}, sha256_lf(cand)
    a.write_genesis(acc, spec, cand, "", instances=digests)
    with pytest.raises(AuditError, match="committed copy"):
        a.begin_evaluation(1, c1, acc, ACC, digests, spec_path=spec)  # genesis not published
    publish("genesis")
    with pytest.raises(AuditError, match="digests pinned"):
        a.begin_evaluation(1, c1, acc, ACC, {"FA": "other"}, spec_path=spec)
    start = a.begin_evaluation(1, c1, acc, ACC, digests, spec_path=spec)
    out = repo / "data/gate0/round1/eval1"

    def confirm():
        return a.confirm_start(1, c1, digests, out, acceptance_path=acc, spec_path=spec)
    with pytest.raises(AuditError, match="committed copy"):
        confirm()  # the start is not published yet
    git("add", "data/gate0/audit.jsonl")
    git("commit", "-q", "-m", "start")
    with pytest.raises(AuditError, match="push first"):
        confirm()  # committed, not pushed
    git("push", "-q", "origin", "main")
    assert confirm()["seq"] == start["seq"]
    out.mkdir(parents=True)
    with pytest.raises(AuditError, match="exists already"):
        confirm()
    out.rmdir()
    git("update-index", "--skip-worktree", "code.py")
    (repo / "code.py").write_text("x = 9\n")
    assert any("hidden" in p for p in checkout_problems(repo))
    with pytest.raises(AuditError, match="not clean"):
        confirm()
    git("update-index", "--no-skip-worktree", "code.py")
    publish("a code change after the start")
    with pytest.raises(AuditError, match="changed since the evaluation was started"):
        confirm()


def test_anchored_code_and_history_are_pinned(tmp_path):
    repo, (acc, spec, cand), git, publish = _repo(tmp_path)
    a = Audit(repo / "data/gate0/audit.jsonl", anchored=True, root=repo)
    digests, c1 = {"FA": "d"}, sha256_lf(cand)
    a.write_genesis(acc, spec, cand, "", instances=digests)
    publish("genesis")
    (repo / "code.py").write_text("x = 2\n")
    publish("a code change after genesis")
    with pytest.raises(AuditError, match="changed since genesis"):
        a.begin_evaluation(1, c1, acc, ACC, digests, spec_path=spec)
    (repo / "code.py").write_text("x = 1\n")
    publish("revert")  # the net diff since genesis is empty again
    a.begin_evaluation(1, c1, acc, ACC, digests, spec_path=spec)
    publish("start")
    full = a.path.read_text()
    a.path.write_text(full.splitlines(keepends=True)[0])
    publish("truncate the audit")
    assert any("truncates" in p for p in a.history_problems())
    with pytest.raises(AuditError):
        a.confirm_start(1, c1, digests, repo / "o", acceptance_path=acc, spec_path=spec)


# ------------------------------------------------------------------ evaluation runs (fixtures only)


def _small_acc(tmp_path, instances):
    acc_data = copy.deepcopy(ACC)
    acc_data["env_perturbations"] = acc_data["env_perturbations"][:1]
    acc_data["power"]["search"] = {"R_M": [6], "R_B": [4], "R_ABL": [2], "R_S": [2], "n_sim": 20}
    acc_data["power"]["final"] = {"n_sim": 20, "sens_n_sim": 10}
    acc, spec, cand = tmp_path / "acceptance.json", tmp_path / "spec.md", tmp_path / "candidates_round1.json"
    acc.write_text(json.dumps(acc_data))
    spec.write_text("spec")
    cand.write_text(json.dumps({"round": 1, "instances": instances}))
    a = Audit(tmp_path / "audit.jsonl", anchored=False)
    a.write_genesis(acc, spec, cand, "fixture test")
    return a, acc, spec, cand


def test_end_to_end_round_on_fixtures_is_logged_and_not_repeatable(tmp_path, monkeypatch):
    a, acc, spec, cand = _small_acc(tmp_path, [FIX_A, FIX_B])
    import devagents.gate0.evaluate as ev
    monkeypatch.setattr(ev, "grid", lambda base: [base])  # one token point keeps the fixture test fast
    res = evaluate_round(1, cand, acc_path=acc, audit=a, out_dir=tmp_path / "out", spec_path=spec, progress=None)
    assert res["decision"] in ("PASS", "FAIL", "INDETERMINATE")
    assert [e["kind"] for e in a.entries()] == ["genesis", "round_registered", "evaluation_started",
                                                "evaluation_progress", "evaluation_completed"]
    assert a.entries()[-1]["payload"]["results_sha"] == sha256_lf(tmp_path / "out" / "results.json")
    json.loads((tmp_path / "out" / "results.json").read_text())  # strict JSON (no Infinity or NaN)
    with pytest.raises(AuditError):
        evaluate_round(1, cand, acc_path=acc, audit=a, out_dir=tmp_path / "o2", spec_path=spec, progress=None)


def test_the_followup_branch_runs_on_forced_qualifying_cells(tmp_path, monkeypatch):
    a, acc, spec, cand = _small_acc(tmp_path, [FIX_A, FIX_B])
    import devagents.gate0.evaluate as ev
    import devagents.gate0.run as run_mod
    monkeypatch.setattr(ev, "grid", lambda base: [base])
    real = run_mod.analyze

    def forced(*args, **kw):
        out = real(*args, **kw)
        out["criteria"]["G3_G4_qualifying"]["qualifying"] = ["FA|urgent", "FB|urgent"]
        return out
    monkeypatch.setattr(run_mod, "analyze", forced)
    res = evaluate_round(1, cand, acc_path=acc, audit=a, out_dir=tmp_path / "out", spec_path=spec, progress=None)
    g9 = res["criteria"]["G9_power"]
    assert g9["power_presentation"] is not None and g9["power_deliberation"] is not None
    f = json.loads((tmp_path / "out" / "results.json").read_text())["followup"]
    assert set(f["deliberation"]["checkpoint_output_tokens"]) == {"250", "500", "1000", "2000", "4000"}
    assert f["cost"]["deliberation"]["api_calls"] > f["cost"]["presentation"]["api_calls"]
    for c in f["effects"].values():
        assert all(n >= 2 for role in c["checkpoints"].values() for n in role.values())


def test_a_crash_is_recorded_as_indeterminate(tmp_path, monkeypatch):
    a, acc, spec, cand = _audit(tmp_path)
    import devagents.gate0.run as run_mod

    def boom(*args, **kw):
        raise RuntimeError("simulated crash")
    monkeypatch.setattr(run_mod, "run_analysis", boom)
    with pytest.raises(RuntimeError):
        evaluate_round(1, cand, acc_path=acc, audit=a, out_dir=tmp_path / "o", spec_path=spec, progress=None)
    last = a.entries()[-1]
    assert last["kind"] == "evaluation_completed" and last["payload"]["decision"] == "INDETERMINATE"
    assert last["payload"]["aborted"]


def test_an_abort_after_a_determined_fail_records_the_fail(tmp_path, monkeypatch):
    a, acc, spec, cand = _audit(tmp_path)
    import devagents.gate0.run as run_mod

    def fail_then_abort(instances, acc_, constants, progress=None, checkpoint=None):
        checkpoint({"pre_power_decision": "FAIL", "criteria": {"G3_G4_qualifying": False}})
        raise KeyboardInterrupt
    monkeypatch.setattr(run_mod, "run_analysis", fail_then_abort)
    with pytest.raises(KeyboardInterrupt):
        evaluate_round(1, cand, acc_path=acc, audit=a, out_dir=tmp_path / "o", spec_path=spec, progress=None)
    kinds = [e["kind"] for e in a.entries()]
    assert kinds[-2:] == ["evaluation_progress", "evaluation_completed"]
    assert a.entries()[-1]["payload"]["decision"] == "FAIL"
    with pytest.raises(AuditError):
        a.log_defect(1, "interrupted", "x", "")  # the FAIL stands


def test_finite_serialization():
    assert _finite({"a": float("-inf"), "b": [float("nan"), 1.0, float("inf")]}) == {"a": "-inf",
                                                                                    "b": ["nan", 1.0, "inf"]}


def test_verify_reports_a_missing_genesis(tmp_path):
    assert not verify(Audit(tmp_path / "none.jsonl", anchored=False))["ok"]


# --------------------------------------------------------------------------- power


def _cells(effect: float) -> list[CellInput]:
    ms = ("X", "Y")
    return [CellInput(f"c{i}", t, "urgent", a={"X": 0.6 + effect, "Y": 0.8 + effect}, b={"X": 0.6, "Y": 0.8},
                      d={"X": 0.55, "Y": 0.82}, r={"X": 0.6, "Y": 0.8}, a_label={"X": 1, "Y": 0},
                      b_label={"X": 0, "Y": 0}, d_label={"X": 0, "Y": 0}, r_label={"X": 0, "Y": 0},
                      checkpoints={role: {m: 2 for m in ms} for role in "abdr"}, ck_eta=0.1)
            for i, t in enumerate(("A", "A", "B", "B"))]


def test_power_is_high_for_a_large_effect_and_low_under_the_null():
    a = dict(ACC["power"]["primary"])
    alloc = {"R_M": 10, "R_B": 8, "R_N": 8, "R_ABL": 4, "R_A": 1, "R_S": 2}
    big = power(_cells(0.3), alloc, {**a, "pi": 1.0, "s_ctl": 0.0, "p_fail": 0.0, "p_fail_M": 0.0}, 200, 1,
                "presentation", 16)
    assert big["all"] > 0.9
    null = power(_cells(0.3), alloc, {**a, "pi": 0.0, "q_default": 0.0, "tau_sim": 0.0, "eta": 0.0}, 400, 2,
                 "presentation", 16)
    assert null["F2"] < 0.1 and null["F1"] < 0.1 and null["F5"] < 0.1
    delib = power(_cells(0.05), alloc, {**a, "pi": 1.0}, 200, 3, "deliberation", 16)
    assert delib["F2"] < 0.05  # two checkpoints costing 0.1 each swamp an effect of 0.05


def test_the_ablation_arm_never_adapts():
    a = {**ACC["power"]["primary"], "pi": 1.0, "q_default": 0.0, "s_ctl": 0.0}
    cells = [CellInput(**{**c.__dict__, "b_label": {"X": 1, "Y": 0}}) for c in _cells(0.3)]
    alloc = {"R_M": 10, "R_B": 8, "R_N": 8, "R_ABL": 6, "R_A": 1, "R_S": 2}
    assert power(cells, alloc, a, 100, 4, "presentation", 16)["F5"] > 0.95  # ABL falls back to the router's plan


def test_allocation_is_the_highest_search_power():
    spec = copy.deepcopy(ACC["power"])
    spec["search"] = {"R_M": [6, 20], "R_B": [4], "R_ABL": [2], "R_S": [2, 4], "n_sim": 100}
    alloc, tried = choose_allocation(_cells(0.05), 4, spec)
    chosen = next(t for t in tried if all(t[k] == alloc[k] for k in alloc))
    assert chosen["power"] == max(t["power"] for t in tried)


def test_total_runs_counts_every_arm():
    alloc = {"R_M": 10, "R_B": 6, "R_N": 6, "R_ABL": 3, "R_A": 1, "R_S": 2}
    assert total_runs(4, 6, alloc) == 2 * 4 * (10 + 6 + 6 + 3 + 1) + 6 * 2
