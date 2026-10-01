"""Experiment 0c (SPEC_0C.md): treatment identity, the scripted `central`, the pre-registration, the pilot and Stage 1
rules, result isolation, and the fake-client pipeline. No network and no API are used."""

import copy
import hashlib
import json
import re
import threading
from dataclasses import asdict
from pathlib import Path

import pytest

from devagents.agents.policies import LLMPolicy, ScriptedPolicy, action_schema
from devagents.agents.scripted_central import ScriptedFirstSpawnPolicy
from devagents.config import EXPERIMENTS, ROOT, Constants, load_frozen, sha256_file
from devagents.environment.sources import InformationEnvironment
from devagents.environment.tasks import TASKS_BY_ID
from devagents.environment.world import load_world
from devagents.evals import exp0c as X
from devagents.evals.analysis import THRESHOLD_COLLAPSE
from devagents.evals.report import audit_parity
from devagents.runtime.resources import estimate_tokens
from devagents.runtime.runtime import ALL_ACTIONS, Run, RunConfig, policy_config
from tests.test_llm_pipeline import Block, Response, Usage, _chars

PREREG, PREREG_SHA = X.load_prereg()
FROZEN_0B = load_frozen(EXPERIMENTS["0b"].frozen)
CONSTANTS = Constants.from_json(FROZEN_0B["constants"])
STATUS_BEFORE_0C = (16586, "9cd5f7d1eb7f857c3429911aac58190f288fbfdf08c15aed45a0df6a8b502686")  # at 931a7c1
ACTION_SCHEMA_SHA = "29d3cdc5254105b64e0ce2d0c3459c0a5761a4d0c489bfd988bc0a9ef48d9b48"
PILOT_STATS_SHA = "f987fc1818f0ff4364385cfef7aadd589e0b4fef520141ce3f6ad14f81677129"


