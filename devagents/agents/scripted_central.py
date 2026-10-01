"""Experiment 0c's scripted `central` baseline (SPEC_0C.md §3).

`ScriptedFirstSpawnPolicy` wraps the experiment's policy (the unchanged `LLMPolicy`, or a test double) and changes
exactly one decision: the first step of the root agent in `central` mode. That step returns a pre-registered SPAWN
instead of asking the model. Everything else — the root's later steps, every child, and every step in every other
mode — is delegated to the wrapped policy unchanged, so `single` and `developmental` send byte-identical requests.

The scripted step is not free. It is decided by an internal `ScriptedPolicy`, so it is priced exactly as the
calibration prices oracle steps (estimator input tokens × input_scale, plus the JSON action's tokens and the declared
reasoning tokens), at the pre-registered assumptions; the runtime charges it, logs it as an LLM step with its latency,
and appends it to the root's transcript. A `SCRIPTED_ACTION` event marks it explicitly in the log.
"""

from __future__ import annotations

import copy
import math

from devagents.agents.policies import ScriptedPolicy, visible_text
from devagents.runtime.runtime import REQUEST_OVERHEAD_TOKENS, Agent, Decision, Run, policy_config, sec

DECLARED_KEY = "central_first_step"
DECLARED_VALUE = "scripted"


class ScriptedFirstSpawnPolicy:
    def __init__(self, inner, actions: dict[str, dict], input_scale: float, reasoning_tokens: int):
        """`actions` maps a task id to the exact SPAWN action dict the `central` root takes as its first step."""
        self.inner = inner
        self.actions = {k: dict(v) for k, v in actions.items()}
        self.input_scale = input_scale
        self.reasoning_tokens = reasoning_tokens

    # Attributes the runner and the request builder read from the policy are the wrapped policy's.
    @property
    def compute(self):
        return getattr(self.inner, "compute", None)

    @property
    def structured(self):
        return getattr(self.inner, "structured", None)

    def declared_asymmetries(self) -> dict[str, dict]:
        return {"central": {DECLARED_KEY: DECLARED_VALUE}}

    def config_for_mode(self, mode: str | None) -> dict:
        """The wrapped policy's configuration, plus the one declared entry in `central` runs."""
        cfg = policy_config(self.inner)
        if mode == "central":
            cfg[DECLARED_KEY] = DECLARED_VALUE
        return cfg

    def _scripted(self, agent: Agent, run: Run) -> ScriptedPolicy | None:
        if run.cfg.mode != "central" or agent.parent is not None or agent.steps != 0:
            return None
        action = self.actions.get(run.cfg.task.id)
        if action is None:
            raise ValueError(f"no pre-registered scripted SPAWN for task {run.cfg.task.id} in central mode")
        return ScriptedPolicy(lambda a, r, allowed: copy.deepcopy(action), reasoning_tokens=self.reasoning_tokens,
                              input_scale=self.input_scale)

    def input_upper_bound(self, agent: Agent, run: Run) -> int:
        """The scripted step declares its exact input (as the calibration oracle does). Other steps declare what the
        wrapped policy declares, or nothing: the runtime then reserves its own bound, exactly as without the wrapper.

        One exception, in `central` only: the root's first live step. The runtime bounds a later step from the previous
        step's reported usage, and here that usage is the scripted step's simulated count, which does not measure how
        the real API tokenizes the re-read SPAWN. So this step declares the runtime's own from-scratch rule over its
        whole input (1 token per 2 characters plus the request overhead), as for any agent's first step. The runtime
        reserves the larger of this and its own bound, so the reserve can only grow."""
        scripted = self._scripted(agent, run)
        if scripted is not None:
            return scripted.input_upper_bound(agent, run)
        declared = getattr(self.inner, "input_upper_bound", None)
        bound = declared(agent, run) if declared is not None else 0
        if run.cfg.mode == "central" and agent.parent is None and agent.steps == 1 and run.cfg.task.id in self.actions:
            chars = len(agent.system) + sum(len(visible_text(m["content"])) for m in agent.transcript)
            bound = max(bound, math.ceil(chars / 2) + REQUEST_OVERHEAD_TOKENS)
        return bound

    def decide(self, agent: Agent, allowed: list[str], max_tokens: int, run: Run) -> Decision:
        scripted = self._scripted(agent, run)
        if scripted is None:
            return self.inner.decide(agent, allowed, max_tokens, run)
        d = scripted.decide(agent, allowed, max_tokens, run)
        run.log.emit("SCRIPTED_ACTION", sec(agent.clock), agent=agent.id, parent=agent.parent, step=agent.steps + 1,
                     action=d.action, in_tokens=d.in_tokens, out_tokens=d.out_tokens, input_scale=self.input_scale,
                     reasoning_tokens=self.reasoning_tokens, error=d.error)
        return d
