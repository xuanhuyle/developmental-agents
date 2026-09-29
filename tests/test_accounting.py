"""Resource accounting invariants (SPEC §3.3): nothing creates money, every charge is accounted for, and
allocation and refunds move money exactly."""

import json
import math
from types import SimpleNamespace

import pytest

from devagents.agents.policies import LLMPolicy, ScriptedPolicy, transcript_tokens
from devagents.config import default_constants
from devagents.environment.tasks import TASKS_BY_ID
from devagents.environment.world import SUPPLIERS
from devagents.evals.calibrate import Assumptions, measure
from devagents.runtime.resources import COMPUTE_OPTIONS, DEFAULT_COMPUTE, InsufficientFunds, Ledger, estimate_tokens, usd
from devagents.runtime.runtime import REQUEST_OVERHEAD_TOKENS, Decision, ReserveViolation, Run, RunConfig
from tests.helpers import by_step, events_of, info, make_run, q, regime, spawn, term, wait

REGION_DOCS = ["region-northland", "region-eastmarch", "region-southvale"]
# The invariants are checked where the runtime's own input bound binds (r = 1) and where a scripted policy's declared
# bound binds (r = 3, whose children need a larger allocation to take a step).
SCALES = [1.0, 3.0]
ALLOC = {1.0: 0.05, 3.0: 0.1}


def replay_balances(events, budget):
    """Rebuild every balance from the log alone: allocations and refunds move money, consumption spends it."""
    bal, spent = {"A0": budget}, {}
    for e in events:
        if e["type"] == "AGENT_CREATED" and e["parent"] is not None:
            bal.setdefault(e["agent"], 0)
        elif e["type"] == "RESOURCE_ALLOCATED":
            bal[e["source"]] -= e["amount"]
            bal[e["target"]] += e["amount"]
        elif e["type"] == "RESOURCE_CONSUMED":
            bal[e["agent"]] -= e["amount"]
            spent[e["agent"]] = spent.get(e["agent"], 0) + e["amount"]
        assert all(v >= 0 for v in bal.values()), f"negative balance after event {e['seq']}"
        assert sum(bal.values()) + sum(spent.values()) == budget, f"conservation broken at event {e['seq']}"
    return bal, spent


# --------------------------------------------------------------------------- ledger primitives

def test_ledger_charge_and_transfer_conserve_money():
    led = Ledger(1000, "A0")
    led.open("A0.1")
    led.transfer("A0", "A0.1", 400)
    led.charge("A0.1", 150)
    led.charge("A0", 100)
    led.check()
    assert led.balance == {"A0": 500, "A0.1": 250} and led.total_spent == 250


def test_ledger_refuses_overdraft_without_side_effects():
    led = Ledger(100, "A0")
    led.open("A0.1")
    with pytest.raises(InsufficientFunds):
        led.charge("A0", 101)
    with pytest.raises(InsufficientFunds):
        led.transfer("A0", "A0.1", 101)
    assert led.balance == {"A0": 100, "A0.1": 0} and led.total_spent == 0
    with pytest.raises(ValueError):
        led.charge("A0", -1)
    with pytest.raises(ValueError):
        led.transfer("A0", "A0.1", -1)


# --------------------------------------------------------------------------- spawning and termination

def fanout_script(alloc=0.05):
    return by_step({
        "A0": [spawn(*[(f"read {d}", alloc, 600) for d in REGION_DOCS], wait=True), term("Westreach")],
        **{f"A0.{i + 1}": [q(d), term(f"facts from {d}")] for i, d in enumerate(REGION_DOCS)},
    })


@pytest.mark.parametrize("scale", SCALES)
def test_spawning_cannot_create_money(scale):
    run = make_run(fanout_script(ALLOC[scale]), input_scale=scale)
    run.execute()
    budget = run.ledger.budget
    bal, spent = replay_balances(run.log.events, budget)
    assert sum(bal.values()) + sum(spent.values()) == budget
    assert run.ledger.total_spent <= budget
    assert bal == run.ledger.balance  # the log alone reproduces the ledger