class ModeAwareModel:
    """A fake Anthropic client model that reads the MODE RULES line as a model would. `single` and (by default)
    `developmental` read every document in one QUERY; with `divide`, `developmental` splits the documents across two
    children. Children read the documents named in their objective (or none, with child_reads="none").
    `central_answer` replaces the central root's answer (to make the realized manipulation fail)."""

    def __init__(self, divide=False, central_answer=None, child_reads="assigned"):
        self.divide, self.central_answer, self.child_reads = divide, central_answer, child_reads
        self.requests = []
        self.lock = threading.Lock()

    def create(self, **kw):
        with self.lock:
            self.requests.append(copy.deepcopy(kw))
        system, first = kw["system"], kw["messages"][0]["content"]
        step = sum(1 for m in kw["messages"] if m["role"] == "assistant")
        if first.startswith("Task "):
            task = TASKS_BY_ID[re.match(r"Task (\w+)\.", first).group(1)]
            docs = list(task.routes[0].docs)
            if step == 0 and self.divide and "You may SPAWN at any step" in system:
                action = {"rationale": "split", "action": "SPAWN", "wait_for_children": True,
                          "children": [{"objective": f"Read {' '.join(h)} for: {task.question}", "context": "",
                                        "budget_usd": 0.2, "lifetime_s": 600} for h in (docs[0::2], docs[1::2])]}
            elif step == 0:
                action = {"rationale": "Read all the documents in one query.", "action": "QUERY",
                          "requests": [{"kind": "doc", "target": d} for d in docs]}
            else:
                central = "Your first action must be SPAWN" in system
                answer = self.central_answer if central and self.central_answer is not None else task.answer
                action = {"rationale": "answer", "action": "TERMINATE", "answer": answer}
        else:
            named = re.findall(r"(?:region|supplier)-[a-z]+", first.split("Context from")[0])
            if step == 0 and named and self.child_reads != "none":
                action = {"rationale": "read", "action": "QUERY", "requests": [{"kind": "doc", "target": d} for d in named]}
            else:
                action = {"rationale": "report", "action": "TERMINATE", "answer": "the facts I found"}
        text = json.dumps(action)
        return Response([Block(text)], Usage(_chars(kw) // 4 + 5, estimate_tokens(text) + 40))


class Client:
    def __init__(self, model):
        self.messages = model


def factory(model):
    return lambda constants: LLMPolicy(constants.compute, client=Client(model))


# --------------------------------------------------------------------------- 0 and 0b untouched; the status record

def test_experiment_0_and_0b_artefacts_are_byte_unchanged():
    assert X.sha256_lf(EXPERIMENTS["0"].frozen) == X.EXP0_FROZEN_SHA
    assert X.sha256_lf(EXPERIMENTS["0b"].frozen) == X.EXP0B_FROZEN_SHA
    assert X.sha256_lf(ROOT / "data" / "exp0b" / "pilot_stats.json") == PILOT_STATS_SHA
    assert FROZEN_0B["spec_sha"] == X.sha256_lf(EXPERIMENTS["0b"].spec)
    assert FROZEN_0B["base_spec_sha"] == X.sha256_lf(EXPERIMENTS["0"].spec)
    assert set(EXPERIMENTS) == {"0", "0b"}  # 0c is never a generic `run`/`report`/`freeze` experiment
    assert (EXPERIMENTS["0"].results, EXPERIMENTS["0b"].results) == (Path("results"), Path("results") / "exp0b")


def test_the_0b_main_run_record_is_appended_and_history_is_untouched():
    data = (ROOT / "EXPERIMENT_STATUS.md").read_bytes().replace(b"\r\n", b"\n")  # as committed (LF)
    n, sha = STATUS_BEFORE_0C
    assert hashlib.sha256(data[:n]).hexdigest() == sha  # append-only: the earlier record is byte-identical
    entry = data[n:].decode("utf-8")
    for needed in ("Experiment 0b main run completed", "360/360", "0 infrastructure failures", X.EXP0B_FROZEN_SHA,
                   "UNINFORMATIVE", "(v)", "FAILED", "0.2830", "0.3552", "zero SPAWN attempts", "exactly one child",
                   "do not override or retrospectively change the verdict",
                   "44da120e65f3cb391e85a911e637d8a495ebf298", "931a7c1e9138436aa960140611aab1b81c4cc9cc"):
        assert needed in entry, needed


# --------------------------------------------------------------------------- treatment identity

def test_constants_model_effort_and_economics_are_0bs():
    assert X.constants_0c(FROZEN_0B) == CONSTANTS
    want = {"class": "LLMPolicy", "structured": True, "model": CONSTANTS.compute.model, "effort": "low"}
    assert X.expected_policy_config(CONSTANTS) == want
    t = PREREG["treatment"]
    assert t["policy_config_sha"] == X.sha256_json(want) and (t["policy_class"], t["structured"], t["effort"]) == (
        "LLMPolicy", True, "low")
    assert PREREG["constants_sha"] == X.sha256_json(FROZEN_0B["constants"])
    r = CONSTANTS.regimes
    assert {k: (v.budget_usd, v.task_value, v.value_of_time) for k, v in r.items()} == {
        "relaxed": (1.392, 0.696, 0.0000696), "urgent": (1.392, 0.696, 0.0011136)}
    assert CONSTANTS.compute.max_concurrency - 1 == 8


def test_developmental_prompt_fingerprint_mode_rules_and_schema_are_0bs():
    t = PREREG["treatment"]
    assert X.prompt_fingerprint(CONSTANTS) == FROZEN_0B["prompt_sha"] == X.EXP0B_PROMPT_SHA == t["prompt_fingerprint"]
    assert X.sha256_json(action_schema(ALL_ACTIONS)) == ACTION_SCHEMA_SHA == t["action_schema_sha"]
    assert t["developmental_mode_rules"] == "MODE RULES: You may SPAWN at any step; agents you create may also SPAWN."
    fresh = X.treatment_identity(CONSTANTS)
    assert fresh == t  # full developmental system prompts, briefs, MODE RULES and action help, per cell


def test_developmental_and_single_send_byte_identical_requests_through_the_wrapper(tmp_path):
    """The wrapper delegates every non-central step unchanged: the API requests are identical with and without it."""
    info = InformationEnvironment(load_world(), CONSTANTS.sources)
    for mode in ("developmental", "single"):
        sent = []
        for wrap in (False, True):
            model = ModeAwareModel(divide=True)
            inner = LLMPolicy(CONSTANTS.compute, client=Client(model))
            policy = X.scripted_policy(inner, PREREG) if wrap else inner
            cfg = RunConfig(TASKS_BY_ID["T01"], CONSTANTS.regimes["urgent"], mode, compute=CONSTANTS.compute,
                            coord=CONSTANTS.coord)
            run = Run(cfg, policy, info)
            run.execute()
            sent.append(json.dumps(model.requests, sort_keys=True, default=vars))
            assert not any(e["type"] == "SCRIPTED_ACTION" for e in run.log.events)
        assert sent[0] == sent[1], mode


def test_policy_configuration_differs_only_by_the_declared_entry_in_central():
    inner = LLMPolicy(CONSTANTS.compute, client=Client(ModeAwareModel()))
    wrapped = X.scripted_policy(inner, PREREG)
    base = policy_config(inner)
    assert base == {"class": "LLMPolicy", "structured": True, "model": CONSTANTS.compute.model, "effort": "low"}
    assert policy_config(inner, "central") == base  # existing policies are unaffected by the mode
    for mode in ("single", "developmental", "router", None):
        assert policy_config(wrapped, mode) == base
    assert policy_config(wrapped, "central") == {**base, "central_first_step": "scripted"}


# --------------------------------------------------------------------------- the scripted topology

EXPECTED_PARTITIONS = {
    "regions": [["region-northland", "region-westreach"], ["region-eastmarch", "region-midlands"],
                ["region-southvale", "region-coastal"]],
    "suppliers": [["supplier-brisk", "supplier-fenwright"], ["supplier-calloway", "supplier-galloway"],
                  ["supplier-dunmore", "supplier-harrow"], ["supplier-eskerfield", "supplier-ivel"]],
}


@pytest.mark.parametrize("cell,k,kind", [("X2|urgent", 3, "regions"), ("T01|urgent", 3, "regions"),
                                         ("T04|urgent", 4, "suppliers"), ("T07|urgent", 3, "regions"),
                                         ("T10|urgent", 4, "suppliers")])
def test_scripted_central_has_the_predeclared_k_and_exact_partition(cell, k, kind):
    topo = X.topology(cell, FROZEN_0B, CONSTANTS)
    assert topo == PREREG["scripted_central"][cell]
    assert topo["k"] == k == X.PREDECLARED_K[cell] and topo["org"] == f"fanout{k}@r0"
    assert topo["partition"] == EXPECTED_PARTITIONS[kind]
    task = TASKS_BY_ID[cell.split("|")[0]]
    assert topo["partition"] == [list(task.routes[0].docs[i::k]) for i in range(k)]
    a = topo["action"]
    assert a["action"] == "SPAWN" and a["wait_for_children"] is True and a["rationale"] == "Split the work across agents."
    assert [c["objective"] for c in a["children"]] == [
        f"Find the facts needed for: {task.question} Read only the sources named in this objective: " + "; ".join(p)
        for p in EXPECTED_PARTITIONS[kind]]
    assert all(c["context"] == "" for c in a["children"])


def test_topologies_come_from_pre_existing_artefacts():
    for cell in X.STAGE1.cells:  # the 0b freeze's router_div, never a new search
        assert PREREG["scripted_central"][cell]["org"] == FROZEN_0B["calibration"]["cells"][cell]["router_div"]
    assert "X2|urgent" not in FROZEN_0B["calibration"]["cells"]  # held out: derived by the unchanged calibration rule
    org, source = X.derive_org("X2|urgent", FROZEN_0B, CONSTANTS)
    assert org.name == "fanout3@r0" and "calibrate.label" in source
    memo = (ROOT / "EXPERIMENT_0C_DECISION.md").read_text(encoding="utf-8")
    assert "k = 3, X2's best fan-out at 0b constants" in memo  # pre-declared before any 0c code existed


def test_a_disagreeing_derivation_stops_instead_of_changing_the_design(monkeypatch):
    monkeypatch.setitem(X.PREDECLARED_K, "T01|urgent", 4)
    with pytest.raises(SystemExit, match="STOP"):
        X.topology("T01|urgent", FROZEN_0B, CONSTANTS)


def test_objectives_use_t0_information_only_and_the_check_catches_leaks():
    info = InformationEnvironment(load_world(), CONSTANTS.sources)
    for topo in PREREG["scripted_central"].values():
        assert X.t0_problems(topo, info) == []
    base = copy.deepcopy(PREREG["scripted_central"]["T10|urgent"])
    doc_line = next(l.strip() for l in info.world.docs["supplier-galloway"].splitlines() if len(l.strip()) >= 25)
    for leak in (" Answer: Galloway Fasteners", " SELECT name FROM suppliers", " " + doc_line):
        bad = copy.deepcopy(base)
        bad["objectives"][0] += leak
        assert X.t0_problems(bad, info), leak
    bad = copy.deepcopy(base)
    bad["contexts"][1] = "founded in 1931"
    assert X.t0_problems(bad, info)
    bad = copy.deepcopy(base)
    bad["partition"][0], bad["partition"][1] = bad["partition"][1], bad["partition"][0]
    assert X.t0_problems(bad, info)


def _offline_central(cell, asm=None):
    asm = asm or X.frozen_assumptions(FROZEN_0B)
    topo = PREREG["scripted_central"][cell]
    task, regime = TASKS_BY_ID[topo["task"]], CONSTANTS.regimes["urgent"]
    org = X._parse_org(topo["org"])
    policy = ScriptedFirstSpawnPolicy(X._oracle(task, org, asm), {topo["task"]: topo["action"]}, 2.0052, 36)
    run = Run(RunConfig(task, regime, "central", compute=CONSTANTS.compute, coord=CONSTANTS.coord), policy,
              InformationEnvironment(load_world(), CONSTANTS.sources))
    run.execute()
    return topo, regime, run.log.events


@pytest.mark.parametrize("cell", ["X2|urgent", "T01|urgent", "T04|urgent", "T07|urgent", "T10|urgent"])
def test_allocation_lifetime_fees_caps_and_reserves_are_exact(cell):
    topo, regime, events = _offline_central(cell)
    assert X.mechanics_problems(topo, events, CONSTANTS, regime) == []
    assert X.central_integrity(events, topo)["intact"]


def test_the_mechanics_check_catches_a_wrong_allocation_or_lifetime():
    topo, regime, events = _offline_central("T04|urgent")
    bad = copy.deepcopy(events)
    next(e for e in bad if e["type"] == "RESOURCE_ALLOCATED" and e["kind"] == "allocation")["amount"] -= 1
    assert any("allocations" in p for p in X.mechanics_problems(topo, bad, CONSTANTS, regime))
    bad = copy.deepcopy(events)
    next(e for e in bad if e["type"] == "AGENT_CREATED" and e["parent"] == "A0")["deadline"] += 1.0
    assert any("lifetimes" in p for p in X.mechanics_problems(topo, bad, CONSTANTS, regime))


def test_the_mechanics_and_integrity_checks_catch_a_missing_child():
    topo, regime, events = _offline_central("T10|urgent")
    bad = [e for e in events if not (e["type"] == "AGENT_SPAWNED" and e["child"] == "A0.4")]
    assert any("3 children instead of 4" in p for p in X.mechanics_problems(topo, bad, CONSTANTS, regime))
    integrity = X.central_integrity(bad, topo)
    assert not integrity["exact_k_children"] and not integrity["intact"]


def test_the_scripted_step_is_charged_exactly_as_the_calibration_prices_an_oracle_step():
    """Same events as the all-scripted oracle fan-out in central mode, apart from the explicit SCRIPTED_ACTION."""
    topo, regime, events = _offline_central("T01|urgent")
    task, org = TASKS_BY_ID["T01"], X._parse_org(topo["org"])
    plain = Run(RunConfig(task, regime, "central", compute=CONSTANTS.compute, coord=CONSTANTS.coord),
                X._oracle(task, org, X.frozen_assumptions(FROZEN_0B)), InformationEnvironment(load_world(), CONSTANTS.sources))
    plain.execute()
    strip = lambda evs: [{k: v for k, v in e.items() if k not in ("wall", "seq", "policy")}
                         for e in evs if e["type"] != "SCRIPTED_ACTION"]
    assert strip(events) == strip(plain.log.events)  # every charge, latency, allocation and outcome is identical
    assert events[0]["policy"]["central_first_step"] == "scripted"
    scripted = [e for e in events if e["type"] == "SCRIPTED_ACTION"]
    llm = [e for e in events if e["type"] == "RESOURCE_CONSUMED" and e["kind"] == "llm" and e["agent"] == "A0"]
    assert len(scripted) == 1 and scripted[0]["seq"] < llm[0]["seq"] and llm[0]["amount"] > 0
    assert (scripted[0]["input_scale"], scripted[0]["reasoning_tokens"]) == (2.0052, 36)


# --------------------------------------------------------------------------- audit parity: only the declared difference

def _starts(**central_policy):
    base = {"class": "LLMPolicy", "structured": True, "model": "m", "effort": "low"}
    out = []
    for mode in ("single", "central", "developmental"):
        policy = dict(base, **(central_policy if mode == "central" else {}))
        out.append({"run_id": f"T01-urgent-{mode}-r0", "task_id": "T01", "regime": "urgent", "repeat": 0, "mode": mode,
                    "audit": {"frozen_sha": "f"}, "prompt_sha": "p", "policy": policy})
    return out


def test_the_declared_central_asymmetry_passes_and_nothing_else_does():
    declared = X.DECLARED_ASYMMETRIES
    assert audit_parity(_starts(central_first_step="scripted"), "f", declared)[0]
    assert not audit_parity(_starts(central_first_step="scripted"), "f")[0]  # undeclared: parity unchanged
    assert not audit_parity(_starts(), "f", declared)[0]  # central lacks its declared entry
    assert not audit_parity(_starts(central_first_step="llm"), "f", declared)[0]
    assert not audit_parity(_starts(central_first_step="scripted", effort="high"), "f", declared)[0]
    assert not audit_parity(_starts(central_first_step="scripted", model="other"), "f", declared)[0]
    s = _starts(central_first_step="scripted")
    s[2]["policy"]["central_first_step"] = "scripted"  # the entry in an undeclared mode is drift
    assert not audit_parity(s, "f", declared)[0]
    s = _starts(central_first_step="scripted")
    s[2]["prompt_sha"] = "q"
    assert not audit_parity(s, "f", declared)[0]


# --------------------------------------------------------------------------- the suites

def test_the_pilot_is_exactly_4_runs_and_stage1_exactly_36_on_the_p_urgent_cells():
    p, s = PREREG["pilot"], PREREG["stage1"]
    assert p["n_runs"] == 4 and sorted(p["planned_runs"]) == sorted(
        f"X2-urgent-{m}-r{r}" for m in ("single", "central") for r in range(2))
    assert s["n_runs"] == 36 and s["repeats"] == 3
    assert s["cells"] == ["T01|urgent", "T04|urgent", "T07|urgent", "T10|urgent"]
    assert sorted(s["cells"]) == sorted(FROZEN_0B["calibration"]["gate"]["sets"]["P_urgent"])
    assert sorted(s["modes"]) == ["central", "developmental", "single"]
    assert {r.split("-")[2] for r in s["planned_runs"]} == {"single", "central", "developmental"}
    assert {(r.split("-")[0], r.split("-")[1]) for r in s["planned_runs"]} == {
        (c.split("|")[0], "urgent") for c in s["cells"]}
    assert not set(p["planned_runs"]) & set(s["planned_runs"])
    for stage in (X.PILOT, X.STAGE1):
        assert [c.run_id for c in X.configs_for(stage, CONSTANTS, X.EXP0B_FROZEN_SHA)] == PREREG[stage.name]["planned_runs"]


def test_isolated_paths_and_output_guard(monkeypatch, tmp_path):
    assert X.PREREG_PATH == ROOT / "data" / "exp0c" / "prereg.json"
    assert X.PILOT.results == Path("results/exp0c/pilot") and X.STAGE1.results == Path("results/exp0c/stage1")
    assert X.PREREG_PATH not in {e.frozen for e in EXPERIMENTS.values()}
    monkeypatch.chdir(tmp_path)  # paths are anchored at the repository, not the working directory
    for bad in ("results/pilot", "results/exp0b/main", "results/main", "results/exp0c/stage1", "results/exp0c",
                "results/exp0c/pilot/../stage1"):
        assert X._forbidden_out(ROOT / bad, X.PILOT), bad
    assert not X._forbidden_out(ROOT / "results/exp0c/pilot", X.PILOT)
    assert X._forbidden_out(ROOT / "results/exp0c/pilot", X.STAGE1)
    assert not X._forbidden_out(tmp_path / "elsewhere", X.PILOT)


def test_the_stage0_offline_checks_all_pass():
    checks = X.stage0_checks(PREREG)
    assert all(not v for v in checks.values()), checks
    g = PREREG["offline_geometry"]["live_0b"]
    assert g["assumptions"]["input_scale"] == 2.0277 and g["assumptions"]["reasoning_tokens"] == 45
    assert g["stage1_means"] == {"single": 0.343, "central_one_child": 0.2787, "scripted_central": 0.549}
    assert PREREG["offline_geometry"]["frozen"]["stage1_means"] == {
        "single": 0.3449, "central_one_child": 0.2822, "scripted_central": 0.554}


def test_a_windows_crlf_checkout_hashes_as_committed(tmp_path):
    """Git for Windows checks text files out with CRLF by default; the pre-registration's hashes must not change."""
    for src in (X.SPEC_PATH, X.DECISION_MEMO, EXPERIMENTS["0b"].frozen, EXPERIMENTS["0"].frozen, X.PREREG_PATH):
        lf = src.read_bytes().replace(b"\r\n", b"\n")  # whatever this checkout's line endings are
        crlf = tmp_path / src.name
        crlf.write_bytes(lf.replace(b"\n", b"\r\n"))
        assert crlf.read_bytes() != lf and X.sha256_lf(crlf) == X.sha256_lf(src) == hashlib.sha256(lf).hexdigest()
    assert PREREG["spec_sha"] == X.sha256_lf(X.SPEC_PATH) and PREREG["source_freeze"]["sha"] == X.EXP0B_FROZEN_SHA


def test_a_changed_spec_invalidates_the_preregistration():
    tampered = dict(PREREG, spec_sha="0" * 64)
    assert any("spec_sha" in p for p in X.verify_prereg(tampered))


# --------------------------------------------------------------------------- the pilot rule

def _central_integrity(**fail):
    ok = {"scripted_spawn_accepted": True, "exact_k_children": True, "exact_partition": True, "no_child_starved": True,
          "no_runtime_termination_before_task": True, "every_child_queried_its_assignment": True,
          "children_reading_outside_assignment": 0, "intact": True,
          "children": [{"id": f"A0.{i + 1}", "assigned": [], "queried": [], "read_assignment": True,
                        "read_outside_assignment": [], "reason": "completed"} for i in range(3)]}
    for k, v in fail.items():
        ok[k] = v
    if any(fail.get(k) is False for k in ("scripted_spawn_accepted", "exact_k_children", "exact_partition",
                                          "no_child_starved", "no_runtime_termination_before_task")):
        ok["intact"] = False
    if fail.get("every_child_queried_its_assignment") is False:
        ok["children"][0]["read_assignment"] = False
    return ok


def _run(cell, mode, rep, fitness, quality=1.0, parallel=None, spawned=None, cap_hits=0, outcome="answered",
         integrity=None, identity=()):
    task = cell.split("|")[0]
    rec = {"run_id": f"{task}-urgent-{mode}-r{rep}", "task_id": task, "regime": "urgent", "cell": cell, "mode": mode,
           "repeat": rep, "fitness": fitness, "quality": quality, "outcome": outcome, "cap_hits": cap_hits,
           "parallel": mode == "central" if parallel is None else parallel,
           "spawned": mode == "central" if spawned is None else spawned, "money_usd": 0.1, "elapsed_s": 100.0,
           "children": 3 if mode == "central" else 0, "agents": 4 if mode == "central" else 1, "api_calls": 2,
           "components": {"quality": quality, "money": -0.1, "time": -fitness}, "identity_problems": list(identity)}
    if mode == "central":
        rec["integrity"] = integrity or _central_integrity()
    return rec


def pilot_data(central_fit=0.55, single_fit=0.35, **central_fail):
    runs = [_run("X2|urgent", m, r, central_fit if m == "central" else single_fit,
                 integrity=_central_integrity(**central_fail) if m == "central" else None)
            for m in ("single", "central") for r in range(2)]
    return {"planned": PREREG["pilot"]["planned_runs"], "runs": runs, "parity_problems": [], "manifest_problems": [],
            "infra_errors": {}}


def test_the_pilot_passes_only_when_integrity_and_manipulation_both_hold():
    assert X.pilot_decision(pilot_data())["verdict"] == "PASS"
    assert X.pilot_decision(pilot_data(central_fit=0.35))["verdict"] == "FAIL"  # equal means: strict >
    assert X.pilot_decision(pilot_data(central_fit=0.3))["verdict"] == "FAIL"
    for cond in ("scripted_spawn_accepted", "exact_k_children", "exact_partition", "no_child_starved",
                 "no_runtime_termination_before_task", "every_child_queried_its_assignment"):
        d = X.pilot_decision(pilot_data(**{cond: False}))
        assert d["verdict"] == "FAIL" and not d["A_instrument_integrity"], cond
    data = pilot_data()
    data["runs"][3]["cap_hits"] = 1
    assert X.pilot_decision(data)["verdict"] == "FAIL"
    data = pilot_data()
    data["runs"][3]["outcome"] = "deadline"
    assert X.pilot_decision(data)["verdict"] == "FAIL"
    data = pilot_data()
    data["runs"].pop(0)  # a missing run: no second pilot, the pilot fails
    assert X.pilot_decision(data)["verdict"] == "FAIL"
    data = pilot_data()
    data["runs"][0]["identity_problems"] = ["drift"]
    assert X.pilot_decision(data)["verdict"] == "FAIL"


# --------------------------------------------------------------------------- the Stage 1 rule

CELLS_0B = FROZEN_0B["calibration"]["cells"]


def stage1_data(parallel_runs=0, central_fit=0.55, single_fit=0.35, single_wrong=0, single_caps=0, non_intact=0,
                drop=(), spawned_not_parallel=0):
    runs = []
    for r in range(3):
        for cell in X.STAGE1.cells:
            runs.append(_run(cell, "single", r, single_fit))
            runs.append(_run(cell, "central", r, central_fit))
            runs.append(_run(cell, "developmental", r, 0.35, parallel=False, spawned=False))
    dev = [x for x in runs if x["mode"] == "developmental"]
    for x in dev[:parallel_runs]:
        x["parallel"] = x["spawned"] = True
    for x in dev[parallel_runs:parallel_runs + spawned_not_parallel]:
        x["spawned"] = True  # spawned, but no overlapping source processing
    single = [x for x in runs if x["mode"] == "single"]
    for x in single[:single_wrong]:
        x["quality"] = 0.0
    for x in single[:single_caps]:
        x["cap_hits"] = 1
    for x in [x for x in runs if x["mode"] == "central"][:non_intact]:
        x["integrity"] = _central_integrity(exact_k_children=False)
    runs = [x for x in runs if x["run_id"] not in drop]
    return {"planned": PREREG["stage1"]["planned_runs"], "runs": runs, "parity_problems": [], "manifest_problems": []}


def verdict(**kw):
    return X.stage1_decision(stage1_data(**kw), CELLS_0B)


def test_criterion_2_threshold_is_exactly_one_half_on_parallel():
    assert THRESHOLD_COLLAPSE == 0.50 == X.RULES["stage1"]["criterion2_threshold"]
    assert X.RULES["stage1"]["criterion2_indicator"] == "parallel"
    assert verdict(parallel_runs=5)["verdict"] == "NO-GO"
    assert verdict(parallel_runs=6)["verdict"] == "GO"
    assert verdict(parallel_runs=0)["verdict"] == "NO-GO"
    assert verdict(parallel_runs=12)["verdict"] == "GO"
    d = verdict(parallel_runs=5)
    assert d["message"] == X.CRITERION2_MESSAGE and d["steps"][-1]["parallel_rate_P"] == pytest.approx(5 / 12)
    for banned in ("refuted", "do not work"):
        assert banned not in d["message"]


def test_criterion_2_counts_parallel_division_not_spawning():
    d = verdict(parallel_runs=5, spawned_not_parallel=7)  # 12 spawned, only 5 parallel
    assert d["verdict"] == "NO-GO" and d["steps"][-1]["spawned_runs_descriptive"] == 12


def test_go_stops_and_launches_nothing(monkeypatch):
    monkeypatch.setattr(X, "run_suite_0c", lambda *a, **k: pytest.fail("evaluation must never launch runs"))
    d = verdict(parallel_runs=6)
    assert d["verdict"] == "GO" and "Stop here" in d["message"] and "explicit user approval" in d["message"]
    from devagents.__main__ import main
    with pytest.raises(SystemExit):
        main(["exp0c", "stage2"])  # there is no Stage 2 command


def test_completion_rule_is_exact():
    ids = PREREG["stage1"]["planned_runs"]
    one_dev = [i for i in ids if "developmental" in i][:1]
    two_dev = [i for i in ids if "developmental" in i and ("T01" in i or "T04" in i)][:2]
    same_cell = [i for i in ids if i.startswith("T07-urgent-single")][:2]
    assert verdict(parallel_runs=0, drop=one_dev)["verdict"] == "NO-GO"  # 11/12 >= 90%, every cell >= 2
    assert verdict(drop=two_dev)["verdict"] == "UNINFORMATIVE"  # 10/12 < 90%
    assert verdict(drop=same_cell)["verdict"] == "UNINFORMATIVE"  # a cell with 1 run
    assert verdict(drop=two_dev)["steps"][0]["step"] == "completion"


def test_the_per_cell_minimum_is_enforced_on_its_own(monkeypatch):
    """With R = 3 the 90%-per-mode rule already implies >= 2 runs per cell; check the per-cell rule in isolation."""
    monkeypatch.setitem(X.RULES["stage1"], "completion_min_fraction_per_mode", 0.0)
    same_cell = [i for i in PREREG["stage1"]["planned_runs"] if i.startswith("T07-urgent-single")]
    assert verdict(drop=same_cell[:1])["verdict"] == "NO-GO"
    d = verdict(drop=same_cell[:2])
    assert d["verdict"] == "UNINFORMATIVE" and d["steps"][0]["per_cell_mode"]["T07|urgent/single"] == 1


def test_treatment_identity_drift_is_uninformative():
    data = stage1_data(parallel_runs=12)
    data["runs"][5]["identity_problems"] = ["model differs"]
    assert X.stage1_decision(data, CELLS_0B)["verdict"] == "UNINFORMATIVE"
    for key in ("parity_problems", "manifest_problems"):
        data = stage1_data(parallel_runs=12)
        data[key] = ["drift"]
        assert X.stage1_decision(data, CELLS_0B)["verdict"] == "UNINFORMATIVE"


def test_single_validity_rule_is_exact():
    assert verdict(single_wrong=3)["verdict"] == "NO-GO"  # 9/12 correct = 0.75
    d = verdict(single_wrong=4)  # 8/12
    assert d["verdict"] == "UNINFORMATIVE" and d["steps"][-1]["step"] == "single_validity"
    assert verdict(single_caps=1)["verdict"] == "UNINFORMATIVE"  # 1/12 > 5%


def test_central_integrity_rule_is_exact():
    assert verdict(non_intact=1)["verdict"] == "NO-GO"
    d = verdict(non_intact=2)
    assert d["verdict"] == "UNINFORMATIVE" and "Implementation failure" in d["message"]


def test_child_behaviour_is_reported_not_counted_as_an_implementation_failure():
    data = stage1_data()
    for x in [x for x in data["runs"] if x["mode"] == "central"][:4]:
        x["integrity"] = _central_integrity(every_child_queried_its_assignment=False)
    d = X.stage1_decision(data, CELLS_0B)
    step = next(s for s in d["steps"] if s["step"] == "central_integrity")
    assert step["ok"] and step["non_intact"] == [] and d["verdict"] == "NO-GO"
    assert sum(v["children_not_reading_assignment"] for v in step["behaviour_reported_separately"].values()) == 4


def test_manipulation_rule_is_strict_and_reports_its_main_shortfall():
    d = verdict(central_fit=0.35, parallel_runs=12)
    assert d["verdict"] == "STOP" and "No Stage 2" in d["message"]
    assert verdict(central_fit=0.3501, parallel_runs=12)["verdict"] == "GO"
    data = stage1_data(central_fit=0.30, parallel_runs=12)
    for x in data["runs"]:
        if x["mode"] == "central":
            x["components"] = {"quality": 1.0, "money": -0.2, "time": -0.5}
        elif x["mode"] == "single":
            x["components"] = {"quality": 1.0, "money": -0.1, "time": -0.55}
    d = X.stage1_decision(data, CELLS_0B)
    assert d["verdict"] == "STOP" and "money" in d["message"]


# --------------------------------------------------------------------------- the pipeline, with a fake client

def _prereg_copy(tmp_path) -> Path:
    path = tmp_path / "prereg.json"
    path.write_bytes(X.PREREG_PATH.read_bytes())
    return path


def test_stage1_cannot_run_before_a_passing_pilot(tmp_path):
    pre = _prereg_copy(tmp_path)
    built = []
    make = lambda c: built.append(1) or LLMPolicy(c.compute, client=Client(ModeAwareModel()))
    with pytest.raises(SystemExit, match="no finished X2 pilot"):
        X.run_stage("stage1", make, out=tmp_path / "s1", pilot_dir=tmp_path / "pilot", prereg_path=pre, verify=False)
    res = X.run_stage("pilot", factory(ModeAwareModel(central_answer="nobody")), out=tmp_path / "pilot",
                      prereg_path=pre, verify=False, workers=1)
    assert res["decision"]["verdict"] == "FAIL" and not res["decision"]["B_realized_manipulation"]
    assert res["decision"]["A_instrument_integrity"]
    built.clear()
    with pytest.raises(SystemExit, match="did not PASS"):
        X.run_stage("stage1", make, out=tmp_path / "s1", pilot_dir=tmp_path / "pilot", prereg_path=pre, verify=False)
    assert built == [] and not (tmp_path / "s1").exists()


def test_pilot_then_stage1_end_to_end_no_go_and_go(tmp_path):
    pre = _prereg_copy(tmp_path)
    pilot = X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False,
                        workers=1)
    d = pilot["decision"]
    assert d["verdict"] == "PASS" and d["mean_fitness"]["central"] > d["mean_fitness"]["single"]
    assert {r["mode"]: r["children"] for r in d["runs"]} == {"single": 0, "central": 3}
    assert all(all(c.values()) for c in d["central_conditions"].values())
    manifest = json.loads((tmp_path / "pilot" / "manifest.json").read_text())
    assert (manifest["experiment"], manifest["stage"], manifest["prereg_sha"]) == ("0c", "pilot", X.sha256_lf(pre))
    assert manifest["frozen_sha"] == X.EXP0B_FROZEN_SHA and manifest["declared_asymmetries"] == X.DECLARED_ASYMMETRIES
    assert (tmp_path / "pilot" / "pilot_report.md").read_text(encoding="utf-8").startswith("# Experiment 0c pilot")

    events = [json.loads(l) for l in (tmp_path / "pilot" / "events" / "X2-urgent-central-r0.jsonl").read_text().splitlines()]
    scripted = [e for e in events if e["type"] == "SCRIPTED_ACTION"]
    assert len(scripted) == 1 and scripted[0]["action"] == PREREG["scripted_central"]["X2|urgent"]["action"]
    assert next(e for e in events if e["type"] == "RUN_STARTED")["policy"]["central_first_step"] == "scripted"

    no_go = X.run_stage("stage1", factory(ModeAwareModel()), out=tmp_path / "s1", pilot_dir=tmp_path / "pilot",
                        prereg_path=pre, verify=False)
    assert no_go["summary"] == {"planned": 36, "completed": 36, "failed": 0, "exhausted": []}
    assert no_go["decision"]["verdict"] == "NO-GO" and no_go["decision"]["message"] == X.CRITERION2_MESSAGE
    assert [s["step"] for s in no_go["decision"]["steps"]] == [
        "completion", "treatment_identity", "single_validity", "central_integrity", "live_manipulation", "criterion_2"]
    assert all(s.get("ok", True) for s in no_go["decision"]["steps"][:-1])

    go = X.run_stage("stage1", factory(ModeAwareModel(divide=True)), out=tmp_path / "s1-go",
                     pilot_dir=tmp_path / "pilot", prereg_path=pre, verify=False)
    assert go["decision"]["verdict"] == "GO" and go["decision"]["steps"][-1]["parallel_rate_P"] == 1.0

    with pytest.raises(SystemExit, match="final"):  # a finished stage is never run again
        X.run_stage("stage1", factory(ModeAwareModel()), out=tmp_path / "s1", pilot_dir=tmp_path / "pilot",
                    prereg_path=pre, verify=False)
    (tmp_path / "s1" / "stage1_decision.json").unlink()  # as if interrupted before deciding: resume repeats nothing
    again = X.run_stage("stage1", factory(ModeAwareModel()), out=tmp_path / "s1", pilot_dir=tmp_path / "pilot",
                        prereg_path=pre, verify=False)
    assert again["summary"]["completed"] == 36 and len((tmp_path / "s1" / "runs.jsonl").read_text().splitlines()) == 36


def test_resume_refuses_a_different_suite_and_the_evaluator_refuses_foreign_data(tmp_path):
    pre = _prereg_copy(tmp_path)
    X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False, workers=1)
    (tmp_path / "other").mkdir()
    other = tmp_path / "other" / "prereg.json"
    prereg = json.loads(pre.read_text(encoding="utf-8"))
    prereg["created_at"] = "another pre-registration"
    other.write_text(json.dumps(prereg))
    with pytest.raises(SystemExit, match="final"):
        X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=other, verify=False)
    (tmp_path / "pilot" / "pilot_decision.json").rename(tmp_path / "decision.json")
    with pytest.raises(SystemExit, match="different suite"):
        X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=other, verify=False)
    with pytest.raises(SystemExit, match="another pre-registration"):
        X.load_stage(tmp_path / "pilot", X.PILOT, prereg, X.sha256_lf(other))
    with pytest.raises(SystemExit, match="stage 'pilot'"):
        X.load_stage(tmp_path / "pilot", X.STAGE1, json.loads(pre.read_text(encoding="utf-8")), X.sha256_lf(pre))
    # an unplanned log in the directory (e.g. copied from another experiment) is never read
    src = tmp_path / "pilot" / "events" / "X2-urgent-single-r0.jsonl"
    (tmp_path / "pilot" / "events" / "T01-urgent-single-r0.jsonl").write_text(src.read_text())
    data = X.load_stage(tmp_path / "pilot", X.PILOT, json.loads(pre.read_text(encoding="utf-8")), X.sha256_lf(pre))
    assert sorted(r["run_id"] for r in data["runs"]) == sorted(PREREG["pilot"]["planned_runs"])
    (tmp_path / "decision.json").rename(tmp_path / "pilot" / "pilot_decision.json")


