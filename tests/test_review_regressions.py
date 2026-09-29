"""Regression tests for defects found by the adversarial code review (ids from EXPERIMENT_STATUS.md)."""

import copy
import json

import pytest

from devagents.agents.policies import LLMPolicy, ScriptedPolicy, clean_content, transcript_tokens
from devagents.config import default_constants, load_frozen
from devagents.environment.sources import InformationEnvironment, SourceCosts
from devagents.environment.tasks import TASKS_BY_ID
from devagents.environment.world import REGIONS, load_world, region_doc_id
from devagents.evals.calibrate import Org, oracle_script
from devagents.evals.experiment import make_manifest, pilot_stats, plan, run_suite, verify_frozen
from devagents.evals.metrics import metrics_from_events
from devagents.runtime.events import EventLog
from devagents.runtime.runtime import Run, RunConfig
from tests.helpers import by_step, events_of, info, make_run, msg, q, regime, spawn, term, wait, work

DOCS = [region_doc_id(r) for r in REGIONS]


def llm_steps(run, agent):
    return [e for e in events_of(run, "RESOURCE_CONSUMED") if e["kind"] == "llm" and e["agent"] == agent]


@pytest.mark.parametrize("root_plan", [
    [spawn(("idle child", 0.1, 900)), wait("any", 1.0)],  # a WAIT that keeps timing out
    [work(), spawn(("idle child", 0.1, 900), wait=True), work()],  # the last allowed step is SPAWN + wait
])
def test_acc1_step_cap_holds_after_waiting(root_plan):
    run = make_run(by_step({"A0": root_plan, "A0.1": [wait("any"), term()]}), max_steps=2)
    run.execute()
    assert len(llm_steps(run, "A0")) == 2 and run.outcome == "max_steps"


def test_acc2_caps_count_spawns_that_are_still_in_flight():
    four = [(f"g{i}", 0.02, 600) for i in range(4)]
    run = make_run(by_step({"A0": [spawn(("a", 0.3, 900), ("b", 0.3, 900), wait=True), term()],
                            "A0.1": [spawn(*four, wait=True), term()], "A0.2": [spawn(*four, wait=True), term()]}))
    run.execute()
    m = metrics_from_events(run.log.events)
    assert m["max_live_agents"] <= run.cfg.compute.max_concurrency and m["agents"] <= run.cfg.max_agents
    rejected = [e for e in events_of(run, "ACTION_COMPLETED") if e["action"] == "SPAWN" and not e["ok"]]
    assert rejected and "concurrency cap" in rejected[0]["error"]


def test_acc3_wait_all_waits_for_a_childs_lifecycle_notice():
    run = make_run(by_step({"A0": [spawn(("slow", 0.1, 3.0), ("quick", 0.1, 900), wait=True), term()],
                            "A0.1": [q(*DOCS), term()], "A0.2": [term("done")]}))
    run.execute()
    notice = [m for m in run.messages if m.kind == "notice"][0]
    report = [m for m in run.messages if m.kind == "report"][0]
    assert report.deliver_at < notice.deliver_at  # the sibling's report arrives first
    final = [e for e in events_of(run, "ACTION_STARTED") if e["agent"] == "A0"][-1]
    assert abs(final["t"] - notice.deliver_at / 1e6) < 1e-6


def test_acc4_message_to_a_child_that_terminated_in_flight_is_reported_as_undelivered():
    run = make_run(by_step({"A0": [spawn(("x", 0.1, 900)), msg("A0.1", "late"), wait("all"), term()],
                            "A0.1": [term("bye")]}), reasoning=400)
    run.execute()
    done = [e for e in events_of(run, "ACTION_COMPLETED") if e["action"] == "MESSAGE"][0]
    sent = [m for m in events_of(run, "MESSAGE_SENT") if m["agent"] == "A0"]
    if not sent:  # the race happened: the charge stands and the agent is told the truth
        assert "not delivered" in done["error"]
        assert any("not delivered" in t["content"] for t in run.agents["A0"].transcript if t["role"] == "user")