@pytest.mark.parametrize("scale", SCALES)
def test_allocation_moves_exactly_from_parent_to_child(scale):
    run = make_run(fanout_script(ALLOC[scale]), input_scale=scale)
    run.execute()
    spawned = events_of(run, "AGENT_SPAWNED")
    allocs = [e for e in events_of(run, "RESOURCE_ALLOCATED") if e["kind"] == "allocation"]
    assert [e["amount"] for e in allocs] == [usd(ALLOC[scale])] * 3
    assert all(a["source"] == "A0" and a["target"] == s["child"] for a, s in zip(allocs, spawned))
    # The parent pays each child's fee: spawn_fee + transfer price × (objective + context tokens).
    coord = run.cfg.coord
    for s in spawned:
        assert s["fee"] == coord.spawn_fee + coord.transfer_per_token * s["context_tokens"]


@pytest.mark.parametrize("scale", SCALES)
def test_termination_refunds_the_unused_balance_to_the_parent(scale):
    run = make_run(fanout_script(ALLOC[scale]), input_scale=scale)
    run.execute()
    for t in events_of(run, "AGENT_TERMINATED"):
        if t["agent"] == "A0":
            continue
        refunds = [e for e in events_of(run, "RESOURCE_ALLOCATED") if e["kind"] == "return" and e["source"] == t["agent"]]
        assert t["returned"] == sum(e["amount"] for e in refunds) and t["returned_to"] == "A0"
        assert run.ledger.balance[t["agent"]] == 0
    # Whatever was not spent is back with the root.
    assert run.ledger.balance["A0"] == run.ledger.budget - run.ledger.total_spent


def test_unaffordable_spawn_is_rejected_whole():
    run = make_run(by_step({"A0": [spawn(("a", 0.6, 100), ("b", 0.6, 100)), term()]}))
    run.execute()
    assert not events_of(run, "AGENT_SPAWNED")
    first = events_of(run, "ACTION_COMPLETED")[0]
    assert first["action"] == "SPAWN" and not first["ok"] and "insufficient balance" in first["error"]
    kinds = {e["kind"] for e in events_of(run, "RESOURCE_CONSUMED")}
    assert kinds == {"llm"}  # only the decision steps were charged


@pytest.mark.parametrize("scale", SCALES)
def test_every_charge_is_recomputable_from_the_log(scale):
    run = make_run(fanout_script(ALLOC[scale]), input_scale=scale)
    run.execute()
    cfg, info = run.cfg, run.info
    for e in events_of(run, "RESOURCE_CONSUMED"):
        if e["kind"] == "llm":
            assert e["amount"] == cfg.compute.step_cost(e["in_tokens"], e["out_tokens"])
        elif e["kind"] == "query":
            assert e["amount"] == (info.costs.sql_fee if e["source"] == "sql" else info.costs.doc_fee)
        elif e["kind"] == "spawn":
            fees = {s["fee"] for s in events_of(run, "AGENT_SPAWNED") if s["agent"] == e["agent"]}
            assert e["amount"] in fees
        elif e["kind"] == "message":
            sent = [m for m in events_of(run, "MESSAGE_SENT") if m["agent"] == e["agent"]]
            assert e["amount"] in {cfg.coord.message_fee + cfg.coord.message_per_token * m["tokens"] for m in sent}
    total = sum(e["amount"] for e in events_of(run, "RESOURCE_CONSUMED"))
    assert total == run.ledger.total_spent == events_of(run, "RUN_COMPLETED")[0]["total_spent"]


@pytest.mark.parametrize("scale", SCALES)
def test_a_step_never_overdraws_and_a_small_budget_ends_in_budget_exhausted(scale):
    run = make_run(by_step({"A0": [q("region-northland")] * 30}), reg=regime(budget_usd=0.05), max_steps=100,
                   input_scale=scale)
    run.execute()
    assert run.outcome == "budget_exhausted"
    assert run.ledger.total_spent <= run.ledger.budget
    assert all(v >= 0 for v in run.ledger.balance.values())


def test_a_policy_reporting_more_input_than_the_bound_is_an_infrastructure_error():
    class Liar:
        def decide(self, agent, allowed, max_tokens, run):
            return Decision(term(), in_tokens=10_000_000, out_tokens=10, assistant_content="{}")
    with pytest.raises(ReserveViolation):
        Run(RunConfig(TASKS_BY_ID["T02"], regime(), "single"), Liar(), info()).execute()