def test_live_identity_checks_catch_drift_in_a_logged_run(tmp_path):
    pre = _prereg_copy(tmp_path)
    X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False, workers=1)
    path = tmp_path / "pilot" / "events" / "X2-urgent-single-r1.jsonl"
    lines = path.read_text().splitlines()
    start = json.loads(lines[0])
    assert start["type"] == "RUN_STARTED"
    start["compute"]["effort"] = "high"
    path.write_text("\n".join([json.dumps(start)] + lines[1:]) + "\n")
    d = X.report_stage(tmp_path / "pilot", pre)["decision"]
    assert d["verdict"] == "FAIL" and any("compute option" in p for p in d["identity_problems"])


def test_children_reading_nothing_fail_the_pilot_but_are_behaviour_in_stage1(tmp_path):
    pre = _prereg_copy(tmp_path)
    d = X.run_stage("pilot", factory(ModeAwareModel(child_reads="none")), out=tmp_path / "pilot", prereg_path=pre,
                    verify=False, workers=1)["decision"]
    assert d["verdict"] == "FAIL" and d["A_instrument_integrity"] is False
    conds = list(d["central_conditions"].values())[0]
    assert conds["scripted_spawn_accepted"] and conds["exact_k_children"] and not conds["every_child_queried_its_assignment"]


