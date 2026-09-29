"""Policies choose one action per agent step.

- `LLMPolicy`: the experimental policy. It makes one Anthropic Messages API call per step,
  with a JSON-schema structured output. Money and latency come from the API-reported usage.
- `ScriptedPolicy`: deterministic, for tests and LLM-free calibration. Input tokens are the
  estimator count of exactly the text an LLM would read, multiplied by `input_scale`. Output
  tokens are the JSON action's tokens plus `reasoning_tokens`.
"""

from __future__ import annotations

import json
import math
import re
import time
from typing import Callable

from devagents.runtime.resources import ComputeOption, estimate_tokens
from devagents.runtime.runtime import ALL_ACTIONS, Agent, Decision, Run


def action_schema(allowed: list[str]) -> dict:
    """Flat JSON schema for one action (structured outputs require additionalProperties: false)."""
    return {
        "type": "object",
        "properties": {
            "rationale": {"type": "string"},
            "action": {"type": "string", "enum": list(allowed)},
            "notes": {"type": "string"},
            "requests": {"type": "array", "items": {
                "type": "object",
                "properties": {"kind": {"type": "string", "enum": ["sql", "doc"]}, "target": {"type": "string"}},
                "required": ["kind", "target"], "additionalProperties": False}},
            "children": {"type": "array", "items": {
                "type": "object",
                "properties": {"objective": {"type": "string"}, "context": {"type": "string"},
                               "budget_usd": {"type": "number"}, "lifetime_s": {"type": "number"}},
                "required": ["objective", "context", "budget_usd", "lifetime_s"], "additionalProperties": False}},
            "wait_for_children": {"type": "boolean"},
            "to": {"type": "string"},
            "content": {"type": "string"},
            "wait_for": {"type": "string", "enum": ["any", "all"]},
            "max_wait_s": {"type": "number"},
            "answer": {"type": "string"},
        },
        "required": ["rationale", "action"],
        "additionalProperties": False,
    }


def parse_action(text: str) -> tuple[dict | None, str]:
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"\{.*\}", text or "", re.DOTALL)
        try:
            obj = json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            obj = None
    if not isinstance(obj, dict):
        return None, "could not parse a JSON object from the reply"
    return obj, ""


def visible_text(content) -> str:
    """The text of one transcript turn as the estimator counts it: plain strings, or the text blocks of an API reply.
    Thinking blocks (and their signatures) are excluded, so the pilot's r = API tokens / estimator tokens is measured
    on the same text the calibration oracle counts."""
    if isinstance(content, str):
        return content
    out = []
    for b in content:
        btype = b.get("type") if isinstance(b, dict) else getattr(b, "type", "")
        if btype == "text":
            out.append(b.get("text", "") if isinstance(b, dict) else getattr(b, "text", ""))
    return "".join(out)


def transcript_tokens(agent: Agent) -> int:
    """Estimator count of the next call's input: the system prompt plus the visible transcript."""
    return estimate_tokens(agent.system) + sum(estimate_tokens(visible_text(m["content"])) for m in agent.transcript)


def _field(b, name: str):
    return b.get(name) if isinstance(b, dict) else getattr(b, name, None)


def clean_content(content: list) -> list:
    """Make a reply safe to re-send: drop empty text blocks and thinking blocks without a signature (both occur on
    refusals and truncated replies, and the API rejects them), keep everything else unchanged. If nothing remains,
    use a placeholder so the assistant turn is never empty."""
    kept = []
    for b in content:
        btype = _field(b, "type")
        if btype == "text" and not (_field(b, "text") or "").strip():
            continue
        if btype == "thinking" and not _field(b, "signature"):
            continue
        kept.append(b)
    return kept or [{"type": "text", "text": "(no output)"}]


class ScriptedPolicy:
    """`script(agent, run, allowed) -> action dict`. If the output would exceed max_tokens, the reply
    is truncated, as a real LLM reply would be."""

    def __init__(self, script: Callable[[Agent, Run, list[str]], dict], reasoning_tokens: int = 0,
                 input_scale: float = 1.0):
        self.script = script
        self.reasoning_tokens = reasoning_tokens
        self.input_scale = input_scale

    def decide(self, agent: Agent, allowed: list[str], max_tokens: int, run: Run) -> Decision:
        action = self.script(agent, run, allowed)
        text = json.dumps(action)
        est_in = transcript_tokens(agent)
        in_tokens = math.ceil(est_in * self.input_scale)
        out = estimate_tokens(text) + self.reasoning_tokens
        if out > max_tokens:
            return Decision(None, in_tokens, max_tokens, text, error="output truncated at max_tokens", truncated=True,
                            est_in_tokens=est_in)
        return Decision(action, in_tokens, out, text, est_in_tokens=est_in, est_visible_out_tokens=estimate_tokens(text))


class LLMPolicy:
    """One Messages API call per agent step. The Anthropic SDK is imported only here."""

    def __init__(self, compute: ComputeOption, client=None, structured: bool = True, max_retries: int = 4):
        if client is None:
            import anthropic  # optional dependency: only the real experiment needs it
            client = anthropic.Anthropic(max_retries=max_retries)
        self.client = client
        self.compute = compute
        self.structured = structured

    def request(self, agent: Agent, allowed: list[str], max_tokens: int) -> dict:
        output_config: dict = {"effort": self.compute.effort}
        if self.structured:
            # The same six-action schema in every mode and step (prompt parity, SPEC §6); the runtime rejects
            # actions the mode does not allow, as invalid, charged steps.
            output_config["format"] = {"type": "json_schema", "schema": action_schema(ALL_ACTIONS)}
        return dict(model=self.compute.model, max_tokens=max_tokens, system=agent.system,
                    messages=[{"role": m["role"], "content": m["content"]} for m in agent.transcript],
                    output_config=output_config)

    def decide(self, agent: Agent, allowed: list[str], max_tokens: int, run: Run) -> Decision:
        est_in = transcript_tokens(agent)
        t0 = time.monotonic()
        resp = self.client.messages.create(**self.request(agent, allowed, max_tokens))
        wall = time.monotonic() - t0
        u = resp.usage
        in_tokens = (u.input_tokens + (getattr(u, "cache_read_input_tokens", 0) or 0)
                     + (getattr(u, "cache_creation_input_tokens", 0) or 0))
        # Append the full content (thinking blocks included) so the history stays append-only.
        content = clean_content(list(resp.content or []))
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        meta = dict(wall_s=wall, est_in_tokens=est_in, est_visible_out_tokens=estimate_tokens(text))
        if resp.stop_reason == "refusal":
            return Decision(None, in_tokens, u.output_tokens, content, error="the model declined (stop_reason=refusal)",
                            **meta)
        if resp.stop_reason == "max_tokens":
            return Decision(None, in_tokens, u.output_tokens, content, error="output truncated at max_tokens",
                            truncated=True, **meta)
        action, err = parse_action(text)
        return Decision(action, in_tokens, u.output_tokens, content, error=err, **meta)