def test_child_messages_and_reports_are_charged_to_the_sender():
    doc = "supplier-" + SUPPLIERS[1]["name"].split()[0].lower()
    run = make_run(by_step({"A0": [spawn(("read", 0.05, 600)), wait("all"), term()],
                            "A0.1": [q(doc), term("report text " * 20)]}))
    run.execute()
    report = [m for m in events_of(run, "MESSAGE_SENT") if m["kind"] == "report"][0]
    charged = [e for e in events_of(run, "RESOURCE_CONSUMED") if e["kind"] == "message" and e["agent"] == "A0.1"]
    assert report["fee"] == charged[0]["amount"] == run.cfg.coord.message_fee + run.cfg.coord.message_per_token * report["tokens"]
    assert report["tokens"] == estimate_tokens(("report text " * 20).strip())


# --------------------------------------------------------------------------- policy-declared input bounds (SPEC §3.3)

T01_DOCS = list(TASKS_BY_ID["T01"].routes[0].docs)  # about 12,700 characters in one QUERY result


def long_read():
    return by_step({"A0": [q(*T01_DOCS), term("Westreach")]})


class Undeclared(ScriptedPolicy):
    """The same token model without a declared input bound: only the runtime's own bound is reserved."""
    input_upper_bound = None


class Declaring:
    """Declares a fixed input bound and reports `reported(agent)` input tokens."""

    def __init__(self, declared, reported):
        self.declared, self.reported = declared, reported

    def input_upper_bound(self, agent, run):
        return self.declared

    def decide(self, agent, allowed, max_tokens, run):
        return Decision(term(), self.reported(agent), 10, "{}")


def single_run(policy):
    return Run(RunConfig(TASKS_BY_ID["T02"], regime(), "single"), policy, info())


def comparable(events):
    """A log's simulation content: without wall-clock stamps and the policy's class name."""
    out = []
    for e in events:
        e = {k: v for k, v in e.items() if k != "wall"}
        if e["type"] == "RUN_STARTED":
            e["policy"] = {k: v for k, v in e["policy"].items() if k != "class"}
        out.append(e)
    return out


@pytest.mark.parametrize("scale", [2.5065, 3.0, 4.0])
def test_a_scripted_policy_above_two_tokens_per_estimator_token_stays_within_its_reserve(scale):
    run = make_run(long_read(), input_scale=scale)
    run.execute()
    assert run.outcome == "answered"
    llm = [e for e in events_of(run, "RESOURCE_CONSUMED") if e["kind"] == "llm"]
    assert len(llm) == 2 and all(e["in_tokens"] == math.ceil(e["est_in_tokens"] * scale) for e in llm)
    # The same run exceeds the runtime's own 1-token-per-2-characters bound, so the declaration is what covers it.
    with pytest.raises(ReserveViolation):
        make_run(long_read(), input_scale=scale, policy=Undeclared).execute()


def test_the_calibration_oracle_runs_at_the_grid_point_that_broke_the_pilot_freeze():
    """`freeze --pilot` (r = 2.0052, 36 reasoning tokens) raised ReserveViolation on T01's solo read at the grid point
    r = 1.25 x 2.0052 = 2.5065."""
    meas = measure(default_constants(), Assumptions(input_scale=2.0052, reasoning_tokens=36), tasks=[TASKS_BY_ID["T01"]])
    assert Assumptions(2.5065, 18, 0) in [Assumptions(**p) for p in meas["points"]]
    solo = [m for (_, _, org, _), m in meas["data"].items() if org == "solo@r0"]
    assert len(solo) == 36 and all(m["outcome"] == "answered" and not m["invalid_actions"] for m in solo)


@pytest.mark.parametrize("scale", [1.0, 2.0052])
def test_where_the_runtime_bound_already_covers_the_scripted_input_nothing_changes(scale):
    """The declaration binds only above the runtime's bound, so earlier calibrations are reproduced exactly."""
    a = make_run(fanout_script(), input_scale=scale)
    a.execute()
    b = make_run(fanout_script(), input_scale=scale, policy=Undeclared)
    b.execute()
    assert comparable(a.log.events) == comparable(b.log.events)


def test_usage_above_a_declared_bound_is_still_a_reserve_violation():
    run = single_run(Declaring(50_000, lambda agent: 50_000))
    run.execute()
    assert run.outcome == "answered"
    with pytest.raises(ReserveViolation, match=r"in=50001.*in<=50000"):
        single_run(Declaring(50_000, lambda agent: 50_001)).execute()


def test_a_declared_bound_can_raise_the_reserve_but_never_lower_it():
    run = single_run(Declaring(0, transcript_tokens))  # declares 0, reports its estimator count: still covered
    run.execute()
    assert run.outcome == "answered"
    with pytest.raises(ReserveViolation):
        single_run(Declaring(0, lambda agent: 10_000_000)).execute()