# --------------------------------------------------------------------------- review hardening

class DenseTokenModel(ModeAwareModel):
    """Reports input tokens the way the real API plausibly tokenizes, denser than the runtime's 1-token-per-2-chars
    bound: the system prompt at the 0b audit's first-step rate (chars/2 + 70), user turns at its worst later-step rate
    (0.5225/char) and assistant JSON turns at 0.7/char. Children send long reports."""

    def create(self, **kw):
        resp = super().create(**kw)
        first = kw["messages"][0]["content"]
        if not first.startswith("Task ") and '"TERMINATE"' in resp.content[0].text:
            resp.content[0].text = json.dumps({"rationale": "report", "action": "TERMINATE", "answer": "x" * 3000})
        def chars(m):
            return len(m["content"]) if isinstance(m["content"], str) else sum(len(b.text) for b in m["content"])
        users = sum(chars(m) for m in kw["messages"] if m["role"] == "user")
        assistants = sum(chars(m) for m in kw["messages"] if m["role"] == "assistant")
        resp.usage.input_tokens = -(-len(kw["system"]) // 2) + 70 + int(0.5225 * users + 0.999) + int(0.7 * assistants + 0.999)
        return resp


@pytest.mark.parametrize("task_id", ["X2", "T01", "T04", "T07", "T10"])
def test_the_root_step_after_the_scripted_spawn_has_a_real_reserve(task_id, monkeypatch):
    """The root's first live step re-reads the scripted SPAWN. Its reserve is the runtime's from-scratch rule over the
    whole input (not the scripted step's simulated usage), and it covers realistic, denser-than-bound tokenization."""
    seen = []
    original = Run._input_upper_bound
    def capture(self, a):
        bound = original(self, a)
        if a.parent is None and a.steps == 1:
            chars = len(a.system) + sum(len(m["content"]) if isinstance(m["content"], str) else
                                        sum(len(getattr(b, "text", "")) for b in m["content"]) for m in a.transcript)
            seen.append((bound, -(-chars // 2) + 1000))
        return bound
    monkeypatch.setattr(Run, "_input_upper_bound", capture)
    model = DenseTokenModel()
    policy = X.scripted_policy(LLMPolicy(CONSTANTS.compute, client=Client(model)), PREREG)
    run = Run(RunConfig(TASKS_BY_ID[task_id], CONSTANTS.regimes["urgent"], "central", compute=CONSTANTS.compute,
                        coord=CONSTANTS.coord), policy, InformationEnvironment(load_world(), CONSTANTS.sources))
    run.execute()  # a ReserveViolation would raise here
    assert run.outcome == "answered" and run.agents["A0"].steps == 2
    reserve, from_scratch = seen[-1]  # the reserve call, after the observation is appended
    actual = [e for e in run.log.events if e["type"] == "RESOURCE_CONSUMED" and e["kind"] == "llm"
              and e["agent"] == "A0"][1]["in_tokens"]
    assert reserve >= from_scratch and reserve - actual > 0.03 * reserve


def test_the_live_root_rereads_the_oracles_spawn_byte_for_byte():
    model = ModeAwareModel()
    policy = X.scripted_policy(LLMPolicy(CONSTANTS.compute, client=Client(model)), PREREG)
    Run(RunConfig(TASKS_BY_ID["T04"], CONSTANTS.regimes["urgent"], "central", compute=CONSTANTS.compute,
                  coord=CONSTANTS.coord), policy, InformationEnvironment(load_world(), CONSTANTS.sources)).execute()
    oracle = X.topology("T04|urgent", FROZEN_0B, CONSTANTS)["action"]
    root_requests = [r for r in model.requests if r["messages"][0]["content"].startswith("Task ")]
    assert len(root_requests) == 1 and root_requests[0]["messages"][1] == {"role": "assistant", "content": json.dumps(oracle)}


def test_integrity_requires_one_charged_scripted_step():
    topo, regime, events = _offline_central("T07|urgent")
    assert X.central_integrity(events, topo)["scripted_spawn_accepted"]
    free = copy.deepcopy(events)
    s = next(e for e in free if e["type"] == "SCRIPTED_ACTION")
    next(e for e in free if e["type"] == "RESOURCE_CONSUMED" and e["kind"] == "llm" and e["seq"] > s["seq"])["amount"] = 0
    assert not X.central_integrity(free, topo)["scripted_spawn_accepted"]
    twice = copy.deepcopy(events) + [dict(s, agent="A0.1", seq=10_000)]
    assert not X.central_integrity(twice, topo)["intact"]


def test_stage0_catches_changed_caps_or_treatment_files(monkeypatch):
    from dataclasses import replace
    original = X.configs_for
    monkeypatch.setattr(X, "configs_for", lambda *a: [replace(c, max_steps=30) for c in original(*a)])
    assert X.stage0_checks(PREREG)["caps_are_0b"]
    monkeypatch.setattr(X, "configs_for", original)
    monkeypatch.setitem(X.EXP0B_TREATMENT_FILES, "devagents/agents/prompts.py", "0" * 64)
    assert X.stage0_checks(PREREG)["treatment_files_unchanged_since_0b"]
    assert set(X.EXP0B_TREATMENT_FILES) >= {"devagents/agents/prompts.py", "devagents/agents/policies.py",
                                           "devagents/runtime/resources.py", "data/world/structured.sql"}
    assert sum(f.startswith("data/world/docs/") for f in X.EXP0B_TREATMENT_FILES) == len(load_world().docs)


def test_a_request_level_change_is_caught_against_0bs_code(monkeypatch):
    """The request stream is pinned to a golden computed with Experiment 0b's own code (67c9d50)."""
    original = LLMPolicy.request
    monkeypatch.setattr(LLMPolicy, "request", lambda self, *a: {**original(self, *a), "temperature": 1.0})
    assert X.request_stream_sha(lambda p: X.scripted_policy(p, PREREG), CONSTANTS) != X.EXP0B_REQUEST_STREAM_SHA
    monkeypatch.setattr(LLMPolicy, "request", original)
    assert X.request_stream_sha(lambda p: X.scripted_policy(p, PREREG), CONSTANTS) == X.EXP0B_REQUEST_STREAM_SHA


@pytest.fixture(scope="module")
def stage1_dir(tmp_path_factory):
    """One fake-client pilot (PASS) and Stage 1 (NO-GO, otherwise valid), reused by the drift harness below."""
    d = tmp_path_factory.mktemp("exp0c")
    pre = _prereg_copy(d)
    X.run_stage("pilot", factory(ModeAwareModel()), out=d / "pilot", prereg_path=pre, verify=False, workers=1)
    X.run_stage("stage1", factory(ModeAwareModel()), out=d / "s1", pilot_dir=d / "pilot", prereg_path=pre, verify=False)
    return d


def _mutate_start(path: Path, fn):
    lines = path.read_text(encoding="utf-8").splitlines()
    start = json.loads(lines[0])
    assert start["type"] == "RUN_STARTED"
    fn(start)
    path.write_text("\n".join([json.dumps(start)] + lines[1:]) + "\n", encoding="utf-8")


def _set(path, value):
    def fn(d):
        for k in path[:-1]:
            d = d[k]
        if value is KeyError:
            del d[path[-1]]
        else:
            d[path[-1]] = value
    return fn


DRIFTS = [
    ("single", ("policy", "model"), "other-model"), ("developmental", ("policy", "effort"), "high"),
    ("developmental", ("policy", "structured"), False), ("single", ("policy", "class"), "OtherPolicy"),
    ("developmental", ("compute", "model"), "other-model"), ("single", ("compute", "price_in"), 3),
    ("developmental", ("prompt_sha",), "0" * 64), ("single", ("audit", "catalog_sha"), "0" * 64),
    ("developmental", ("audit", "frozen_sha"), "0" * 64), ("developmental", ("audit", "max_steps"), 30),
    ("single", ("audit", "question"), "another question"), ("developmental", ("budget",), 1),
    ("single", ("deadline_s",), 1499.0), ("developmental", ("value_of_time",), 0.002),
    ("developmental", ("policy", "central_first_step"), "scripted"), ("central", ("policy", "central_first_step"), KeyError),
    ("central", ("policy", "effort"), "high"), ("single", ("wall",), 0.0),
]


@pytest.mark.parametrize("mode,path,value", DRIFTS, ids=[f"{m}:{'.'.join(p)}" for m, p, _ in DRIFTS])
def test_each_logged_identity_field_is_checked(stage1_dir, tmp_path, mode, path, value):
    import shutil
    d = tmp_path / "s1"
    shutil.copytree(stage1_dir / "s1", d)
    _mutate_start(d / "events" / f"T04-urgent-{mode}-r1.jsonl", _set(path, value))
    dec = X.report_stage(d, stage1_dir / "prereg.json")["decision"]
    assert dec["verdict"] == "UNINFORMATIVE" and dec["steps"][-1]["step"] == "treatment_identity"


def test_uniform_drift_in_every_run_is_caught(stage1_dir, tmp_path):
    import shutil
    d = tmp_path / "s1"
    shutil.copytree(stage1_dir / "s1", d)
    for p in (d / "events").glob("*.jsonl"):
        _mutate_start(p, _set(("policy", "effort"), "high"))
    dec = X.report_stage(d, stage1_dir / "prereg.json")["decision"]
    assert dec["verdict"] == "UNINFORMATIVE"


@pytest.mark.parametrize("key,value", [("policy", {"class": "LLMPolicy"}), ("constants", {}),
                                       ("declared_asymmetries", {}), ("frozen_sha", "0" * 64), ("spec_sha", "0" * 64),
                                       ("treatment", {"action_schema_sha": "0" * 64})])
def test_manifest_drift_is_caught(stage1_dir, tmp_path, key, value):
    import shutil
    d = tmp_path / "s1"
    shutil.copytree(stage1_dir / "s1", d)
    m = json.loads((d / "manifest.json").read_text())
    m[key] = value
    (d / "manifest.json").write_text(json.dumps(m))
    assert X.report_stage(d, stage1_dir / "prereg.json")["decision"]["verdict"] == "UNINFORMATIVE"


def test_a_scripted_step_outside_central_is_caught(stage1_dir, tmp_path):
    import shutil
    d = tmp_path / "s1"
    shutil.copytree(stage1_dir / "s1", d)
    path = d / "events" / "T01-urgent-developmental-r0.jsonl"
    lines = path.read_text().splitlines()
    lines.insert(1, json.dumps({"seq": 0, "run_id": "T01-urgent-developmental-r0", "type": "SCRIPTED_ACTION",
                                "t": 0.0, "agent": "A0", "step": 1, "action": {}}))
    path.write_text("\n".join(lines) + "\n")
    assert X.report_stage(d, stage1_dir / "prereg.json")["decision"]["verdict"] == "UNINFORMATIVE"


def test_the_untouched_fixture_is_a_valid_no_go(stage1_dir):
    assert X.report_stage(stage1_dir / "s1", stage1_dir / "prereg.json")["decision"]["verdict"] == "NO-GO"


# --------------------------------------------------------------------------- event-level integrity definitions

def _edit(events, pred, **changes):
    out = copy.deepcopy(events)
    for e in out:
        if pred(e):
            e.update(changes)
    return out


def _drop(events, pred):
    return [e for e in copy.deepcopy(events) if not pred(e)]


def _first_step(e, kind):
    return e["type"] == kind and e["agent"] == "A0" and e.get("step") == 1


@pytest.fixture(scope="module")
def offline_t01():
    return _offline_central("T01|urgent")[::2]  # (topo, events)


def test_integrity_definitions_event_by_event(offline_t01):
    topo, events = offline_t01
    I = lambda evs: X.central_integrity(evs, topo)
    assert I(events)["intact"] and I(events)["every_child_queried_its_assignment"]
    # the scripted SPAWN must be accepted: completed ok and not discarded, and equal to the pre-registered action
    assert not I(_edit(events, lambda e: _first_step(e, "ACTION_COMPLETED"), ok=False))["intact"]
    assert not I(_edit(events, lambda e: _first_step(e, "ACTION_COMPLETED"), discarded=True))["intact"]
    other = copy.deepcopy(topo["action"])
    other["children"] = other["children"][:2]
    assert not I(_edit(events, lambda e: e["type"] == "SCRIPTED_ACTION", action=other))["scripted_spawn_accepted"]
    # exact k and exact objectives
    assert not I(_drop(events, lambda e: e["type"] == "AGENT_SPAWNED" and e["child"] == "A0.3"))["exact_k_children"]
    swapped = copy.deepcopy(events)
    sp = [e for e in swapped if e["type"] == "AGENT_SPAWNED"]
    sp[0]["objective"], sp[1]["objective"] = sp[1]["objective"], sp[0]["objective"]
    assert not I(swapped)["exact_partition"]
    # starvation and runtime terminations before the assigned QUERY are mechanical failures
    no_reads = _drop(events, lambda e: e["type"] == "INFORMATION_QUERIED" and e["agent"] == "A0.1")
    starved = _edit(no_reads, lambda e: e["type"] == "AGENT_TERMINATED" and e["agent"] == "A0.1",
                    reason="budget_exhausted", steps=0)
    assert not I(starved)["no_child_starved"] and not I(starved)["intact"]
    for reason in ("lifetime_expired", "ancestor_terminated", "max_steps", "context_exhausted", "budget_exhausted"):
        killed = _edit(no_reads, lambda e: e["type"] == "AGENT_TERMINATED" and e["agent"] == "A0.1", reason=reason, steps=3)
        assert not I(killed)["no_runtime_termination_before_task"] and not I(killed)["intact"], reason
        late = _edit(events, lambda e: e["type"] == "AGENT_TERMINATED" and e["agent"] == "A0.1", reason=reason, steps=3)
        assert I(late)["intact"], reason  # terminated by the runtime only after reading its assignment
    # a child that chose not to read (or read only part) is behaviour: intact, but reported and fatal for the pilot
    partial = _drop(events, lambda e: e["type"] == "INFORMATION_QUERIED" and e["agent"] == "A0.2"
                    and e["source"] == topo["partition"][1][0])
    assert I(partial)["intact"] and not I(partial)["every_child_queried_its_assignment"]
    quit_early = no_reads  # A0.1 completed without reading anything
    assert I(quit_early)["intact"] and not I(quit_early)["every_child_queried_its_assignment"]
    extra = copy.deepcopy(events) + [dict(next(e for e in events if e["type"] == "INFORMATION_QUERIED" and e["agent"] == "A0.2"),
                                          agent="A0.1", seq=99_999)]
    assert I(extra)["intact"] and I(extra)["children_reading_outside_assignment"] == 1


# --------------------------------------------------------------------------- final decisions, exhausted runs, the gate

def test_a_stage_decision_is_final_and_never_rerun(tmp_path):
    pre = _prereg_copy(tmp_path)
    X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False, workers=1)
    with pytest.raises(SystemExit, match="no second pilot"):
        X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False)
    X.pilot_record_path(pre).unlink()  # even without the record, the decision itself is final
    with pytest.raises(SystemExit, match="final"):
        X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False)
    first = (tmp_path / "pilot" / "pilot_decision.json").read_bytes()
    X.report_stage(tmp_path / "pilot", pre)  # a recomputation never overwrites the final decision
    assert (tmp_path / "pilot" / "pilot_decision.json").read_bytes() == first
    assert (tmp_path / "pilot" / "pilot_recomputed_decision.json").exists()


class InfraFailingModel(ModeAwareModel):
    """Every API call of one run fails with an infrastructure error (the reserve violation stands in for any)."""

    def create(self, **kw):
        if "Task X2" in kw["messages"][0]["content"] and "Your first action must be SPAWN" in kw["system"]:
            from devagents.runtime.runtime import ReserveViolation
            raise ReserveViolation("simulated infrastructure failure")
        return super().create(**kw)


def test_runs_whose_retries_are_spent_are_final_and_fail_the_pilot(tmp_path, monkeypatch):
    import devagents.evals.experiment as E
    monkeypatch.setattr(E.time, "sleep", lambda s: None)
    pre = _prereg_copy(tmp_path)
    res = X.run_stage("pilot", factory(InfraFailingModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False,
                      workers=1)
    d = res["decision"]
    assert d["verdict"] == "FAIL" and d["missing_runs"] and "incomplete (infrastructure)" in d["reasons"][0]
    assert sorted(res["summary"]["exhausted"]) == sorted(r for r in PREREG["pilot"]["planned_runs"] if "central" in r)
    # even if the decision file were lost, a resumed stage never attempts an exhausted run again
    (tmp_path / "pilot" / "pilot_decision.json").unlink()
    X.pilot_record_path(pre).unlink()
    again = X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False)
    assert again["decision"]["verdict"] == "FAIL" and again["summary"]["completed"] == 2


def test_the_gate_needs_the_pilots_own_final_pass_under_the_same_code(tmp_path, monkeypatch):
    pre = _prereg_copy(tmp_path)
    X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False, workers=1)
    prereg, sha = X.load_prereg(pre)
    assert X.pilot_gate(tmp_path / "pilot", prereg, sha, pre)["passed"]
    record = json.loads(X.pilot_record_path(pre).read_text())
    assert record["verdict"] == "PASS" and record["prereg_sha"] == sha
    with pytest.raises(SystemExit, match="pilot_record"):  # the committed record ties Stage 1 to this pilot
        X.pilot_gate(tmp_path / "pilot", prereg, sha, tmp_path / "elsewhere" / "prereg.json")
    monkeypatch.setattr(X, "code_sha", lambda: {"devagents/evals/exp0c.py": "edited"})
    with pytest.raises(SystemExit, match="did not PASS"):
        X.pilot_gate(tmp_path / "pilot", prereg, sha, pre)
    monkeypatch.undo()
    (tmp_path / "pilot" / "pilot_decision.json").unlink()
    with pytest.raises(SystemExit, match="no finished X2 pilot"):
        X.pilot_gate(tmp_path / "pilot", prereg, sha, pre)


