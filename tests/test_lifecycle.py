"""Lifecycle and simulation semantics (SPEC §3.2, §5, §6): time, concurrency, delivery, waiting, expiry, cascades,
mode rules, lineage and determinism."""

from devagents.environment.world import REGIONS, region_doc_id
from devagents.evals.metrics import metrics_from_events
from tests.helpers import by_step, events_of, make_run, msg, q, regime, spawn, term, wait, work

DOCS = [region_doc_id(r) for r in REGIONS]


def solo_script():
    return by_step({"A0": [q(*DOCS), term("Westreach")]})


def fanout_script(k=3, wait_kind="continuation"):
    buckets = [DOCS[i::k] for i in range(k)]
    root = [spawn(*[(f"read {','.join(b)}", 0.05, 900) for b in buckets], wait=wait_kind == "continuation")]
    if wait_kind == "explicit":
        root.append(wait("all"))
    root.append(term("Westreach"))
    return by_step({"A0": root, **{f"A0.{i + 1}": [q(*b), term("facts")] for i, b in enumerate(buckets)}})


def test_division_trades_money_for_time_on_independent_documents():
    solo, fan = make_run(solo_script()), make_run(fanout_script())
    solo.execute(), fan.execute()
    ms, mf = metrics_from_events(solo.log.events), metrics_from_events(fan.log.events)
    assert ms["quality"] == mf["quality"] == 1.0
    assert mf["elapsed_s"] < ms["elapsed_s"]  # concurrency comes only from multiple agents
    assert mf["money_usd"] > ms["money_usd"]  # and it is not free
    assert mf["parallel"] and not ms["parallel"] and mf["max_live_agents"] == 4


def test_multi_source_query_latencies_add_up():
    run = make_run(by_step({"A0": [q(*DOCS[:3]), term()]}))
    run.execute()
    queried = events_of(run, "INFORMATION_QUERIED")
    started = next(e for e in events_of(run, "ACTION_STARTED") if e["action"] == "QUERY")
    assert abs(started["action_latency_s"] - sum(e["latency_s"] for e in queried)) < 1e-3


def test_continuation_and_explicit_wait_both_wake_after_all_reports():
    for kind in ("continuation", "explicit"):
        run = make_run(fanout_script(wait_kind=kind))
        run.execute()
        reports = [m for m in events_of(run, "MESSAGE_SENT") if m["kind"] == "report"]
        last_delivery = max(m["deliver_at"] for m in reports)
        final = [e for e in events_of(run, "ACTION_STARTED") if e["agent"] == "A0" and e["action"] == "TERMINATE"][0]
        assert abs(final["t"] - last_delivery) < 1e-6, kind  # woke exactly when the last report arrived
        llm_steps = [e for e in events_of(run, "RESOURCE_CONSUMED") if e["kind"] == "llm" and e["agent"] == "A0"]
        assert len(llm_steps) == (2 if kind == "continuation" else 3)  # the continuation saves one decision


def test_messages_are_invisible_before_delivery_and_wake_waiting_agents():
    run = make_run(by_step({"A0": [spawn(("wait for a message", 0.1, 900)), msg("A0.1", "the answer is 7"), wait("all"),
                                   term()],
                            "A0.1": [wait("any"), term("got it")]}))
    run.execute()
    sent = [m for m in events_of(run, "MESSAGE_SENT") if m["kind"] == "message"][0]
    child_steps = [e for e in events_of(run, "ACTION_STARTED") if e["agent"] == "A0.1"]
    assert child_steps[1]["t"] == sent["deliver_at"]  # woke at delivery, not before
    obs = run.agents["A0.1"].transcript[2]["content"]
    assert "the answer is 7" in obs and "the answer is 7" not in run.agents["A0.1"].transcript[0]["content"]


def test_child_lifetime_expiry_discards_in_flight_work_and_notifies_parent():
    run = make_run(by_step({"A0": [spawn(("slow reader", 0.1, 5), wait=True), term()],
                            "A0.1": [q(*DOCS), term("too late")]}))
    run.execute()
    t = [e for e in events_of(run, "AGENT_TERMINATED") if e["agent"] == "A0.1"][0]
    assert t["reason"] == "lifetime_expired"
    discarded = [e for e in events_of(run, "ACTION_COMPLETED") if e["agent"] == "A0.1" and e["discarded"]]
    assert discarded and not [e for e in events_of(run, "INFORMATION_QUERIED") if e["agent"] == "A0.1"]
    assert run.ledger.balance["A0.1"] == 0
    notices = [m for m in run.messages if m.kind == "notice" and m.recipient == "A0"]
    assert notices and "lifetime_expired" in notices[0].content


def test_root_termination_cascades_and_nothing_starts_afterwards():
    run = make_run(by_step({"A0": [spawn(("a", 0.1, 900), ("b", 0.1, 900)), term("early")],
                            "A0.1": [q(*DOCS), term()], "A0.2": [work(), work(), q(*DOCS), term()]}))
    run.execute()
    end = events_of(run, "RUN_COMPLETED")[0]["t"]
    for e in events_of(run, "ACTION_STARTED"):
        assert e["t"] < end or e["agent"] == "A0"
    reasons = {e["agent"]: e["reason"] for e in events_of(run, "AGENT_TERMINATED")}
    assert reasons == {"A0.1": "ancestor_terminated", "A0.2": "ancestor_terminated", "A0": "answered"}
    for aid in ("A0.1", "A0.2"):
        assert run.ledger.balance[aid] == 0
    terms = events_of(run, "AGENT_TERMINATED")
    assert [e["agent"] for e in terms][-1] == "A0"  # descendants first


