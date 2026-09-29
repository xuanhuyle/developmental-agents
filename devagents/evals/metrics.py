"""Grading, per-run metrics (derived only from the event log), and fitness (SPEC §3.4, §9).

Raw metrics never contain fitness weights. `fitness()` can recompute any stored run's score
with any weights.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from devagents.environment.tasks import Task
from devagents.runtime.resources import to_usd

_STOP = {"the", "region", "supplier", "city", "ceo", "mr", "ms", "dr", "of", "is"}
CAP_REASONS = {"max_steps", "context_exhausted"}


def _norm(s: str) -> str:
    s = s.casefold().replace("’", "'")
    s = re.sub(r"[^\w ]+", " ", s)
    return " ".join(w for w in s.split() if w not in _STOP)


def grade(task: Task, answer: str | None) -> float:
    """Frozen normalizer. Numbers: exactly one number in the answer, within relative tolerance 1e-6.
    Names: normalized equality with the answer or a listed alias."""
    if not answer:
        return 0.0
    if task.kind == "number":
        nums = re.findall(r"-?\d+(?:\.\d+)?", answer.replace(",", ""))
        if len(nums) != 1:
            return 0.0
        truth = float(task.answer)
        return 1.0 if abs(float(nums[0]) - truth) <= 1e-6 * max(1.0, abs(truth)) else 0.0
    accepted = {_norm(a) for a in (task.answer, *task.aliases)}
    return 1.0 if _norm(answer) in accepted else 0.0


def query_intervals(events: list[dict]) -> list[tuple[float, float, str]]:
    """(start, end, agent) of each completed QUERY's source processing, which excludes the decision latency."""
    started = {(e["agent"], e["step"]): e for e in events if e["type"] == "ACTION_STARTED" and e["action"] == "QUERY"}
    out = []
    for e in events:
        if e["type"] == "ACTION_COMPLETED" and e["action"] == "QUERY" and e["ok"] and not e["discarded"]:
            s = started[(e["agent"], e["step"])]
            out.append((s["t"] + s["llm_latency_s"], e["t"], e["agent"]))
    return out


def parallel_division(events: list[dict]) -> bool:
    """True if at some simulated instant two different agents were each processing sources."""
    iv = sorted(query_intervals(events))
    for i, (s1, e1, a1) in enumerate(iv):
        for s2, e2, a2 in iv[i + 1:]:
            if s2 >= e1:
                break
            if a1 != a2 and s2 < e1 and s1 < e2:
                return True
    return False


def metrics_from_events(events: list[dict]) -> dict:
    """Reconstruct every per-run metric from the append-only log alone."""
    start = next(e for e in events if e["type"] == "RUN_STARTED")
    end = next((e for e in events if e["type"] == "RUN_COMPLETED"), None)
    created = [e for e in events if e["type"] == "AGENT_CREATED"]
    parents = {e["agent"]: e["parent"] for e in created}

    spend = {"llm": 0, "query": 0, "spawn": 0, "message": 0}
    llm_calls = in_tok = out_tok = 0
    for e in events:
        if e["type"] == "RESOURCE_CONSUMED":
            spend[e["kind"]] += e["amount"]
            if e["kind"] == "llm":
                llm_calls += 1
                in_tok += e["in_tokens"]
                out_tok += e["out_tokens"]

    queries = [e for e in events if e["type"] == "INFORMATION_QUERIED"]
    messages = [e for e in events if e["type"] == "MESSAGE_SENT"]
    terms = [e for e in events if e["type"] == "AGENT_TERMINATED"]
    completed = [e for e in events if e["type"] == "ACTION_COMPLETED"]
    reasons = sorted(e["reason"] for e in terms)

    changes = sorted([(e["t"], 1, e["seq"]) for e in created] + [(e["t"], -1, e["seq"]) for e in terms])
    live = peak = 0
    for _, delta, _ in changes:
        live += delta
        peak = max(peak, live)

    return {
        "run_id": start["run_id"],
        "task_id": start["task_id"],
        "task_class": start["task_class"],
        "regime": start["regime"],
        "mode": start["mode"],
        "repeat": start.get("repeat", 0),
        "compute": start["compute"]["id"],
        "budget_usd": to_usd(start["budget"]),
        "deadline_s": start["deadline_s"],
        "value_of_time": start["value_of_time"],
        "answer": end["answer"] if end else None,
        "outcome": end["outcome"] if end else "incomplete",
        "quality": end["quality"] if end else 0.0,
        "elapsed_s": end["elapsed_s"] if end else start["deadline_s"],
        "wall_s": round(end["wall"] - start["wall"], 3) if end else None,
        "money_usd": to_usd(sum(spend.values())),
        "llm_usd": to_usd(spend["llm"]),
        "query_usd": to_usd(spend["query"]),
        "spawn_usd": to_usd(spend["spawn"]),
        "message_usd": to_usd(spend["message"]),
        "coordination_usd": to_usd(spend["spawn"] + spend["message"]),
        "llm_calls": llm_calls,
        "in_tokens": in_tok,
        "out_tokens": out_tok,
        "agents": len(created),
        "spawned": len(created) > 1,
        "parallel": parallel_division(events),
        "max_live_agents": peak,
        "max_depth": max((e["depth"] for e in created), default=0),
        "messages": sum(1 for m in messages if m["kind"] == "message"),
        "reports": sum(1 for m in messages if m["kind"] == "report"),
        "message_tokens": sum(m["tokens"] for m in messages),
        "sql_queries": sum(1 for q in queries if q["kind"] == "structured"),
        "doc_queries": sum(1 for q in queries if q["kind"] == "unstructured"),
        "sql_tokens": sum(q["tokens"] for q in queries if q["kind"] == "structured"),
        "doc_tokens": sum(q["tokens"] for q in queries if q["kind"] == "unstructured"),
        "invalid_actions": sum(1 for e in completed if not e["ok"] and not e["discarded"]),
        "discarded_actions": sum(1 for e in completed if e["discarded"]),
        "cap_hits": sum(1 for r in reasons if r in CAP_REASONS),
        "termination_reasons": reasons,
        "lineage": sorted([p, c] for c, p in parents.items() if p is not None),
    }


@dataclass(frozen=True)
class Weights:
    task_value: float = 1.0  # V
    value_of_time: float = 0.0  # $ per second
    w_coord: float = 0.0
    failure_penalty: float = 1.0


def fitness(m: dict, w: Weights) -> float:
    failed = m["outcome"] != "answered"
    elapsed = m["deadline_s"] if failed else m["elapsed_s"]
    return (m["quality"]
            - m["money_usd"] / w.task_value
            - w.value_of_time * elapsed / w.task_value
            - w.w_coord * m["coordination_usd"] / w.task_value
            - w.failure_penalty * failed)
