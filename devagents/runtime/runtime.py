"""Deterministic discrete-event runtime for one run (SPEC §3, §5, §6).

The runtime owns time, money, lineage and the rules of each mode. A policy only chooses the next
action for one agent. Every state change is written to the event log.

Time is integer microseconds. Events are processed in order of
(time, class, agent creation index, sequence number). The classes, in order, are:
COMPLETE < EXPIRE < DELIVER < WAKE < START.

- START: the agent observes messages delivered so far and decides (one policy call). All charges
  (the LLM step plus the action's fees) are posted now, all-or-nothing, and COMPLETE is scheduled
  at start + latency.
- COMPLETE: the action's effects apply (context update, child creation and allocation, message
  enqueue, answer, termination), but only if the actor is still live. A terminated actor's
  in-flight action keeps its charges and has no effects.
- EXPIRE: the agent reached its deadline. For the root, that is the run deadline and the run fails.
- DELIVER: a message or notice arrives. It may wake a waiting agent.
- WAKE: a WAIT timed out.
"""

from __future__ import annotations

import hashlib
import heapq
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from devagents.agents import prompts
from devagents.environment.sources import SQL_SOURCE, InformationEnvironment, QueryResult
from devagents.environment.tasks import Regime, Task
from devagents.runtime.events import EventLog
from devagents.runtime.resources import (
    COMPUTE_OPTIONS, DEFAULT_COMPUTE, ComputeOption, CoordinationCosts, Ledger, estimate_tokens, to_usd, usd,
)

MODES = ("single", "central", "router", "developmental")
ROOT = "A0"
US = 1_000_000  # microseconds per second
REQUEST_OVERHEAD_TOKENS = 1000  # input-bound allowance for request framing and the injected output schema (SPEC §3.3)

COMPLETE, EXPIRE, DELIVER, WAKE, START = range(5)
ALL_ACTIONS = ["WORK", "QUERY", "SPAWN", "MESSAGE", "WAIT", "TERMINATE"]
NO_SPAWN = ["WORK", "QUERY", "MESSAGE", "WAIT", "TERMINATE"]


def policy_config(policy) -> dict:
    """Everything about the policy that changes what the model sees or may output (logged, checked for parity)."""
    compute = getattr(policy, "compute", None)
    return {"class": type(policy).__name__, "structured": getattr(policy, "structured", None),
            "model": getattr(compute, "model", None), "effort": getattr(compute, "effort", None)}


def us(seconds: float) -> int:
    """Seconds -> integer microseconds, rounded up (latencies are never shortened)."""
    return math.ceil(round(seconds * US, 3))


def sec(t_us: int) -> float:
    return t_us / US


class ReserveViolation(RuntimeError):
    """A realized LLM cost exceeded the pre-step reserve. This is an infrastructure error; it is
    never absorbed as a free call."""


@dataclass(frozen=True)
class RunConfig:
    task: Task
    regime: Regime
    mode: str
    compute: ComputeOption = COMPUTE_OPTIONS[DEFAULT_COMPUTE]
    coord: CoordinationCosts = field(default_factory=CoordinationCosts)
    max_steps: int = 20  # per agent
    max_agents: int = 16  # per run, root included
    max_requests_per_query: int = 10
    central_budget_share: float = 0.5
    central_lifetime_share: float = 0.6
    repeat: int = 0
    frozen_sha: str = ""  # SHA-256 of data/frozen.json when running the frozen main suite
    fixed_rule_spawns: bool = False  # apply the central allocation rule in any mode (used by the calibration oracle)

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"unknown mode {self.mode!r}")

    @property
    def max_children(self) -> int:
        """K: the one division cap shared by every mode and by the calibration oracle."""
        return self.compute.max_concurrency - 1

    @property
    def run_id(self) -> str:
        return f"{self.task.id}-{self.regime.name}-{self.mode}-r{self.repeat}"

    def resource_audit(self, info: InformationEnvironment) -> dict:
        """Everything that must be identical across modes for one (task, regime, repeat) (SPEC §6)."""
        return {
            "task_id": self.task.id, "question": self.task.question, "regime": asdict(self.regime),
            "compute": asdict(self.compute), "coord": asdict(self.coord), "source_costs": asdict(info.costs),
            "sources": sorted(info.source_ids), "catalog_sha": hashlib.sha256(info.catalog().encode()).hexdigest(),
            "max_steps": self.max_steps, "max_agents": self.max_agents, "max_children": self.max_children,
            "max_requests_per_query": self.max_requests_per_query, "repeat": self.repeat,
            "central_budget_share": self.central_budget_share, "central_lifetime_share": self.central_lifetime_share,
            "frozen_sha": self.frozen_sha,
        }


