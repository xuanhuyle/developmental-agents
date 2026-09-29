"""Metrics come from the log alone, fitness can be recomputed with any weights, and the §8 evaluator can both
pass and fail (SPEC §7.3, §8, §9)."""

import json
import random

import pytest

from devagents.config import load_frozen
from devagents.environment.tasks import TASKS
from devagents.evals.analysis import _synthetic_policies, evaluate, synthetic_records, validity
from devagents.evals.experiment import verify_frozen
from devagents.evals.metrics import Weights, fitness, metrics_from_events
from devagents.runtime.events import EventLog, read_events
from devagents.runtime.runtime import Run, RunConfig
from devagents.agents.policies import ScriptedPolicy
from devagents.environment.tasks import TASKS_BY_ID
from tests.helpers import by_step, info, q, regime, spawn, term

FROZEN = load_frozen()
CELLS, SETS = FROZEN["calibration"]["cells"], FROZEN["calibration"]["gate"]["sets"]
MAX_DOCS = {t.id: t.max_doc_route for t in TASKS}


def test_metrics_from_the_jsonl_file_match_the_in_memory_run(tmp_path):
    cfg = RunConfig(TASKS_BY_ID["T01"], regime(), "developmental")
    script = by_step({"A0": [spawn(("read region-northland", 0.05, 900), wait=True), term("Westreach")],
                      "A0.1": [q("region-northland"), term("r")]})
    log = EventLog(cfg.run_id, tmp_path / "run.jsonl")
    run = Run(cfg, ScriptedPolicy(script, reasoning_tokens=40), info(), log)
    run.execute()
    log.close()
    from_disk = metrics_from_events(read_events(tmp_path / "run.jsonl"))
    assert from_disk == metrics_from_events(run.log.events)
    assert from_disk["money_usd"] == run.ledger.total_spent / 1e6
    assert from_disk["agents"] == len(run.agents) and from_disk["quality"] == 1.0


def test_fitness_is_recomputable_with_other_weights_without_rerunning():
    m = {"quality": 1.0, "money_usd": 0.1, "elapsed_s": 100.0, "deadline_s": 1500.0, "coordination_usd": 0.01,
         "outcome": "answered"}
    base = fitness(m, Weights(task_value=0.5, value_of_time=0.001))
    assert base == pytest.approx(1 - 0.2 - 0.2)
    assert fitness(m, Weights(task_value=0.5, value_of_time=0.002)) == pytest.approx(base - 0.2)
    assert fitness(m, Weights(task_value=0.5, value_of_time=0.001, w_coord=1.0)) == pytest.approx(base - 0.02)
    failed = dict(m, outcome="deadline", quality=0.0)
    assert fitness(failed, Weights(task_value=0.5, value_of_time=0.001)) == pytest.approx(-0.2 - 3.0 - 1.0)


# --------------------------------------------------------------------------- the evaluator

def verdict_for(policy_name, repeats=3, accuracy=1.0, cost_cv=0.1, seed=3):
    pol = _synthetic_policies(CELLS, MAX_DOCS)[policy_name]
    recs = synthetic_records(CELLS, pol, repeats, {c: accuracy for c in ("solo", "parallel", "cross")},
                             random.Random(seed), cost_cv)
    return evaluate(recs, CELLS, SETS, n_boot=300)


def test_an_ideal_policy_is_supported():
    res = verdict_for("IDEAL")
    assert res["verdict"] == "supported", res["fired"]


@pytest.mark.parametrize("policy, expected", [
    ("ALWAYS", "1_always_spawn"),
    ("NEVER", "2_never_spawn"),
    ("SPAWN_IFF_URGENT", "3a_within_regime"),
    ("SPAWN_IFF_MULTIDOC", "3b_twin"),
    ("SPAWN_IFF_MULTIDOC", "3c_dissociation"),
    ("RANDOM", "3a_within_regime"),
])
def test_collapse_and_surface_heuristics_are_rejected_by_the_intended_criterion(policy, expected):
    res = verdict_for(policy)
    assert res["verdict"] == "not supported" and expected in res["fired"], res["fired"]


def test_a_policy_that_divides_correctly_but_loses_quality_is_rejected():
    ideal = _synthetic_policies(CELLS, MAX_DOCS)["IDEAL"]
    rng = random.Random(0)
    recs = synthetic_records(CELLS, ideal, 5, {c: 0.95 for c in ("solo", "parallel", "cross")}, rng, 0.1)
    for r in recs:  # developmental answers 30 points worse than everyone else
        if r["mode"] == "developmental" and rng.random() < 0.3 and r["quality"] == 1.0:
            r["quality"], r["fitness"] = 0.0, r["fitness"] - 1.0
    res = evaluate(recs, CELLS, SETS, n_boot=300)
    assert "4b_quality_loss_vs_single" in res["fired"]


def test_validity_flags_missing_runs_and_failed_manipulation_check():
    ideal = _synthetic_policies(CELLS, MAX_DOCS)["IDEAL"]
    recs = synthetic_records(CELLS, ideal, 3, {c: 1.0 for c in ("solo", "parallel", "cross")}, random.Random(1), 0.1)
    planned = {m: 3 * len(CELLS) for m in ("single", "central", "router", "developmental")}
    ok = validity(recs, CELLS, planned, 3, audit_ok=True, frozen_ok=True)
    assert ok["valid"], ok
    dropped = [r for r in recs if not (r["mode"] == "single" and r["task_id"] == "T01")]
    assert not validity(dropped, CELLS, planned, 3, audit_ok=True, frozen_ok=True)["iv_completion"]
    swapped = [dict(r, mode={"single": "central", "central": "single"}.get(r["mode"], r["mode"])) for r in recs]
    assert not validity(swapped, CELLS, planned, 3, audit_ok=True, frozen_ok=True)["v_manipulation_check"]


# --------------------------------------------------------------------------- the frozen calibration

def test_frozen_calibration_still_verifies():
    """Changing the world, prices, prompts or runtime changes the calibration; then a re-freeze is required."""
    assert FROZEN["calibration"]["gate"]["passed"]
    assert verify_frozen(FROZEN) == []
    assert json.dumps(FROZEN["calibration"]["gate"]["sets"]["P"]) and FROZEN["R"] >= 3