def test_acc5_oracle_fanout_uses_exactly_the_central_allocation_rule():
    """Both the oracle (developmental + fixed_rule_spawns) and central allocate by the same rule, recomputed here from
    each run's own log: an equal share of 50% of the balance left after the decision step and the spawn fees."""
    task = TASKS_BY_ID["T01"]
    script = oracle_script(task, task.routes[0], Org("fanout", 0, 3), 0)
    for mode, fixed in (("developmental", True), ("central", False)):
        run = Run(RunConfig(task, regime(), mode, fixed_rule_spawns=fixed), ScriptedPolicy(script, reasoning_tokens=150),
                  info())
        run.execute()
        consumed = events_of(run, "RESOURCE_CONSUMED")
        first_fee = next(i for i, e in enumerate(consumed) if e["kind"] == "spawn")
        balance = run.ledger.budget - sum(e["amount"] for e in consumed[:first_fee])
        fees = sum(e["amount"] for e in consumed if e["kind"] == "spawn")
        allocs = [e["amount"] for e in events_of(run, "RESOURCE_ALLOCATED") if e["kind"] == "allocation"]
        assert allocs == [int(0.5 * (balance - fees)) // 3] * 3, mode


def test_acc6_nothing_is_charged_after_an_agent_terminates_or_the_run_ends():
    scenarios = [
        by_step({"A0": [spawn(("a", 0.1, 4.0), wait=True), term()], "A0.1": [work(), q(*DOCS), term()]}),
        by_step({"A0": [spawn(("a", 0.1, 900), ("b", 0.1, 900)), term("early")],
                 "A0.1": [q(*DOCS), term()], "A0.2": [work(), q(*DOCS), term()]}),
    ]
    for script in scenarios:
        run = make_run(script)
        run.execute()
        ended = {e["agent"]: e["t"] for e in events_of(run, "AGENT_TERMINATED")}
        end = events_of(run, "RUN_COMPLETED")[0]["t"]
        for e in events_of(run, "RESOURCE_CONSUMED"):
            assert e["t"] <= ended[e["agent"]] and e["t"] <= end


def test_val4_wait_with_zero_timeout_returns_immediately():
    run = make_run(by_step({"A0": [spawn(("idle", 0.1, 900)), wait("any", 0), term()], "A0.1": [wait("any"), term()]}))
    run.execute()
    starts = [e for e in events_of(run, "ACTION_STARTED") if e["agent"] == "A0"]
    waited = next(e for e in events_of(run, "ACTION_COMPLETED") if e["agent"] == "A0" and e["action"] == "WAIT")
    assert abs(starts[2]["t"] - waited["t"]) < 1e-6  # no time passed while waiting


class _Block:
    def __init__(self, type, text="", signature=None, thinking=None):
        self.type, self.text, self.signature, self.thinking = type, text, signature, thinking


def test_val1_token_estimate_ignores_thinking_blocks_and_sdk_reprs():
    run = make_run(by_step({"A0": [term()]}))
    run.execute()
    a = run.agents["A0"]
    plain = transcript_tokens(a)
    a.transcript[1] = {"role": "assistant", "content": [_Block("thinking", signature="x" * 5000, thinking=""),
                                                         _Block("text", text=a.transcript[1]["content"])]}
    assert transcript_tokens(a) == plain


def test_val5_replies_are_cleaned_before_they_are_re_sent():
    assert clean_content([]) == [{"type": "text", "text": "(no output)"}]
    kept = clean_content([_Block("thinking", signature=None), _Block("text", text=" "), _Block("text", text="ok")])
    assert [b.text for b in kept] == ["ok"]
    signed = _Block("thinking", signature="sig")
    assert clean_content([signed]) == [signed]


def test_stat1_pilot_cost_cv_is_not_biased_low(tmp_path):
    from tests.test_llm_pipeline import FakeClient, FakeModel
    from devagents.environment.tasks import PILOT_TASKS
    c = default_constants()
    configs = plan(PILOT_TASKS, c, ["single", "central"], 2)
    run_suite(configs, LLMPolicy(c.compute, client=FakeClient(FakeModel())), c, tmp_path,
              make_manifest("pilot", configs, c, True, ""))
    stats = pilot_stats(tmp_path)
    assert stats["cost_cv"] is not None and stats["cost_cv_groups"] == 12


def test_stat5_pilot_with_any_developmental_log_is_refused(tmp_path):
    (tmp_path / "events").mkdir()
    cfg = RunConfig(TASKS_BY_ID["X1"], regime(), "developmental")
    log = EventLog(cfg.run_id, tmp_path / "events" / f"{cfg.run_id}.jsonl")
    log.emit("RUN_STARTED", 0.0, task_id="X1", mode="developmental")  # an incomplete log, e.g. after an infra error
    log.close()
    with pytest.raises(ValueError, match="developmental or router"):
        pilot_stats(tmp_path)


def test_stat2_a_different_suite_cannot_resume_in_the_same_directory(tmp_path):
    from tests.test_llm_pipeline import FakeClient, FakeModel
    c = default_constants()
    policy = LLMPolicy(c.compute, client=FakeClient(FakeModel()))
    first = plan([TASKS_BY_ID["T02"]], c, ["single"], 1)
    run_suite(first, policy, c, tmp_path, make_manifest("main", first, c, False, ""))
    second = plan([TASKS_BY_ID["T02"]], c, ["single"], 2)
    with pytest.raises(SystemExit, match="different suite"):
        run_suite(second, policy, c, tmp_path, make_manifest("main", second, c, False, ""))


def test_spec5_catalog_shows_repaired_latencies_exactly():
    env = InformationEnvironment(load_world(), SourceCosts(doc_per_token_s=0.105))
    assert "0.105s per document token" in env.catalog()


def test_spec3_verify_frozen_detects_numeric_drift():
    frozen = load_frozen()
    assert verify_frozen(frozen) == []
    tampered = copy.deepcopy(frozen)
    key = next(iter(tampered["calibration"]["cells"]))
    tampered["calibration"]["cells"][key]["solo_fitness"] += 0.01
    assert any("calibrated values" in p for p in verify_frozen(tampered))
    tampered = copy.deepcopy(frozen)
    tampered["prompt_sha"] = "0" * 64
    assert any("prompt fingerprint" in p for p in verify_frozen(tampered))


# --------------------------------------------------------------------------- test-adequacy findings (TEST-4..10)

from devagents.evals.analysis import Runs, _synthetic_policies, contrast_ci, evaluate, synthetic_records  # noqa: E402
import random  # noqa: E402

FROZEN = load_frozen()
CELLS, SETS = FROZEN["calibration"]["cells"], FROZEN["calibration"]["gate"]["sets"]
MAX_DOCS = {t.id: t.max_doc_route for t in TASKS_BY_ID.values()}


def test_test4_criterion_5_fires_when_developmental_is_as_wasteful_as_central():
    pol = _synthetic_policies(CELLS, MAX_DOCS)["WASTEFUL"]
    recs = synthetic_records(CELLS, pol, 3, {c: 1.0 for c in ("solo", "parallel", "cross")}, random.Random(0), 0.1)
    res = evaluate(recs, CELLS, SETS, n_boot=300)
    assert "5_central_matches_on_S" in res["fired"] and "4c_cost_loss_vs_single_elsewhere" in res["fired"]
    assert not any(k.startswith(("1_", "2_", "3")) for k in res["fired"])  # its organization is right


def _rec(task, cls, regime, mode, spawned=False, fitness=0.5, quality=1.0):
    return {"task_id": task, "task_class": cls, "subtype": "", "regime": regime, "mode": mode, "fitness": fitness,
            "quality": quality, "spawned": spawned, "parallel": spawned, "cap_hits": 0, "infra_error": False}


def test_test4_rates_are_means_over_strata_not_pooled_over_cells():
    cells = {"A1|urgent": {"task": "A1", "task_class": "solo", "regime": "urgent"},
             "A2|urgent": {"task": "A2", "task_class": "solo", "regime": "urgent"},
             "A3|urgent": {"task": "A3", "task_class": "solo", "regime": "urgent"},
             "B1|urgent": {"task": "B1", "task_class": "parallel", "regime": "urgent"}}
    recs = [_rec("A1", "solo", "urgent", "developmental", True), _rec("A2", "solo", "urgent", "developmental", True),
            _rec("A3", "solo", "urgent", "developmental", True), _rec("B1", "parallel", "urgent", "developmental", False)]
    assert Runs(recs, cells).rate(set(cells), "spawned") == pytest.approx(0.5)  # pooled would be 0.75


def test_test4_bootstrap_resamples_tasks_as_well_as_runs():
    cells = {f"T{i}|urgent": {"task": f"T{i}", "task_class": "parallel", "regime": "urgent"} for i in range(4)}
    recs = []
    for i in range(4):  # identical runs within a cell, very different effects between tasks
        for rep in range(3):
            recs.append(_rec(f"T{i}", "parallel", "urgent", "developmental", fitness=[0.0, 0.1, 0.2, 1.0][i]))
            recs.append(_rec(f"T{i}", "parallel", "urgent", "single", fitness=0.0))
    ci = contrast_ci(Runs(recs, cells), set(cells), "single", "fitness", n_boot=2000)
    assert ci["hi"] - ci["lo"] > 0.3  # run-level resampling alone would give a zero-width interval


def test_test6_messages_are_invisible_until_delivered():
    run = make_run(by_step({"A0": [spawn(("listen", 0.1, 900)), msg("A0.1", "SECRET"), wait("all"), term()],
                            "A0.1": [wait("any", 0.0), wait("any"), term()]}))
    run.execute()
    sent = [m for m in events_of(run, "MESSAGE_SENT") if m["kind"] == "message"][0]
    child = run.agents["A0.1"]
    starts = [e["t"] for e in events_of(run, "ACTION_STARTED") if e["agent"] == "A0.1"]
    for obs, t in zip([m for m in child.transcript if m["role"] == "user"], starts):
        assert ("SECRET" in obs["content"]) == (t >= sent["deliver_at"]), t


def test_test7_grandchild_refunds_go_to_its_parent_not_the_root():
    from tests.test_accounting import replay_balances
    run = make_run(by_step({"A0": [spawn(("mid", 0.3, 900), wait=True), term()],
                            "A0.1": [spawn(("leaf", 0.1, 600), wait=True), term()], "A0.1.1": [q(DOCS[0]), term()]}))
    run.execute()
    leaf = [e for e in events_of(run, "AGENT_TERMINATED") if e["agent"] == "A0.1.1"][0]
    assert leaf["returned_to"] == "A0.1" and leaf["returned"] > 0
    bal, _ = replay_balances(run.log.events, run.ledger.budget)
    assert bal == run.ledger.balance


def test_test8_spawn_fee_charges_the_copied_context():
    from devagents.runtime.resources import estimate_tokens
    ctx = "x" * 400
    run = make_run(by_step({"A0": [spawn(("read", 0.1, 900), wait=True, context=ctx), term()],
                            "A0.1": [term("r")]}))
    run.execute()
    fee = [e for e in events_of(run, "RESOURCE_CONSUMED") if e["kind"] == "spawn"][0]["amount"]
    coord = run.cfg.coord
    assert fee == coord.spawn_fee + coord.transfer_per_token * (estimate_tokens("read") + estimate_tokens(ctx))


def test_test9_central_allocation_and_lifetime_follow_the_rule_exactly():
    from devagents.runtime.runtime import us
    run = make_run(by_step({"A0": [spawn(("a", 0.9, 1), ("b", 0.9, 1)), term()],
                            "A0.1": [term()], "A0.2": [term()]}), mode="central")
    run.execute()
    consumed = events_of(run, "RESOURCE_CONSUMED")
    first_fee = next(i for i, e in enumerate(consumed) if e["kind"] == "spawn")
    balance = run.ledger.budget - sum(e["amount"] for e in consumed[:first_fee])
    fees = sum(e["amount"] for e in consumed if e["kind"] == "spawn")
    allocs = [e["amount"] for e in events_of(run, "RESOURCE_ALLOCATED") if e["kind"] == "allocation"]
    assert allocs == [int(0.5 * (balance - fees)) // 2] * 2
    started = events_of(run, "ACTION_STARTED")[0]
    t_decided = us(started["t"]) + us(started["llm_latency_s"])
    done = next(e for e in events_of(run, "ACTION_COMPLETED") if e["action"] == "SPAWN")
    expected = us(done["t"]) + us(0.6 * (us(run.cfg.regime.deadline_s) - t_decided) / 1e6)
    for c in events_of(run, "AGENT_CREATED")[1:]:
        assert abs(us(c["deadline"]) - expected) <= 2  # µs rounding only


def test_test10_router_first_valid_action_not_first_step():
    run = make_run(by_step({"A0": [{"rationale": "oops", "action": "BOGUS"}, spawn(("a", 0.1, 900), wait=True), term()],
                            "A0.1": [term()]}), mode="router")
    run.execute()
    assert len(run.agents) == 2  # an invalid first step does not use up the one organizational decision


def test_test10_childless_wait_any_is_invalid_and_the_run_continues():
    run = make_run(by_step({"A0": [wait("any"), term("x")]}))
    run.execute()
    first = events_of(run, "ACTION_COMPLETED")[0]
    assert not first["ok"] and "nobody can send" in first["error"] and run.outcome == "answered"


def test_test10_child_deadline_is_capped_at_the_parents():
    run = make_run(by_step({"A0": [spawn(("a", 0.1, 10_000), wait=True), term()], "A0.1": [term()]}),
                   reg=regime(deadline_s=300.0))
    run.execute()
    assert events_of(run, "AGENT_CREATED")[1]["deadline"] == 300.0


def test_test10_budget_capped_truncation_ends_the_agent():
    class Truncating:
        def decide(self, agent, allowed, max_tokens, run):
            from devagents.runtime.runtime import Decision
            return Decision(None, 100, max_tokens, "{", error="truncated", truncated=True)
    from devagents.environment.tasks import TASKS_BY_ID as T
    run = Run(RunConfig(T["T02"], regime(budget_usd=0.03), "single"), Truncating(), info())
    run.execute()
    assert run.outcome == "budget_exhausted"


def test_test10_a_report_is_always_affordable_after_a_step():
    # a child whose allocation barely covers its steps still sends its final report
    run = make_run(by_step({"A0": [spawn(("tight", 0.03, 900), wait=True), term()], "A0.1": [term("R" * 200)]}))
    run.execute()
    assert [m for m in events_of(run, "MESSAGE_SENT") if m["kind"] == "report"]