@dataclass
class Message:
    sender: str
    recipient: str
    content: str
    kind: str  # "message" | "report" | "notice"
    deliver_at: int
    subject: str | None = None  # for notices: the child the notice is about
    delivered: bool = False
    seen: bool = False


@dataclass
class Agent:
    id: str
    parent: str | None
    depth: int
    objective: str
    deadline: int  # µs
    clock: int  # µs
    index: int
    permissions: frozenset
    system: str = ""
    brief: str = ""
    transcript: list = field(default_factory=list)
    status: str = "ready"  # ready | busy | waiting | terminated
    wait_for: str | None = None
    wait_token: int = 0
    steps: int = 0
    valid_actions: int = 0
    children: list = field(default_factory=list)
    pending: list = field(default_factory=list)  # observation lines for the next step
    last_cost: int = 0
    last_latency: int = 0
    reason: str = ""
    refunded: int = 0
    prev_in_tokens: int = 0
    prev_out_tokens: int = 0
    new_chars: int = 0  # characters appended to the transcript since the last LLM call
    inflight: dict | None = None


@dataclass
class Decision:
    action: dict | None
    in_tokens: int
    out_tokens: int
    assistant_content: Any
    error: str = ""
    truncated: bool = False
    wall_s: float = 0.0
    est_in_tokens: int = 0  # estimator count of the same input (pilot measures r = in_tokens / est_in_tokens)
    est_visible_out_tokens: int = 0  # estimator count of the visible reply (reasoning = out - visible)


class Policy(Protocol):
    """Chooses the next action for one agent. A policy may also define `input_upper_bound(agent, run) -> int`, a
    bound on the input tokens its next `decide` will report. The runtime reserves the larger of that and its own
    bound, so a policy can raise the step reserve but never lower it."""

    def decide(self, agent: Agent, allowed: list[str], max_tokens: int, run: "Run") -> Decision: ...