def test_root_deadline_is_a_failure_scored_at_the_deadline():
    run = make_run(by_step({"A0": [q(*DOCS), term()]}), reg=regime(deadline_s=30.0))
    run.execute()
    m = metrics_from_events(run.log.events)
    assert m["outcome"] == "deadline" and m["quality"] == 0.0 and m["elapsed_s"] == 30.0


def test_agent_with_live_children_is_suspended_not_killed_when_it_cannot_afford_a_step():
    run = make_run(by_step({"A0": [spawn(("take nearly everything", 0.985, 900)), work(), term("done")],
                            "A0.1": [q(DOCS[0]), term("r")]}))
    run.execute()
    assert run.outcome == "answered"
    root_steps = [e["action"] for e in events_of(run, "ACTION_STARTED") if e["agent"] == "A0"]
    assert root_steps == ["SPAWN", "WORK", "TERMINATE"]


def test_step_cap_is_logged_as_a_cap_hit():
    run = make_run(by_step({"A0": [work()]}), max_steps=3)
    run.execute()
    m = metrics_from_events(run.log.events)
    assert m["outcome"] == "max_steps" and m["cap_hits"] == 1


# --------------------------------------------------------------------------- mode rules

def test_single_mode_cannot_spawn():
    run = make_run(by_step({"A0": [spawn(("x", 0.1, 100)), term()]}), mode="single")
    run.execute()
    first = events_of(run, "ACTION_COMPLETED")[0]
    assert not first["ok"] and "not available" in first["error"] and len(run.agents) == 1


def test_central_mode_forces_spawn_first_with_the_fixed_allocation_rule():
    run = make_run(by_step({"A0": [q(DOCS[0]), spawn(("a", 0.9, 1), ("b", 0.9, 1)), term()],
                            "A0.1": [q(DOCS[0]), term()], "A0.2": [q(DOCS[1]), term()]}), mode="central")
    run.execute()
    actions = [(e["action"], e["ok"]) for e in events_of(run, "ACTION_COMPLETED") if e["agent"] == "A0"]
    assert actions[0] == ("QUERY", False)  # not allowed before the decomposition
    assert actions[1] == ("SPAWN", True)
    allocs = [e["amount"] for e in events_of(run, "RESOURCE_ALLOCATED") if e["kind"] == "allocation"]
    assert len(set(allocs)) == 1 and allocs[0] < 0.5 * run.ledger.budget / 2 + 1  # equal shares of 50%, not 0.9
    created = events_of(run, "AGENT_CREATED")[1:]
    spawn_done = [e for e in events_of(run, "ACTION_COMPLETED") if e["action"] == "SPAWN" and e["ok"]][0]
    assert all(abs((c["deadline"] - spawn_done["t"]) - 0.6 * (run.cfg.regime.deadline_s - 0)) < 20 for c in created)
    # children may not spawn
    assert "SPAWN" not in run.allowed_actions(run.agents["A0.1"])


def test_router_may_spawn_only_as_its_first_valid_action():
    run = make_run(by_step({"A0": [q(DOCS[0]), spawn(("a", 0.1, 100)), term()]}), mode="router")
    run.execute()
    spawn_result = [e for e in events_of(run, "ACTION_COMPLETED") if e["action"] == "SPAWN"][0]
    assert not spawn_result["ok"] and len(run.agents) == 1
    run = make_run(by_step({"A0": [spawn(("a", 0.1, 900), wait=True), spawn(("b", 0.1, 900)), term()],
                            "A0.1": [q(DOCS[0]), term()]}), mode="router")
    run.execute()
    oks = [e["ok"] for e in events_of(run, "ACTION_COMPLETED") if e["action"] == "SPAWN"]
    assert oks == [True, False]


def test_concurrency_cap_rejects_the_whole_spawn():
    kids = [(f"c{i}", 0.01, 100) for i in range(9)]  # K = 8 children max per SPAWN, 9 live agents max
    run = make_run(by_step({"A0": [spawn(*kids), term()]}))
    run.execute()
    assert len(run.agents) == 1 and "1 to 8" in events_of(run, "ACTION_COMPLETED")[0]["error"]


def test_permissions_are_inherited_and_never_widened():
    run = make_run(by_step({"A0": [spawn(("a", 0.1, 900), wait=True), term()],
                            "A0.1": [q("no-such-doc"), q(DOCS[0]), term()]}))
    run.execute()
    created = {e["agent"]: set(e["permissions"]) for e in events_of(run, "AGENT_CREATED")}
    assert created["A0.1"] == created["A0"]
    bad = [e for e in events_of(run, "ACTION_COMPLETED") if e["agent"] == "A0.1" and not e["ok"]][0]
    assert "unknown source" in bad["error"]


# --------------------------------------------------------------------------- lineage and determinism

def test_events_reconstruct_lineage():
    run = make_run(by_step({"A0": [spawn(("a", 0.3, 900), ("b", 0.1, 900), wait=True), term()],
                            "A0.1": [spawn(("grandchild", 0.05, 600), wait=True), term()],
                            "A0.1.1": [q(DOCS[0]), term()], "A0.2": [q(DOCS[1]), term()]}))
    run.execute()
    m = metrics_from_events(run.log.events)
    assert m["lineage"] == [["A0", "A0.1"], ["A0", "A0.2"], ["A0.1", "A0.1.1"]]
    assert m["max_depth"] == 2
    for a in run.agents.values():
        assert sorted(a.children) == sorted(c for p, c in m["lineage"] if p == a.id)


def test_runs_are_deterministic():
    def strip(events):
        return [{k: v for k, v in e.items() if k != "wall"} for e in events]
    a, b = make_run(fanout_script()), make_run(fanout_script())
    a.execute(), b.execute()
    assert strip(a.log.events) == strip(b.log.events)
