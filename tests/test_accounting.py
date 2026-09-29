"""Resource accounting invariants (SPEC §3.3): nothing creates money, every charge is accounted for, and
allocation and refunds move money exactly."""

import pytest

from devagents.runtime.resources import InsufficientFunds, Ledger, estimate_tokens, usd
from devagents.runtime.runtime import ReserveViolation
from devagents.environment.world import SUPPLIERS
from tests.helpers import by_step, events_of, make_run, q, spawn, term, wait

REGION_DOCS = ["region-northland", "region-eastmarch", "region-southvale"]


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


def test_spawning_cannot_create_money():
    run = make_run(fanout_script())
    run.execute()
    budget = run.ledger.budget
    bal, spent = replay_balances(run.log.events, budget)
    assert sum(bal.values()) + sum(spent.values()) == budget
    assert run.ledger.total_spent <= budget
    assert bal == run.ledger.balance  # the log alone reproduces the ledger


def test_allocation_moves_exactly_from_parent_to_child():
    run = make_run(fanout_script(alloc=0.05))
    run.execute()
    spawned = events_of(run, "AGENT_SPAWNED")
    allocs = [e for e in events_of(run, "RESOURCE_ALLOCATED") if e["kind"] == "allocation"]
    assert [e["amount"] for e in allocs] == [usd(0.05)] * 3
    assert all(a["source"] == "A0" and a["target"] == s["child"] for a, s in zip(allocs, spawned))
    # The parent pays each child's fee: spawn_fee + transfer price × (objective + context tokens).
    coord = run.cfg.coord
    for s in spawned:
        assert s["fee"] == coord.spawn_fee + coord.transfer_per_token * s["context_tokens"]


def test_termination_refunds_the_unused_balance_to_the_parent():
    run = make_run(fanout_script())
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


def test_every_charge_is_recomputable_from_the_log():
    run = make_run(fanout_script())
    run.execute()
    cfg, info = run.cfg, run.info
    for e in events_of(run, "RESOURCE_CONSUMED"):
        if e["kind"] == "llm":
            assert e["amount"] == cfg.compute.step_cost(e["in_tokens"], e["out_tokens"])
        elif e["kind"] == "query":
            assert e["amount"] == (info.costs.sql_fee if e["source"] == "sql" else info.costs.doc_fee)
        elif e["kind"] == "message":
            sent = [m for m in events_of(run, "MESSAGE_SENT") if m["agent"] == e["agent"]]
            assert e["amount"] in {cfg.coord.message_fee + cfg.coord.message_per_token * m["tokens"] for m in sent}
    total = sum(e["amount"] for e in events_of(run, "RESOURCE_CONSUMED"))
    assert total == run.ledger.total_spent == events_of(run, "RUN_COMPLETED")[0]["total_spent"]


def test_a_step_never_overdraws_and_a_small_budget_ends_in_budget_exhausted():
    from tests.helpers import regime
    run = make_run(by_step({"A0": [q("region-northland")] * 30}), reg=regime(budget_usd=0.05), max_steps=100)
    run.execute()
    assert run.outcome == "budget_exhausted"
    assert run.ledger.total_spent <= run.ledger.budget
    assert all(v >= 0 for v in run.ledger.balance.values())


def test_a_policy_reporting_more_input_than_the_bound_is_an_infrastructure_error():
    class Liar:
        def decide(self, agent, allowed, max_tokens, run):
            from devagents.runtime.runtime import Decision
            return Decision(term(), in_tokens=10_000_000, out_tokens=10, assistant_content="{}")
    from devagents.runtime.runtime import Run, RunConfig
    from devagents.environment.tasks import TASKS_BY_ID
    from tests.helpers import info, regime
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