def test_the_preregistration_pins_the_deciding_code():
    assert PREREG["code_sha"] == X.code_sha()
    assert {"devagents/evals/exp0c.py", "devagents/agents/scripted_central.py", "devagents/runtime/runtime.py",
            "devagents/evals/report.py", "devagents/evals/analysis.py"} <= set(PREREG["code_sha"])


def test_uniform_drift_in_fingerprint_audit_or_caps_is_caught(stage1_dir, tmp_path):
    import shutil
    for path, value in ((("prompt_sha",), "0" * 64), (("audit", "catalog_sha"), "0" * 64), (("audit", "max_steps"), 30)):
        d = tmp_path / "-".join(path)
        shutil.copytree(stage1_dir / "s1", d)
        for log in (d / "events").glob("*.jsonl"):
            _mutate_start(log, _set(path, value))
        assert X.report_stage(d, stage1_dir / "prereg.json")["decision"]["verdict"] == "UNINFORMATIVE", path


def test_verify_checks_the_spawns_serialization_not_only_its_content():
    tampered = json.loads(json.dumps(PREREG, sort_keys=True))  # same content, keys sorted
    checks = X.stage0_checks(tampered)
    assert checks["spawn_bytes_equal_the_oracle"] and not checks["topology_k_and_partition"]


