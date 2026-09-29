"""Small builders shared by the tests. The scripts are explicit, so every test states the behaviour it exercises."""

from __future__ import annotations

from dataclasses import replace

from devagents.agents.policies import ScriptedPolicy
from devagents.environment.sources import InformationEnvironment
from devagents.environment.tasks import REGIMES, TASKS_BY_ID
from devagents.environment.world import load_world
from devagents.runtime.runtime import Run, RunConfig

WORLD = load_world()


def info():
    return InformationEnvironment(WORLD)


def regime(name="urgent", **changes):
    return replace(REGIMES[name], **changes)


def make_run(script, task="T01", mode="developmental", reg=None, reasoning=50, **cfg):
    config = RunConfig(TASKS_BY_ID[task], reg or regime(), mode, **cfg)
    return Run(config, ScriptedPolicy(script, reasoning_tokens=reasoning), info())


def by_step(plans: dict):
    """plans: agent id -> list of actions (the last one repeats)."""
    def script(agent, run, allowed):
        plan = plans[agent.id]
        return plan[min(agent.steps, len(plan) - 1)]
    return script


def q(*docs, sql=None):
    reqs = ([{"kind": "sql", "target": sql}] if sql else []) + [{"kind": "doc", "target": d} for d in docs]
    return {"rationale": "read", "action": "QUERY", "requests": reqs}


def spawn(*children, wait=False):
    return {"rationale": "divide", "action": "SPAWN", "wait_for_children": wait,
            "children": [{"objective": o, "context": "", "budget_usd": b, "lifetime_s": l} for o, b, l in children]}


def term(answer="x"):
    return {"rationale": "done", "action": "TERMINATE", "answer": answer}


def wait(for_="all", max_wait=None):
    a = {"rationale": "wait", "action": "WAIT", "wait_for": for_}
    if max_wait is not None:
        a["max_wait_s"] = max_wait
    return a


def work():
    return {"rationale": "think", "action": "WORK", "notes": "thinking"}


def msg(to, content="hello"):
    return {"rationale": "tell", "action": "MESSAGE", "to": to, "content": content}


def events_of(run, type_):
    return [e for e in run.log.events if e["type"] == type_]
