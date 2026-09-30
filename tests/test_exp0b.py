"""Experiment 0b (SPEC_0B.md): the reproducible bootstrap (amendment 0b-0), the 0b configuration path, and the frozen
0b calibration. Experiment 0 must stay exactly as it was."""

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from devagents.config import (EXPERIMENTS, FROZEN_PATH, SPEC_PATH, Constants, default_constants, exp0b_constants,
                              load_frozen, sha256_file)
from devagents.evals.analysis import contrast_ci, criteria_check, evaluate, Runs, synthetic_records

ROOT = Path(__file__).resolve().parents[1]
EXP0_FROZEN_SHA = "910bf2020f2fd62b7c94e9ca0ee504a16a9abb82a4a54635c04632192dfbb6f9"  # provisional; never to change
FROZEN_0B = load_frozen(EXPERIMENTS["0b"].frozen)


def synthetic(cells, seed=1, repeats=3):
    import random
    return synthetic_records(cells, lambda c, rng: "div" if c["label"] == "P" else "solo", repeats,
                             {"solo": 0.9, "parallel": 0.9, "cross": 0.9}, random.Random(seed))


# --------------------------------------------------------------------------- amendment 0b-0: reproducible bootstrap

def test_the_bootstrap_does_not_depend_on_the_order_cells_are_given_in():
    cells = FROZEN_0B["calibration"]["cells"]
    runs = Runs(synthetic(cells), cells)
    keys = sorted(cells)
    a = contrast_ci(runs, keys, "single", n_boot=300)
    b = contrast_ci(runs, list(reversed(keys)), "single", n_boot=300)
    c = contrast_ci(runs, set(keys), "single", n_boot=300)
    assert a == b == c and a["lo"] < a["hi"]


EVAL_SCRIPT = """
import json, random
from devagents.config import EXPERIMENTS, load_frozen
from devagents.environment.tasks import TASKS
from devagents.evals.analysis import criteria_check, evaluate, synthetic_records
f = load_frozen(EXPERIMENTS["0b"].frozen)
cells, sets = f["calibration"]["cells"], f["calibration"]["gate"]["sets"]
records = synthetic_records(cells, lambda c, rng: "div" if c["label"] == "P" else "solo", 3,
                            {"solo": 0.9, "parallel": 0.9, "cross": 0.9}, random.Random(1))
ev = evaluate(records, cells, sets, n_boot=300)
cc = criteria_check(cells, sets, {t.id: t.max_doc_route for t in TASKS}, n_sims=8, n_boot=100, repeats_options=(3,))
print(json.dumps({"evaluate": ev, "criteria_check": cc}, sort_keys=True, default=str))
"""