class Run:
    def __init__(self, config: RunConfig, policy: Policy, info: InformationEnvironment, log: EventLog | None = None):
        self.cfg = config
        self.policy = policy
        self.info = info
        self.log = log or EventLog(config.run_id)
        self.agents: dict[str, Agent] = {}
        self.messages: list[Message] = []
        self.ledger = Ledger(usd(config.regime.budget_usd), ROOT)
        self.catalog = info.catalog()
        self.end_time: int | None = None
        self.answer: str | None = None
        self.outcome: str | None = None
        self._queue: list = []
        self._seq = 0

    # ------------------------------------------------------------------ event queue

    def _push(self, t: int, cls: int, agent: Agent, kind: str, payload: Any = None) -> None:
        self._seq += 1
        heapq.heappush(self._queue, (t, cls, agent.index, self._seq, kind, agent.id, payload))

    def execute(self) -> dict:
        cfg = self.cfg
        self.log.emit("RUN_STARTED", 0.0, task_id=cfg.task.id, task_class=cfg.task.task_class, regime=cfg.regime.name,
                      mode=cfg.mode, repeat=cfg.repeat, budget=self.ledger.budget, deadline_s=cfg.regime.deadline_s,
                      value_of_time=cfg.regime.value_of_time, compute=asdict(cfg.compute),
                      audit=cfg.resource_audit(self.info), prompt_sha=self.prompt_fingerprint(),
                      policy=policy_config(self.policy))
        root = self._create_agent(None, objective=cfg.task.question, context="", deadline=us(cfg.regime.deadline_s),
                                  t=0, allocation=0)
        while self._queue and self.end_time is None:
            t, cls, _, _, kind, aid, payload = heapq.heappop(self._queue)
            a = self.agents[aid]
            if kind == "deliver":
                self._on_deliver(payload, t)
            elif a.status == "terminated":
                continue  # stale event: nothing happens after termination
            elif kind == "start":
                self._on_start(a, t)
            elif kind == "complete":
                self._on_complete(a, t, payload)
            elif kind == "expire":
                self._on_expire(a, t)
            elif kind == "wake":
                if a.status == "waiting" and payload == a.wait_token:
                    a.pending.append(f"Your WAIT timed out at t={sec(t):.1f}s.")
                    self._make_ready(a, t)
            self.ledger.check()
        if self.end_time is None:  # queue drained without a root outcome (cannot normally happen)
            self._end_run(root, "no_answer", root.deadline)
        return self._finalize()

    # ------------------------------------------------------------------ mode rules

    def allowed_actions(self, a: Agent) -> list[str]:
        mode = self.cfg.mode
        if mode == "developmental":
            return list(ALL_ACTIONS)
        if mode == "single":
            return ["WORK", "QUERY", "TERMINATE"]
        if a.parent is not None:
            return list(NO_SPAWN)  # created agents never spawn in central/router
        if mode == "central":
            return ["SPAWN"] if a.valid_actions == 0 else list(NO_SPAWN)
        return list(ALL_ACTIONS) if a.valid_actions == 0 else list(NO_SPAWN)  # router: SPAWN only as first action

    def _mode_rules(self, is_root: bool) -> str:
        mode, cfg = self.cfg.mode, self.cfg
        key = mode if mode in ("single", "developmental") else f"{mode}_{'root' if is_root else 'child'}"
        return prompts.MODE_RULES[key].format(k=cfg.max_children, share=cfg.central_budget_share,
                                              life=cfg.central_lifetime_share)

    def system_prompt_for(self, is_root: bool) -> str:
        r = self.cfg.regime
        return prompts.system_prompt(mode_rules=self._mode_rules(is_root), catalog=self.catalog, compute=self.cfg.compute,
                                     coord=self.cfg.coord, task_value=r.task_value, value_of_time=r.value_of_time,
                                     failure_penalty=r.failure_penalty, max_children=self.cfg.max_children,
                                     overhead_tokens=REQUEST_OVERHEAD_TOKENS)

    def prompt_fingerprint(self) -> str:
        """Hash of the mode-independent prompt text (everything except the MODE RULES line)."""
        text = self.system_prompt_for(True).replace(self._mode_rules(True), "<MODE RULES>")
        return hashlib.sha256(text.encode()).hexdigest()

    # ------------------------------------------------------------------ START

    def _on_start(self, a: Agent, t: int) -> None:
        cfg, compute = self.cfg, self.cfg.compute
        if a.status != "ready":
            return
        a.clock = t
        if a.steps >= cfg.max_steps:  # the cap holds whatever the previous action was (WAIT, SPAWN+wait, ...)
            self._stop(a, "max_steps", t)
            return
        self._observe(a)
        in_upper = self._input_upper_bound(a)
        if in_upper > compute.context_capacity:
            self._stop(a, "context_exhausted", t)
            return
        free = self.ledger.balance[a.id] - self._reserve_base(in_upper)
        max_tokens = int(min(compute.max_output_tokens, max(0, free) // (compute.price_out + cfg.coord.message_per_token)))
        if max_tokens < compute.min_step_tokens:
            if self._live_children(a):  # allocated money will come back; suspend instead of dying
                a.pending.append("Suspended: your balance cannot cover a step until money is returned to you.")
                self._enter_wait(a, "any", a.deadline, t)
            else:
                self._stop(a, "budget_exhausted", t)
            return

        allowed = self.allowed_actions(a)
        d = self.policy.decide(a, allowed, max_tokens, self)
        cost = compute.step_cost(d.in_tokens, d.out_tokens)
        if d.in_tokens > in_upper or d.out_tokens > max_tokens or cost > self.ledger.balance[a.id]:
            raise ReserveViolation(f"{a.id}: realized step (in={d.in_tokens}, out={d.out_tokens}) exceeds the reserve "
                                   f"(in<={in_upper}, out<={max_tokens})")
        spent0 = self.ledger.spent[a.id]
        self.ledger.charge(a.id, cost)
        llm_latency = us(compute.step_latency(d.in_tokens, d.out_tokens))
        self.log.emit("RESOURCE_CONSUMED", sec(t), agent=a.id, parent=a.parent, kind="llm", amount=cost,
                      in_tokens=d.in_tokens, out_tokens=d.out_tokens, compute=compute.id, latency_s=sec(llm_latency),
                      wall_s=d.wall_s, est_in_tokens=d.est_in_tokens, est_visible_out_tokens=d.est_visible_out_tokens)
        a.prev_in_tokens, a.prev_out_tokens, a.new_chars = d.in_tokens, d.out_tokens, 0
        a.transcript.append({"role": "assistant", "content": d.assistant_content})
        a.steps += 1

        action = d.action if isinstance(d.action, dict) else None
        name = action.get("action") if action else None
        budget_capped = d.truncated and max_tokens < compute.max_output_tokens
        error = d.error or self._validate(a, action, allowed)
        plan: dict = {"action": name or "INVALID", "t0": t}
        if budget_capped:
            plan.update(kind="budget_exhausted", error="output truncated at the budget-capped max_tokens")
            latency = 0
        elif error:
            plan.update(kind="invalid", error=error)
            latency = 0
        else:
            error, latency = self._prepare(a, action, plan, t, t + llm_latency)
            if error:
                plan.update(kind="invalid", error=error)
                latency = 0
            else:
                a.valid_actions += 1
        self.log.emit("ACTION_STARTED", sec(t), agent=a.id, parent=a.parent, step=a.steps, action=plan["action"],
                      detail=action, llm_latency_s=sec(llm_latency), action_latency_s=sec(latency))
        a.last_cost = self.ledger.spent[a.id] - spent0
        a.status, a.inflight = "busy", plan
        self._push(t + llm_latency + latency, COMPLETE, a, "complete", plan)

    def _observe(self, a: Agent) -> None:
        """Append the next user turn: the brief (first step) or the last result, then the status and new messages."""
        new = [m for m in self.messages if m.recipient == a.id and m.delivered and not m.seen]
        for m in new:
            m.seen = True
        kids = []
        in_flight = {x for m in self._undelivered_to(a) for x in (m.sender, m.subject)}
        for cid in a.children:
            c = self.agents[cid]
            if c.status == "terminated" and cid not in in_flight:
                kids.append(f"{cid} terminated ({c.reason}, returned ${to_usd(c.refunded):.4f})")
            else:  # termination becomes observable only when its report or notice is delivered
                kids.append(f"{cid} live")
        head = a.brief if a.steps == 0 else ("\n".join(a.pending) if a.pending else "(no result)")
        msgs = [f"[t={sec(m.deliver_at):.1f}s] from {m.sender} ({m.kind}): {m.content}" for m in new]
        a.new_chars += len(head) + sum(len(x) for x in msgs) + 400  # the status block itself is ~400 characters
        status = prompts.status_block(
            t=sec(a.clock), deadline=sec(a.deadline), balance=self.ledger.balance[a.id], steps=a.steps,
            max_steps=self.cfg.max_steps, last_cost=a.last_cost, last_latency=sec(a.last_latency), children=kids,
            messages=msgs, min_step=self.min_step_balance(a))
        a.new_chars -= len(head) + sum(len(x) for x in msgs) + 400
        text = f"{head}\n\n{status}"
        a.pending = []
        a.transcript.append({"role": "user", "content": text})
        a.new_chars += len(text)

    def _reserve_base(self, in_upper: int) -> int:
        """The part of the step reserve that does not depend on max_tokens: input upper bound and one message fee."""
        return in_upper * self.cfg.compute.price_in + self.cfg.coord.message_fee

    def min_step_balance(self, a: Agent) -> int:
        """Smallest balance that lets `a` take its next step (shown to the agent in every status block)."""
        c = self.cfg
        return self._reserve_base(self._input_upper_bound(a)) + c.compute.min_step_tokens * (
            c.compute.price_out + c.coord.message_per_token)

    def _input_upper_bound(self, a: Agent) -> int:
        """Upper bound on this step's input tokens: the exact previous usage, plus at most 1 token per 2 new
        characters, plus the fixed request overhead (for example an injected output schema). A policy whose token
        model can exceed this (a scripted policy with input_scale > 2) declares its own bound, and the larger one
        is used. The step reserve therefore always covers the realized cost."""
        overhead = REQUEST_OVERHEAD_TOKENS
        if a.prev_in_tokens:
            bound = a.prev_in_tokens + a.prev_out_tokens + math.ceil(a.new_chars / 2) + overhead
        else:
            bound = math.ceil((len(a.system) + a.new_chars) / 2) + overhead
        declared = getattr(self.policy, "input_upper_bound", None)
        return bound if declared is None else max(bound, declared(a, self))

    # ------------------------------------------------------------------ validation

    def _validate(self, a: Agent, action: dict | None, allowed: list[str]) -> str:
        if action is None:
            return "the reply must be one JSON object"
        name = action.get("action")
        if name not in allowed:
            return f"action {name!r} is not available now (available: {', '.join(allowed)})"
        if name == "QUERY":
            reqs = action.get("requests")
            if not isinstance(reqs, list) or not reqs:
                return "QUERY needs a non-empty 'requests' list"
            if len(reqs) > self.cfg.max_requests_per_query:
                return f"at most {self.cfg.max_requests_per_query} requests per QUERY"
            for r in reqs:
                if not isinstance(r, dict) or r.get("kind") not in ("sql", "doc") or not isinstance(r.get("target"), str):
                    return "each request needs 'kind' ('sql' or 'doc') and a string 'target'"
                source = SQL_SOURCE if r["kind"] == "sql" else r["target"]
                if source not in a.permissions:
                    return f"unknown source or no permission: {r['target']!r}"
        elif name == "SPAWN":
            kids = action.get("children")
            k = self.cfg.max_children
            if not isinstance(kids, list) or not 1 <= len(kids) <= k:
                return f"SPAWN needs a 'children' list with 1 to {k} entries"
            for c in kids:
                if not isinstance(c, dict) or not isinstance(c.get("objective"), str) or not c["objective"].strip():
                    return "each child needs a non-empty string 'objective'"
                if not isinstance(c.get("context", ""), str):
                    return "'context' must be a string"
                if self.cfg.mode != "central":
                    if not _is_number(c.get("budget_usd")) or c["budget_usd"] < 0:
                        return "each child needs a non-negative number 'budget_usd'"
                    if not _is_number(c.get("lifetime_s")) or c["lifetime_s"] <= 0:
                        return "each child needs a positive number 'lifetime_s'"
            if "wait_for_children" in action and not isinstance(action["wait_for_children"], bool):
                return "wait_for_children must be true or false"
        elif name == "MESSAGE":
            to = action.get("to")
            if not isinstance(to, str) or not isinstance(action.get("content"), str):
                return "MESSAGE needs string 'to' and 'content'"
            if to not in ([a.parent] if a.parent else []) + a.children:
                return f"{to!r} is not your parent or one of your children"
            if self.agents[to].status == "terminated":
                return f"{to} has terminated"
        elif name == "WAIT":
            wait_for = action.get("wait_for", "any")
            if wait_for not in ("any", "all"):
                return "wait_for must be 'any' or 'all'"
            if action.get("max_wait_s") is not None and not _is_number(action["max_wait_s"]):
                return "max_wait_s must be a number"
            parent_live = a.parent is not None and self.agents[a.parent].status != "terminated"
            if wait_for == "any" and not (self._live_children(a) or parent_live or self._undelivered_to(a)):
                return "nobody can send you a message"
        elif name == "TERMINATE":
            if not isinstance(action.get("answer", ""), str):
                return "answer must be a string"
        return ""

    # ------------------------------------------------------------------ charges at START

    def _prepare(self, a: Agent, action: dict, plan: dict, t: int, t_decided: int) -> tuple[str, int]:
        """Check affordability and caps, post the action's charges (all-or-nothing, stamped at START time t), and
        return the action's latency. t_decided (START + decision latency) anchors the central lifetime rule."""
        name, coord = action["action"], self.cfg.coord
        plan["kind"] = name
        if name == "QUERY":
            results: list[QueryResult] = [self.info.query(r["kind"], r["target"]) for r in action["requests"]]
            fee = sum(r.fee for r in results)
            if fee > self.ledger.balance[a.id]:
                return f"insufficient balance for this QUERY (needs ${to_usd(fee):.4f})", 0
            for r in results:
                if r.fee:
                    self.ledger.charge(a.id, r.fee)
                    self.log.emit("RESOURCE_CONSUMED", sec(t), agent=a.id, parent=a.parent, kind="query",
                                  amount=r.fee, source=r.source)
            plan["results"] = results
            return "", sum(us(r.latency_s) for r in results)
        if name == "SPAWN":
            kids = action["children"]
            live = sum(1 for x in self.agents.values() if x.status != "terminated")
            pending = sum(len(x.inflight.get("specs", ())) for x in self.agents.values() if x.inflight)
            if live + pending + len(kids) > self.cfg.compute.max_concurrency:
                return f"concurrency cap: at most {self.cfg.compute.max_concurrency} live agents", 0
            if len(self.agents) + pending + len(kids) > self.cfg.max_agents:
                return f"run cap: at most {self.cfg.max_agents} agents per run", 0
            specs = []
            for c in kids:
                objective, context = c["objective"].strip(), c.get("context", "")
                tokens = estimate_tokens(objective) + estimate_tokens(context)
                specs.append({"objective": objective, "context": context, "tokens": tokens,
                              "fee": coord.spawn_fee + coord.transfer_per_token * tokens})
            fees = sum(s["fee"] for s in specs)
            if self.cfg.mode == "central" or self.cfg.fixed_rule_spawns:  # fixed rule (SPEC §6, §7.1)
                share, life = fixed_allocation(self.ledger.balance[a.id], fees, len(specs), a.deadline - t_decided,
                                               self.cfg.central_budget_share, self.cfg.central_lifetime_share)
                for s in specs:
                    s["allocation"], s["lifetime"] = share, life
            else:
                for s, c in zip(specs, kids):
                    s["allocation"], s["lifetime"] = usd(float(c["budget_usd"])), us(float(c["lifetime_s"]))
            need = fees + sum(s["allocation"] for s in specs)
            if need > self.ledger.balance[a.id]:
                return f"insufficient balance for this SPAWN (needs ${to_usd(need):.4f})", 0
            for s in specs:
                self.ledger.charge(a.id, s["fee"])
                self.log.emit("RESOURCE_CONSUMED", sec(t), agent=a.id, parent=a.parent, kind="spawn",
                              amount=s["fee"])
            plan["specs"] = specs
            plan["wait"] = self.cfg.mode == "central" or bool(action.get("wait_for_children", False))
            return "", us(coord.spawn_latency_s)
        if name in ("MESSAGE", "TERMINATE"):
            if name == "TERMINATE":
                plan["answer"] = action.get("answer", "").strip()
                if a.parent is None:
                    return "", 0
                content, to, kind = plan["answer"] or "(empty report)", a.parent, "report"
            else:
                content, to, kind = action["content"], action["to"], "message"
            tokens = estimate_tokens(content)
            fee = coord.message_fee + coord.message_per_token * tokens
            if fee > self.ledger.balance[a.id]:  # cannot happen: the step reserve covers any message
                return "insufficient balance to send", 0
            self.ledger.charge(a.id, fee)
            self.log.emit("RESOURCE_CONSUMED", sec(t), agent=a.id, parent=a.parent, kind="message", amount=fee)
            plan["message"] = {"to": to, "content": content, "kind": kind, "tokens": tokens, "fee": fee}
            return "", 0
        if name == "WAIT":
            plan["wait_for"] = action.get("wait_for", "any")
            plan["max_wait"] = action.get("max_wait_s")
        return "", 0

    # ------------------------------------------------------------------ COMPLETE

    def _on_complete(self, a: Agent, t: int, plan: dict) -> None:
        a.inflight = None
        a.clock = t
        a.last_latency = t - plan["t0"]
        kind, ok, error = plan["kind"], True, plan.get("error", "")
        if kind == "budget_exhausted":
            self._emit_completed(a, plan, t, False, error)
            self._stop(a, "budget_exhausted", t)
            return
        if kind == "invalid":
            a.pending.append(f"Error: {error}. Nothing was done.")
            ok = False
        elif kind == "WORK":
            a.pending.append("Noted.")
        elif kind == "QUERY":
            parts = []
            for r in plan["results"]:
                self.log.emit("INFORMATION_QUERIED", sec(t), agent=a.id, parent=a.parent, source=r.source, kind=r.kind,
                              ok=r.ok, tokens=r.tokens, rows=r.rows, fee=r.fee, latency_s=r.latency_s, error=r.error)
                label = "sql" if r.source == SQL_SOURCE else f"doc {r.source}"
                meta = f"{r.tokens} tokens, {r.latency_s:.1f}s, fee ${to_usd(r.fee):.4f}"
                parts.append(f"[{label}] ({meta})\n{r.text}" if r.ok else f"[{label}] ERROR: {r.error} ({meta})")
            a.pending.append("\n\n".join(parts))
        elif kind == "SPAWN":
            created = [self._create_agent(a, objective=s["objective"], context=s["context"],
                                          deadline=min(a.deadline, t + s["lifetime"]), t=t, allocation=s["allocation"],
                                          fee=s["fee"]).id for s in plan["specs"]]
            a.pending.append(f"Created {', '.join(created)}.")
        elif kind in ("MESSAGE", "TERMINATE") and "message" in plan:
            m = plan["message"]
            delivered = self.agents[m["to"]].status != "terminated"
            if delivered:
                msg = Message(a.id, m["to"], m["content"], m["kind"], t + us(self.cfg.coord.message_latency_s))
                self.messages.append(msg)
                self._push(msg.deliver_at, DELIVER, self.agents[m["to"]], "deliver", msg)
                self.log.emit("MESSAGE_SENT", sec(t), agent=a.id, parent=a.parent, to=m["to"], kind=m["kind"],
                              tokens=m["tokens"], fee=m["fee"], deliver_at=sec(msg.deliver_at), content=m["content"])
            if kind == "MESSAGE":
                if delivered:
                    a.pending.append(f"Message sent to {m['to']}.")
                else:  # the recipient terminated while the MESSAGE was in flight; the fee stands (SPEC §3.2)
                    error = f"not delivered: {m['to']} terminated before the message was sent (fee kept)"
                    a.pending.append(f"Message to {m['to']} {error}.")
        self._emit_completed(a, plan, t, ok, error)

        if kind == "TERMINATE":
            if a.parent is None:
                self.answer = plan["answer"]
                self._end_run(a, "answered" if plan["answer"] else "no_answer", t)
            else:
                self._terminate(a, "completed", t)
            return
        if kind == "SPAWN" and plan["wait"]:
            self._enter_wait(a, "all", a.deadline, t)
        elif kind == "WAIT":
            mw = plan["max_wait"]
            until = a.deadline if mw is None else min(a.deadline, t + us(max(0.0, float(mw))))
            self._enter_wait(a, plan["wait_for"], until, t)
        else:
            self._make_ready(a, t)
        if a.status == "ready" and a.steps >= self.cfg.max_steps:
            self._stop(a, "max_steps", t)

    def _emit_completed(self, a: Agent, plan: dict, t: int, ok: bool, error: str) -> None:
        self.log.emit("ACTION_COMPLETED", sec(t), agent=a.id, parent=a.parent, step=a.steps, action=plan["action"],
                      ok=ok, error=error, duration_s=sec(t - plan["t0"]), discarded=False)

    # ------------------------------------------------------------------ waiting and delivery

    def _live_children(self, a: Agent) -> list[str]:
        return [c for c in a.children if self.agents[c].status != "terminated"]

    def _undelivered_to(self, a: Agent, senders: list[str] | None = None) -> list[Message]:
        return [m for m in self.messages if m.recipient == a.id and not m.delivered
                and (senders is None or m.sender in senders or m.subject in senders)]

    def _wait_satisfied(self, a: Agent) -> bool:
        if a.wait_for == "all":
            return not self._live_children(a) and not self._undelivered_to(a, a.children)
        return any(m.recipient == a.id and m.delivered and not m.seen for m in self.messages)

    def _enter_wait(self, a: Agent, wait_for: str, until: int, t: int) -> None:
        a.status, a.wait_for = "waiting", wait_for
        a.wait_token += 1
        a.pending.append(f"Waiting ({wait_for}) from t={sec(t):.1f}s.")
        if self._wait_satisfied(a):
            self._make_ready(a, t)
        else:
            self._push(until, WAKE, a, "wake", a.wait_token)

    def _make_ready(self, a: Agent, t: int) -> None:
        a.status, a.wait_for = "ready", None
        a.clock = max(a.clock, t)
        self._push(a.clock, START, a, "start")

    def _on_deliver(self, m: Message, t: int) -> None:
        m.delivered = True
        a = self.agents[m.recipient]
        if a.status == "waiting" and self._wait_satisfied(a):
            self._make_ready(a, t)

    def _notify(self, parent: Agent, child: str, text: str, t: int) -> None:
        """Free, content-free lifecycle notice to a live parent about `child`, delivered like a message."""
        msg = Message("runtime", parent.id, text, "notice", t + us(self.cfg.coord.message_latency_s), subject=child)
        self.messages.append(msg)
        self._push(msg.deliver_at, DELIVER, parent, "deliver", msg)

    # ------------------------------------------------------------------ lifecycle

    def _create_agent(self, parent: Agent | None, *, objective: str, context: str, deadline: int, t: int,
                      allocation: int, fee: int = 0) -> Agent:
        if parent is None:
            aid, depth, perms = ROOT, 0, self.info.source_ids
        else:
            aid = f"{parent.id}.{len(parent.children) + 1}"
            depth, perms = parent.depth + 1, parent.permissions  # inherited, never widened
            self.ledger.open(aid)
        a = Agent(id=aid, parent=parent.id if parent else None, depth=depth, objective=objective, deadline=deadline,
                  clock=t, index=len(self.agents), permissions=frozenset(perms))
        self.agents[aid] = a
        if parent is not None:
            parent.children.append(aid)
            self.log.emit("AGENT_SPAWNED", sec(t), agent=parent.id, parent=parent.parent, child=aid, allocation=allocation,
                          fee=fee, context_tokens=estimate_tokens(objective) + estimate_tokens(context),
                          objective=objective)
        self.log.emit("AGENT_CREATED", sec(t), agent=aid, parent=a.parent, depth=depth, objective=objective,
                      deadline=sec(deadline), permissions=sorted(perms))
        if parent is not None and allocation:
            self.ledger.transfer(parent.id, aid, allocation)
            self.log.emit("RESOURCE_ALLOCATED", sec(t), agent=aid, parent=parent.id, source=parent.id, target=aid,
                          amount=allocation, kind="allocation")
        a.system = self.system_prompt_for(parent is None)
        r = self.cfg.regime
        if parent is None:
            a.brief = prompts.root_brief(task_id=self.cfg.task.id, question=self.cfg.task.question, agent_id=aid,
                                         balance=self.ledger.balance[aid], deadline=sec(deadline),
                                         value_of_time=r.value_of_time)
        else:
            a.brief = prompts.child_brief(agent_id=aid, parent=parent.id, t=sec(t), objective=objective, context=context,
                                          balance=allocation, deadline=sec(deadline), value_of_time=r.value_of_time)
        a.new_chars = 0
        self._push(t, START, a, "start")
        self._push(deadline, EXPIRE, a, "expire")
        return a

    def _terminate(self, a: Agent, reason: str, t: int) -> None:
        """Terminate `a` after its live descendants (post-order, creation order). Each refund goes to the parent,
        which is still live at that moment."""
        for cid in a.children:
            if self.agents[cid].status != "terminated":
                self._terminate(self.agents[cid], "ancestor_terminated", t)
        if a.inflight is not None:  # charges stand, effects are discarded
            self.log.emit("ACTION_COMPLETED", sec(t), agent=a.id, parent=a.parent, step=a.steps,
                          action=a.inflight["action"], ok=False, error="actor terminated before completion",
                          duration_s=sec(t - a.inflight["t0"]), discarded=True)
            a.inflight = None
        a.status, a.reason = "terminated", reason
        returned = 0
        if a.parent is not None:
            returned = self.ledger.balance[a.id]
            if returned:
                self.ledger.transfer(a.id, a.parent, returned)
                self.log.emit("RESOURCE_ALLOCATED", sec(t), agent=a.id, parent=a.parent, source=a.id, target=a.parent,
                              amount=returned, kind="return")
        a.refunded = returned
        self.log.emit("AGENT_TERMINATED", sec(t), agent=a.id, parent=a.parent, reason=reason, returned=returned,
                      returned_to=a.parent if returned else None, steps=a.steps)

    def _stop(self, a: Agent, reason: str, t: int) -> None:
        """Involuntary termination (budget, step cap, context). For the root this ends the run as a failure."""
        if a.parent is None:
            self._end_run(a, reason, t)
            return
        parent = self.agents[a.parent]
        self._terminate(a, reason, t)
        self._notify(parent, a.id, f"{a.id} terminated ({reason}) without a report.", t)

    def _on_expire(self, a: Agent, t: int) -> None:
        if a.parent is None:
            self._end_run(a, "deadline", t)
            return
        parent = self.agents[a.parent]
        self._terminate(a, "lifetime_expired", t)
        self._notify(parent, a.id, f"{a.id} terminated (lifetime_expired) without a report.", t)

    def _end_run(self, root: Agent, outcome: str, t: int) -> None:
        self.outcome, self.end_time = outcome, t
        self._terminate(root, outcome, t)

    def _finalize(self) -> dict:
        self.ledger.check()
        for a in self.agents.values():
            assert a.status == "terminated"
            assert a.parent is None or self.ledger.balance[a.id] == 0, f"{a.id} holds money after termination"
        from devagents.evals.metrics import grade  # evals depends on runtime, not vice versa
        answered = self.outcome == "answered"
        quality = grade(self.cfg.task, self.answer) if answered else 0.0
        elapsed = sec(self.end_time) if answered else self.cfg.regime.deadline_s
        self.log.emit("RUN_COMPLETED", sec(self.end_time), answer=self.answer, outcome=self.outcome, quality=quality,
                      elapsed_s=elapsed, total_spent=self.ledger.total_spent, agents=len(self.agents))
        return {"run_id": self.cfg.run_id, "outcome": self.outcome, "answer": self.answer, "quality": quality,
                "elapsed_s": elapsed, "spent_usd": to_usd(self.ledger.total_spent), "agents": len(self.agents)}


def fixed_allocation(balance: int, fees: int, k: int, remaining: int, budget_share: float,
                     lifetime_share: float) -> tuple[int, int]:
    """The central rule, which the calibration oracle also uses: an equal share of `budget_share` of the
    balance left after fees (floor division, remainder stays), and a lifetime of `lifetime_share` of the remaining time."""
    return int(budget_share * max(0, balance - fees)) // k, us(lifetime_share * sec(remaining))


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
