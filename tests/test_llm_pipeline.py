"""The real LLMPolicy, driven by a fake Anthropic client, through the runner and the report. No network is used."""

import json
import re

from devagents.agents.policies import LLMPolicy, action_schema
from devagents.config import default_constants, load_frozen
from devagents.environment.tasks import TASKS_BY_ID
from devagents.evals.experiment import plan, run_suite, make_manifest
from devagents.evals.metrics import metrics_from_events
from devagents.evals.report import build_report, format_markdown
from devagents.runtime.events import read_events
from devagents.runtime.resources import estimate_tokens
from devagents.runtime.runtime import MODES


class Block:
    def __init__(self, text):
        self.type, self.text = "text", text


class Usage:
    def __init__(self, i, o):
        self.input_tokens, self.output_tokens = i, o
        self.cache_read_input_tokens = self.cache_creation_input_tokens = 0


class Response:
    def __init__(self, content, usage, stop_reason="end_turn"):
        self.content, self.usage, self.stop_reason = content, usage, stop_reason


def _chars(kw) -> int:
    n = len(kw["system"])
    for m in kw["messages"]:
        n += len(m["content"]) if isinstance(m["content"], str) else sum(len(b.text) for b in m["content"])
    return n


class FakeModel:
    """Reads the request the way a model would (the brief, the step count, the allowed actions) and answers."""

    def __init__(self, refuse_first_child_step=False):
        self.requests = []
        self.refuse = refuse_first_child_step

    def create(self, **kw):
        self.requests.append(kw)
        allowed = kw["output_config"]["format"]["schema"]["properties"]["action"]["enum"]
        first = kw["messages"][0]["content"]
        step = sum(1 for m in kw["messages"] if m["role"] == "assistant")
        if self.refuse and first.startswith("You are agent") and step == 0:
            self.refuse = False
            return Response([Block("")], Usage(_chars(kw) // 4, 5), "refusal")
        action = self.root(first, step, allowed) if first.startswith("Task ") else self.child(first, step)
        text = json.dumps(action)
        return Response([Block(text)], Usage(_chars(kw) // 4 + 5, estimate_tokens(text) + 40))

    def root(self, brief, step, allowed):
        task = TASKS_BY_ID[re.match(r"Task (\w+)\.", brief).group(1)]
        route = task.routes[0]
        if step == 0 and "SPAWN" in allowed and (allowed == ["SPAWN"] or len(route.docs) >= 4):
            docs = list(route.docs) or ["travel-policy"]
            halves = [docs[i::2] for i in range(min(2, len(docs)))]
            return {"rationale": "divide", "action": "SPAWN", "wait_for_children": True,
                    "children": [{"objective": f"Read {' '.join(h)} for: {task.question}", "context": "",
                                  "budget_usd": 0.1, "lifetime_s": 600} for h in halves]}
        if step == 0 and "QUERY" in allowed:
            reqs = [{"kind": "sql", "target": s} for s in route.sql] + [{"kind": "doc", "target": d} for d in route.docs]
            return {"rationale": "read", "action": "QUERY", "requests": reqs}
        return {"rationale": "answer", "action": "TERMINATE", "answer": task.answer}

    def child(self, brief, step):
        docs = re.findall(r"(?:region|supplier|travel)-[a-z]+", brief.split("Context from")[0])
        if step == 0 and docs:
            return {"rationale": "read", "action": "QUERY", "requests": [{"kind": "doc", "target": d} for d in docs]}
        return {"rationale": "report", "action": "TERMINATE", "answer": "the facts I found"}


class FakeClient:
    def __init__(self, model):
        self.messages = model


def test_request_shape_and_append_only_transcript(tmp_path):
    model = FakeModel()
    c = default_constants()
    policy = LLMPolicy(c.compute, client=FakeClient(model))
    configs = plan([TASKS_BY_ID["T01"]], c, ["developmental"], 1, regimes=["urgent"])
    run_suite(configs, policy, c, tmp_path, make_manifest("test", configs, c, True, ""))
    req = model.requests[0]
    assert req["model"] == c.compute.model and 0 < req["max_tokens"] <= c.compute.max_output_tokens
    assert req["output_config"]["effort"] == c.compute.effort
    assert req["output_config"]["format"]["schema"] == action_schema(["WORK", "QUERY", "SPAWN", "MESSAGE", "WAIT", "TERMINATE"])
    for r in model.requests:  # alternating turns, first is user, last is user
        roles = [m["role"] for m in r["messages"]]
        assert roles[0] == "user" and roles[-1] == "user" and all(a != b for a, b in zip(roles, roles[1:]))
    events = read_events(next((tmp_path / "events").glob("*.jsonl")))
    llm = [e for e in events if e["type"] == "RESOURCE_CONSUMED" and e["kind"] == "llm"]
    assert all(e["est_in_tokens"] > 0 for e in llm)  # the pilot can measure the tokenizer ratio


def test_a_refusal_is_a_charged_invalid_step_not_a_crash(tmp_path):
    model = FakeModel(refuse_first_child_step=True)
    c = default_constants()
    configs = plan([TASKS_BY_ID["T01"]], c, ["developmental"], 1, regimes=["urgent"])
    run_suite(configs, LLMPolicy(c.compute, client=FakeClient(model)), c, tmp_path, make_manifest("t", configs, c, True, ""))
    m = metrics_from_events(read_events(next((tmp_path / "events").glob("*.jsonl"))))
    assert m["invalid_actions"] == 1 and m["outcome"] == "answered"


def test_full_pipeline_runner_to_report(tmp_path):
    c = default_constants()
    tasks = [TASKS_BY_ID[t] for t in ("T02", "T01", "T09")]
    configs = plan(tasks, c, list(MODES), 2)
    summary = run_suite(configs, LLMPolicy(c.compute, client=FakeClient(FakeModel())), c, tmp_path,
                        make_manifest("test", configs, c, True, ""), workers=4)
    assert summary == {"planned": 48, "completed": 48, "failed": 0}
    # resuming does not repeat completed runs
    again = run_suite(configs, LLMPolicy(c.compute, client=FakeClient(FakeModel())), c, tmp_path,
                      make_manifest("test", configs, c, True, ""))
    assert again["completed"] == 48 and len((tmp_path / "runs.jsonl").read_text().splitlines()) == 48
    rep = build_report(tmp_path, load_frozen(), frozen_ok=False, n_boot=200)
    assert rep["exploratory"] and rep["n_runs"] == 48
    assert rep["validity"]["iii_audit_parity"], rep["audit_problems"]
    assert set(rep["criteria"]["criteria"]) >= {"1_always_spawn", "2_never_spawn", "3a_within_regime"}
    by_mode = {(r["class"], r["regime"], r["mode"]): r for r in rep["table"]}
    assert by_mode[("solo", "urgent", "single")]["quality"] == 1.0
    assert by_mode[("parallel", "urgent", "central")]["spawned"] == 1.0
    md = format_markdown(rep)
    assert "EXPLORATORY" in md and "Pareto frontier" in md


def test_report_on_a_pilot_suite_does_not_apply_section_8(tmp_path):
    from devagents.environment.tasks import PILOT_TASKS
    from devagents.evals.experiment import pilot_stats
    c = default_constants()
    configs = plan(PILOT_TASKS, c, ["single", "central"], 2)
    run_suite(configs, LLMPolicy(c.compute, client=FakeClient(FakeModel())), c, tmp_path,
              make_manifest("pilot", configs, c, True, ""))
    rep = build_report(tmp_path, load_frozen(), frozen_ok=False, n_boot=50)
    assert rep["verdict"].startswith("not applicable") and rep["exploratory"]
    stats = pilot_stats(tmp_path)  # the pilot statistics the freeze consumes
    assert stats["runs"] == 24 and stats["input_scale"] > 0 and stats["single_accuracy"]["solo"] == 1.0