def test_evaluation_and_criteria_check_are_invariant_to_PYTHONHASHSEED():
    outs = set()
    for seed in ("0", "1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(ROOT))
        outs.add(subprocess.run([sys.executable, "-c", EVAL_SCRIPT], env=env, cwd=ROOT, capture_output=True, text=True,
                                check=True).stdout)
    assert len(outs) == 1


# --------------------------------------------------------------------------- Experiment 0 is untouched

def test_experiment_0_keeps_its_paths_constants_and_frozen_file():
    e0 = EXPERIMENTS["0"]
    assert (e0.spec, e0.frozen, e0.results) == (SPEC_PATH, FROZEN_PATH, Path("results"))
    assert e0.constants is default_constants
    c = default_constants()
    assert {k: (r.budget_usd, r.task_value, r.value_of_time) for k, r in c.regimes.items()} == {
        "relaxed": (1.0, 0.5, 0.00005), "urgent": (1.0, 0.5, 0.0008)}
    assert sha256_file(FROZEN_PATH) == EXP0_FROZEN_SHA


# --------------------------------------------------------------------------- the Experiment 0b configuration

def test_experiment_0b_changes_exactly_the_four_monetary_constants():
    e0, e0b = default_constants(), exp0b_constants()
    assert (e0b.compute, e0b.coord, e0b.sources) == (e0.compute, e0.coord, e0.sources)  # K = 8, prices, latencies
    assert e0b.compute.max_concurrency - 1 == 8
    for name, r in e0b.regimes.items():
        assert replace(r, budget_usd=1.0, task_value=0.5, value_of_time=e0.regimes[name].value_of_time) == e0.regimes[name]
    assert {k: (r.budget_usd, r.task_value, r.value_of_time) for k, r in e0b.regimes.items()} == {
        "relaxed": (1.392, 0.696, 0.0000696), "urgent": (1.392, 0.696, 0.0011136)}


def test_experiment_0b_has_its_own_paths():
    e = EXPERIMENTS["0b"]
    assert e.frozen == ROOT / "data" / "exp0b" / "frozen.json" and e.spec == ROOT / "SPEC_0B.md"
    assert e.results == Path("results") / "exp0b" and e.constants is exp0b_constants
    assert len({x.frozen for x in EXPERIMENTS.values()}) == len({x.results for x in EXPERIMENTS.values()}) == 2


def test_manifests_record_their_experiment_and_its_spec():
    from devagents.environment.tasks import TASKS
    from devagents.evals.experiment import make_manifest, plan
    c = exp0b_constants()
    configs = plan(TASKS[:1], c, ["single"], 1)
    m = make_manifest("main", configs, c, False, "x", experiment="0b")
    assert m["experiment"] == "0b" and m["spec_sha"] == sha256_file(EXPERIMENTS["0b"].spec)
    assert make_manifest("main", configs, c, False, "x")["spec_sha"] == sha256_file(SPEC_PATH)


# --------------------------------------------------------------------------- the committed 0b freeze

def test_the_0b_freeze_verifies_and_is_the_preregistered_one():
    from devagents.evals.calibrate import Assumptions
    from devagents.evals.experiment import verify_frozen
    f = FROZEN_0B
    assert f["experiment"] == "0b" and not f["provisional"]
    assert verify_frozen(f) == []
    adjusted = exp0b_constants()
    adjusted = replace(adjusted, compute=replace(adjusted.compute, min_step_tokens=256))
    assert Constants.from_json(f["constants"]) == adjusted  # 0b constants; pilot adjustments leave the deadline at 1500
    assert Assumptions(**f["assumptions"]) == Assumptions(input_scale=2.0052, reasoning_tokens=36)
    assert f["repair_steps"] == {"doc_per_token": 0, "urgent_vot": 0, "relaxed_vot": 0} and f["R"] == 3
    labels = [c["label"] for c in f["calibration"]["cells"].values()]
    assert (labels.count("S"), labels.count("P"), labels.count("ambiguous")) == (23, 4, 3)
    sizes = {k: len(v) for k, v in f["calibration"]["gate"]["sets"].items()}
    assert (sizes["S_urgent"], sizes["P_urgent"], sizes["twin"], sizes["D_urgent"], sizes["I"]) == (8, 4, 8, 3, 0)
    assert f["spec_sha"] == sha256_file(EXPERIMENTS["0b"].spec) and f["base_spec_sha"] == sha256_file(SPEC_PATH)


def test_run_and_report_refuse_a_frozen_file_or_suite_from_the_other_experiment(tmp_path):
    from devagents.__main__ import main
    from devagents.evals.experiment import frozen_constants
    assert frozen_constants("0b")[0]["experiment"] == "0b"
    (tmp_path / "manifest.json").write_text(json.dumps({"experiment": "0b"}))
    with pytest.raises(SystemExit, match="Experiment 0b"):
        main(["report", str(tmp_path), "--experiment", "0"])


def test_a_0b_suite_reports_as_experiment_0b(tmp_path):
    from devagents.agents.policies import LLMPolicy
    from devagents.environment.tasks import TASKS_BY_ID
    from devagents.evals.experiment import make_manifest, plan, run_suite
    from devagents.evals.report import build_report, format_markdown
    from tests.test_llm_pipeline import FakeClient, FakeModel
    c = exp0b_constants()
    configs = plan([TASKS_BY_ID["T02"]], c, ["single", "developmental"], 1, regimes=["urgent"])
    run_suite(configs, LLMPolicy(c.compute, client=FakeClient(FakeModel())), c, tmp_path,
              make_manifest("test", configs, c, True, "", experiment="0b"))
    starts = [json.loads(line) for p in (tmp_path / "events").glob("*.jsonl") for line in p.read_text().splitlines()
              if '"RUN_STARTED"' in line]
    assert {s["audit"]["regime"]["budget_usd"] for s in starts} == {1.392}
    rep = build_report(tmp_path, FROZEN_0B, frozen_ok=False, n_boot=50)
    assert rep["experiment"] == "0b" and "# Experiment 0b report" in format_markdown(rep)