class ReserveSpy(ScriptedPolicy):
    """Checks, at every decision, that the reserve covers the declared input and the offered max_tokens."""

    def decide(self, agent, allowed, max_tokens, run):
        c = run.cfg
        per_out = c.compute.price_out + c.coord.message_per_token
        base = self.input_upper_bound(agent, run) * c.compute.price_in + c.coord.message_fee
        assert base + max_tokens * per_out <= run.ledger.balance[agent.id]
        assert run.min_step_balance(agent) >= base + c.compute.min_step_tokens * per_out
        return super().decide(agent, allowed, max_tokens, run)


@pytest.mark.parametrize("scale", [1.0, 3.0, 4.0])
def test_the_reserve_covers_the_declared_input_when_the_balance_is_tight(scale):
    run = make_run(by_step({"A0": [q("region-northland")] * 30}), reg=regime(budget_usd=0.05), max_steps=100,
                   input_scale=scale, policy=ReserveSpy)
    run.execute()
    assert run.outcome == "budget_exhausted"


@pytest.mark.parametrize("scale", [2.5065, 3.0])
def test_a_scripted_policy_declares_exactly_what_it_reports(scale):
    seen = []

    class Recorder(ScriptedPolicy):
        def decide(self, agent, allowed, max_tokens, run):
            declared = self.input_upper_bound(agent, run)
            d = super().decide(agent, allowed, max_tokens, run)
            seen.append((declared, d.in_tokens))
            return d

    make_run(long_read(), input_scale=scale, policy=Recorder).execute()
    assert len(seen) == 2 and all(declared == reported for declared, reported in seen)


class BoundaryClient:
    """A fake Anthropic client that reports exactly the runtime's input bound (SPEC §3.3), recomputed from the request
    alone, plus `excess` tokens on step `at`."""

    def __init__(self, actions, excess=0, at=0):
        self.actions, self.excess, self.at = actions, excess, at
        self.prev = (0, 0)
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        msgs = kw["messages"]
        step = sum(m["role"] == "assistant" for m in msgs)
        new_chars = len(msgs[-1]["content"])
        if step == 0:
            bound = math.ceil((len(kw["system"]) + new_chars) / 2) + REQUEST_OVERHEAD_TOKENS
        else:
            bound = sum(self.prev) + math.ceil(new_chars / 2) + REQUEST_OVERHEAD_TOKENS
        in_tokens, out_tokens = bound + (self.excess if step == self.at else 0), 20
        self.prev = (in_tokens, out_tokens)
        usage = SimpleNamespace(input_tokens=in_tokens, output_tokens=out_tokens, cache_read_input_tokens=0,
                                cache_creation_input_tokens=0)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(self.actions[step]))],
                               usage=usage, stop_reason="end_turn")


def test_the_live_reserve_is_exactly_the_runtime_bound():
    """Pins the live bound itself: usage equal to it passes at every step, one token more raises."""
    actions = [{"rationale": "think", "action": "WORK", "notes": "thinking"}, term()]
    compute = COMPUTE_OPTIONS[DEFAULT_COMPUTE]
    run = single_run(LLMPolicy(compute, client=BoundaryClient(actions)))
    run.execute()
    assert run.outcome == "answered"
    assert len([e for e in events_of(run, "RESOURCE_CONSUMED") if e["kind"] == "llm"]) == 2
    for at in (0, 1):
        with pytest.raises(ReserveViolation):
            single_run(LLMPolicy(compute, client=BoundaryClient(actions, excess=1, at=at))).execute()


def test_the_live_llm_policy_keeps_the_runtime_bound():
    """LLMPolicy declares no bound, so a live step is reserved exactly as before, and API usage above that reserve is
    an infrastructure error."""
    usage = SimpleNamespace(input_tokens=10_000_000, output_tokens=10, cache_read_input_tokens=0,
                            cache_creation_input_tokens=0)
    reply = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(term()))], usage=usage,
                            stop_reason="end_turn")
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: reply))
    policy = LLMPolicy(COMPUTE_OPTIONS[DEFAULT_COMPUTE], client=client)
    assert getattr(policy, "input_upper_bound", None) is None
    with pytest.raises(ReserveViolation):
        single_run(policy).execute()