# --------------------------------------------------------------------------- interrupted runs never lose live output

class CrashingModel(ModeAwareModel):
    """Crashes (a defect or an interruption, not an infrastructure error) at the central root's first live step."""

    def create(self, **kw):
        if "Task X2" in kw["messages"][0]["content"] and "Your first action must be SPAWN" in kw["system"]:
            raise RuntimeError("the session ended")
        return super().create(**kw)


def test_an_interrupted_run_keeps_its_partial_log_and_spends_one_attempt(tmp_path):
    pre = _prereg_copy(tmp_path)
    with pytest.raises(RuntimeError):
        X.run_stage("pilot", factory(CrashingModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False, workers=1)
    partial = [p.stem for p in (tmp_path / "pilot" / "events").glob("*.jsonl")
               if '"RUN_COMPLETED"' not in p.read_text(encoding="utf-8")]
    assert partial  # live output that must survive the resume
    res = X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False,
                      workers=1)
    assert res["decision"]["verdict"] == "PASS"
    aborted = sorted(p.name for p in (tmp_path / "pilot" / "events" / "aborted").glob("*.jsonl"))
    assert aborted == [f"{r}.1.jsonl" for r in sorted(partial)]
    errors = [json.loads(l) for l in (tmp_path / "pilot" / "errors.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sorted(e["run_id"] for e in errors) == sorted(partial) and all("interrupted" in e["error"] for e in errors)
    assert X.attempts_used(tmp_path / "pilot") == {r: 1 for r in partial}


def test_a_finished_log_without_its_runs_line_is_kept_and_the_budget_spans_sessions(tmp_path, monkeypatch):
    import devagents.evals.experiment as E
    monkeypatch.setattr(E.time, "sleep", lambda s: None)
    pre = _prereg_copy(tmp_path)
    out = tmp_path / "pilot"
    X.run_stage("pilot", factory(ModeAwareModel()), out=out, prereg_path=pre, verify=False, workers=1)
    for f in ("pilot_decision.json", "pilot_report.md"):
        (out / f).unlink()
    X.pilot_record_path(pre).unlink()
    lines = (out / "runs.jsonl").read_text().splitlines()
    (out / "runs.jsonl").write_text("\n".join(lines[:2]) + "\n")  # as if the session died before recording two runs
    res = X.run_stage("pilot", factory(InfraFailingModel()), out=out, prereg_path=pre, verify=False, workers=1)
    assert res["summary"]["completed"] == 4 and not (out / "errors.jsonl").exists()  # recovered, not re-run
    assert res["decision"]["verdict"] == "PASS"
    # across sessions, failed and interrupted attempts share one budget of 4 attempts
    out2 = tmp_path / "pilot2"
    (out2 / "events").mkdir(parents=True)
    with open(out2 / "errors.jsonl", "w") as fh:
        for _ in range(3):
            fh.write(json.dumps({"run_id": "X2-urgent-central-r0", "error": "interrupted"}) + "\n")
    X.pilot_record_path(pre).unlink()
    res = X.run_stage("pilot", factory(InfraFailingModel()), out=out2, prereg_path=pre, verify=False, workers=1)
    assert X.attempts_used(out2)["X2-urgent-central-r0"] == 4 and "X2-urgent-central-r0" in res["summary"]["exhausted"]
