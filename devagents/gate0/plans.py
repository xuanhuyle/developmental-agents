"""Gate-0 organizations (GATE_0_SPEC.md §3): generic plan types, instantiated per member and run as scripted policies.

Every plan runs through the unchanged runtime in `developmental` mode with the calibration oracle's conventions: the
runtime applies the fixed allocation rule (`fixed_rule_spawns`), every step is priced like an oracle step (estimator
tokens × r input, JSON action + reasoning tokens output), and reasoning is perfect (the final answer is the member's
ground truth, *provided* the root actually received every needed fact before answering; that is checked from the log).

Plan names are `<prefix>[k]>` + `<continuation>`:

- `blind`: the root reads the triage source and every candidate unit, then answers (no use of information).
- `triage>solo`, `triage>fan<k>`, `triage>self+<k>`: the root reads the triage source, then reads the needed documents
  itself, or spawns k children over them and waits for all of them, or spawns k children and reads one share itself.
  Shares are size-balanced (largest-first on the catalog's token counts).
- `spec<k>>…`: the root spawns k children over *all* candidate units at t0 (size-balanced). In template A a
  child runs the triage query itself and reads only its units that are needed; in template B the root reads the
  triage memo while the children read their units. Continuations (B): `wait` (wait for every child), `dissolve`
  (after the memo, wait only for children holding a needed unit; the others are terminated when the run ends), and
  `cancel` (also MESSAGE each child that holds only dead units "STOP"; a stopped child terminates at its next step).
- `spectop<m>>…`: like `spec`, but only the m largest units get a child each; the root reads the triage source, then
  the remaining needed units itself.

A plan's *structure* is fixed at t0 (`fixed`) unless its continuation is `dissolve`/`cancel`, or unless the plan is a
`triage>…` plan whose continuation is chosen after the reveal (that choice is made by the adaptive oracle, never by a
plan). The adaptive oracle groups plans by their common pre-reveal prefix (`group`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from devagents.agents.policies import ScriptedPolicy
from devagents.config import Constants
from devagents.evals.calibrate import Assumptions
from devagents.evals.metrics import metrics_from_events
from devagents.gate0.worlds import Instance, Member
from devagents.environment.tasks import Regime
from devagents.runtime.resources import estimate_tokens
from devagents.runtime.runtime import Run, RunConfig

MAX_PER_QUERY = 10
STOP = "STOP: your assignment is no longer needed. Terminate now."


@dataclass(frozen=True)
class Plan:
    prefix: str  # "blind" | "triage" | "spec" | "spectop"
    k: int = 0
    cont: str = ""  # "solo" | "fan" | "self" | "wait" | "dissolve" | "cancel"

    @property
    def name(self) -> str:
        if self.prefix == "blind":
            return "blind"
        if self.prefix == "triage":
            return {"solo": "triage>solo", "fan": f"triage>fan{self.k}", "self": f"triage>self+{self.k}"}[self.cont]
        return f"{self.prefix}{self.k}>{self.cont}"

    @property
    def group(self) -> str:
        """Plans with the same group share every action before the reveal (verified from the logs)."""
        return "triage" if self.prefix == "triage" else ("blind" if self.prefix == "blind" else f"{self.prefix}{self.k}")

    @property
    def fixed(self) -> bool:
        """True if the plan's organizational structure is decided at t0 (a one-shot router may choose it)."""
        return self.cont not in ("dissolve", "cancel")

    @property
    def has_children(self) -> bool:
        return self.prefix in ("spec", "spectop") or (self.prefix == "triage" and self.cont in ("fan", "self"))


def parse_plan(name: str) -> Plan:
    if name == "blind":
        return Plan("blind")
    if name == "triage>solo":
        return Plan("triage", 0, "solo")
    head, cont = name.split(">")
    if head == "triage":
        if cont.startswith("self+"):
            return Plan("triage", int(cont[5:]), "self")
        return Plan("triage", int(cont[3:]), "fan")
    for pre in ("spectop", "spec"):
        if head.startswith(pre):
            return Plan(pre, int(head[len(pre):]), cont)
    raise ValueError(f"unknown plan {name!r}")


def library(inst: Instance, member: Member, k_max: int) -> list[Plan]:
    """Every plan defined for this member. `triage>fan<k>` needs k <= #needed documents; the others exist for every
    member of a reveal set."""
    n_units, n_needed = len(inst.units), len(member.needed)
    plans = []
    if inst.triage:
        plans.append(Plan("blind"))
    plans.append(Plan("triage", 0, "solo"))
    plans += [Plan("triage", k, "fan") for k in range(1, min(k_max, n_needed) + 1)]
    plans += [Plan("triage", k, "self") for k in range(1, min(k_max, n_needed - 1) + 1)]
    conts = ("wait",) if (inst.triage_filters_units or not inst.triage) else ("wait", "dissolve", "cancel")
    if inst.triage:  # without a triage source, spec<k> would be triage>fan<k> under another name
        plans += [Plan("spec", k, c) for k in range(1, min(k_max, n_units) + 1) for c in conts]
    plans += [Plan("spectop", m, c) for m in range(1, min(2, n_units - 1) + 1) for c in conts]
    return plans


# --------------------------------------------------------------------------- scripts


def _query(reqs) -> dict:
    return {"rationale": "Read the sources needed.", "action": "QUERY",
            "requests": [{"kind": k, "target": t} for k, t in reqs]}


def _chunks(reqs: list, n: int = MAX_PER_QUERY) -> list[list]:
    return [reqs[i:i + n] for i in range(0, len(reqs), n)]


def balanced(items: list, size, k: int) -> list[tuple]:
    """Deterministic largest-first (LPT) assignment of items to k bins by size; ties by position. Sizes are the catalog's
    token counts, which are identical across the members of a reveal set."""
    bins, load = [[] for _ in range(k)], [0] * k
    for i in sorted(range(len(items)), key=lambda i: (-size(items[i]), i)):
        j = min(range(k), key=lambda b: (load[b], b))
        bins[j].append(i)
        load[j] += size(items[i])
    return [tuple(items[i] for i in sorted(b)) for b in bins]


def _work(i: int) -> dict:
    return {"rationale": "Double-check the facts gathered so far.", "action": "WORK",
            "notes": f"Check {i + 1}: the gathered values are consistent with the question."}


class Program:
    """The scripted organization for one (instance, member, plan): one generator per agent, advanced once per step."""

    def __init__(self, inst: Instance, member: Member, plan: Plan, extra_work: int):
        self.inst, self.member, self.plan, self.extra = inst, member, plan, extra_work
        self.gens: dict = {}
        self.assign: list[tuple[int, ...]] = []  # unit indices per child (spec/spectop)
        self.child_docs: list[list[str]] = []  # documents per child (triage>fan)

    def __call__(self, agent, run, allowed) -> dict:
        g = self.gens.get(agent.id)
        if g is None:
            g = self._root(run) if agent.parent is None else self._child(agent, run)
            self.gens[agent.id] = g
        return next(g)

    # ---- helpers
    @property
    def triage_reqs(self) -> list:
        return list(self.inst.triage)

    def _docs_of(self, units) -> list[str]:
        return [d for u in units for d in self.inst.units[u]]

    def _spawn(self, objectives: list[str], wait: bool) -> dict:
        return {"rationale": "Split the work across agents.", "action": "SPAWN", "wait_for_children": wait,
                "children": [{"objective": o, "context": "", "budget_usd": 0.0, "lifetime_s": 1.0} for o in objectives]}

    def _objective(self, docs: list[str], filtered: bool) -> str:
        q = self.inst.question
        if filtered:
            return (f"Find the facts needed for: {q} Run the triage query yourself, then read only those of these "
                    f"documents that it selects: " + "; ".join(docs))
        return f"Find the facts needed for: {q} Read only the sources named in this objective: " + "; ".join(docs)

    def _answer(self) -> dict:
        return {"rationale": "All needed facts are in hand.", "action": "TERMINATE", "answer": self.member.answer}

    def _reported(self, run, child_id: str) -> bool:
        return any(m.recipient == "A0" and m.sender == child_id and m.kind == "report" and m.delivered
                   for m in run.messages)

    def _top_units(self, m: int) -> list[int]:
        size = {i: sum(self._tokens(d) for d in u) for i, u in enumerate(self.inst.units)}
        return sorted(range(len(self.inst.units)), key=lambda i: (-size[i], i))[:m]

    def _tokens(self, doc: str) -> int:
        return estimate_tokens(self.member.world.docs[doc])  # the count the catalog shows

    # ---- root
    def _root(self, run):
        p, inst, member = self.plan, self.inst, self.member
        if p.prefix == "blind":
            for ch in _chunks(self.triage_reqs + [("doc", d) for d in inst.unit_docs]):
                yield _query(ch)
        elif p.prefix == "triage":
            if self.triage_reqs:
                yield _query(self.triage_reqs)
            if p.cont == "solo":
                for ch in _chunks([("doc", d) for d in member.needed]):
                    yield _query(ch)
            elif p.cont == "fan":
                self.child_docs = [list(b) for b in balanced(list(member.needed), self._tokens, p.k)]
                yield self._spawn([self._objective(ds, False) for ds in self.child_docs], wait=True)
            else:  # "self": k children and the root share the needed documents (k + 1 balanced shares)
                shares = [list(b) for b in balanced(list(member.needed), self._tokens, p.k + 1)]
                own, self.child_docs = shares[0], shares[1:]
                yield self._spawn([self._objective(ds, False) for ds in self.child_docs], wait=False)
                for ch in _chunks([("doc", d) for d in own]):
                    yield _query(ch)
                self.assign = [()] * p.k
                kids = [f"A0.{i + 1}" for i in range(p.k)]
                while not all(self._reported(run, c) for c in kids):
                    yield {"rationale": "Wait for the reports still needed.", "action": "WAIT", "wait_for": "all"}
        else:
            units = list(range(len(inst.units)))
            if p.prefix == "spec":
                usize = lambda u: sum(self._tokens(d) for d in inst.units[u])  # noqa: E731
                self.assign = balanced(units, usize, p.k)
            else:
                self.assign = [(u,) for u in self._top_units(p.k)]
            filtered = inst.triage_filters_units
            objectives = [self._objective(self._docs_of(a), filtered) for a in self.assign]
            if p.prefix == "spec" and (filtered or not inst.triage):
                # Template A: every child triages for itself, so the root has nothing to do but wait (the
                # calibration's atstart-k).
                yield self._spawn(objectives, wait=True)
            else:
                yield self._spawn(objectives, wait=False)
                if self.triage_reqs:
                    yield _query(self.triage_reqs)  # the reveal
                if p.prefix == "spectop":  # the root reads the needed units it did not hand out
                    assigned = {u for a in self.assign for u in a}
                    rest = [d for u in member.live_units if u not in assigned for d in inst.units[u]]
                    for ch in _chunks([("doc", d) for d in rest]):
                        yield _query(ch)
                yield from self._finish_waiting(run)
        for i in range(self.extra):
            yield _work(i)
        yield self._answer()

    def _finish_waiting(self, run):
        """`wait` waits for every child; `dissolve`/`cancel` only for children holding a needed unit. Both send WAIT
        only while a child they wait for has not reported, so the continuations differ only in whom they wait for."""
        p, live = self.plan, set(self.member.live_units)
        kids = [f"A0.{i + 1}" for i in range(len(self.assign))]
        if p.cont == "wait" or self.inst.triage_filters_units or not self.inst.triage:
            needed = kids
        else:
            needed = [c for c, a in zip(kids, self.assign) if set(a) & live]
            if p.cont == "cancel":
                # The status read below is a peek the root could only infer 0.5 s later; it only avoids an invalid
                # MESSAGE to a child that has just terminated. Disclosed in GATE_0_SPEC.md §3.
                for c, a in zip(kids, self.assign):
                    if not set(a) & live and run.agents[c].status != "terminated":
                        yield {"rationale": "This assignment is no longer needed.", "action": "MESSAGE", "to": c,
                               "content": STOP}
        mode = "all" if set(needed) == set(kids) else "any"
        while not all(self._reported(run, c) for c in needed):
            yield {"rationale": "Wait for the reports still needed.", "action": "WAIT", "wait_for": mode}

    # ---- children
    def _stopped(self, agent, run) -> bool:
        return any(m.recipient == agent.id and m.sender == agent.parent and m.kind == "message" and m.delivered
                   and m.content == STOP for m in run.messages)

    def _child(self, agent, run):
        idx = int(agent.id.split(".")[-1]) - 1
        report = {"rationale": "Report back.", "action": "TERMINATE",
                  "answer": "Facts found: the requested value for each entity read, quoted from the source text."}
        if self.plan.prefix == "triage":
            plan = [_query(ch) for ch in _chunks([("doc", d) for d in self.child_docs[idx]])]
        else:
            units = self.assign[idx]
            if self.inst.triage_filters_units:  # template A: triage first, then only the selected units
                mine = [d for u in units if u in self.member.live_units for d in self.inst.units[u]]
                plan = [_query(self.triage_reqs)] + [_query(ch) for ch in _chunks([("doc", d) for d in mine])]
            else:
                plan = [_query(ch) for ch in _chunks([("doc", d) for d in self._docs_of(units)])]
        plan += [_work(i) for i in range(self.extra)]
        for step in plan:
            if self._stopped(agent, run):
                yield {"rationale": "Stopped by the parent.", "action": "TERMINATE",
                       "answer": "Stopped: assignment cancelled."}
                return
            yield step
        yield report


# --------------------------------------------------------------------------- running and checking


def _strip(e: dict) -> dict:
    return {k: v for k, v in e.items() if k not in ("wall", "run_id")}


def _digest(events: list[dict]) -> str:
    return hashlib.sha256(json.dumps([_strip(e) for e in events], sort_keys=True, default=str).encode()).hexdigest()


def run_plan(inst: Instance, member: Member, plan: Plan, regime: Regime, asm: Assumptions,
             constants: Constants) -> dict:
    """Run one organization and return its metrics plus the Gate-0 checks (all derived from the event log)."""
    program = Program(inst, member, plan, asm.extra_work_steps)
    policy = ScriptedPolicy(program, reasoning_tokens=asm.reasoning_tokens, input_scale=asm.input_scale)
    cfg = RunConfig(inst.task(member), regime, "developmental", compute=constants.compute, coord=constants.coord,
                    fixed_rule_spawns=True)
    run = Run(cfg, policy, inst.info(member, constants.sources))
    t0_state = hashlib.sha256((run.system_prompt_for(True) + "\x00" + run.catalog).encode()).hexdigest()
    run.execute()
    ev = run.log.events
    m = metrics_from_events(ev)
    calls: dict[str, int] = {}
    for e in ev:
        if e["type"] == "RESOURCE_CONSUMED" and e["kind"] == "llm":
            calls[e["agent"]] = calls.get(e["agent"], 0) + 1
    return {**{k: m[k] for k in ("outcome", "quality", "elapsed_s", "money_usd", "llm_calls", "in_tokens",
                                 "out_tokens", "agents", "invalid_actions", "cap_hits", "termination_reasons",
                                 "parallel")},
            "root_calls": calls.get("A0", 0), "max_child_calls": max((v for a, v in calls.items() if a != "A0"),
                                                                     default=0),
            **checks(inst, member, ev), "t0_state": t0_state, "root_brief": _root_brief_digest(run)}


def _root_brief_digest(run: Run) -> str:
    root = run.agents["A0"]
    first_user = next(m["content"] for m in root.transcript if m["role"] == "user")
    return hashlib.sha256(first_user.split("\n\nStatus:")[0].encode()).hexdigest()


def checks(inst: Instance, member: Member, events: list[dict]) -> dict:
    """Information completeness, the reveal time, the pre-reveal digest and the organizational signature."""
    triage_sources = {("structured" if k == "sql" else t) for k, t in inst.triage}

    def is_triage(e):
        return e["type"] == "INFORMATION_QUERIED" and e["ok"] and (
            (e["kind"] == "structured" and "structured" in triage_sources) or e["source"] in triage_sources)

    first = next((e for e in events if is_triage(e)), None)
    t_reveal = first["t"] if first else None
    pre = [e for e in events if first is None or e["seq"] < first["seq"]]
    # who read what, and which children's reports reached the root before it decided to answer
    answer_start = max((e["t"] for e in events if e["type"] == "ACTION_STARTED" and e["agent"] == "A0"
                        and e["action"] == "TERMINATE"), default=None)
    delivered = {e["agent"] for e in events if e["type"] == "MESSAGE_SENT" and e["kind"] == "report"
                 and e["to"] == "A0" and answer_start is not None and e["deliver_at"] <= answer_start}
    known_docs, triage_known = set(), False
    for e in events:
        if e["type"] != "INFORMATION_QUERIED" or not e["ok"]:
            continue
        if e["agent"] == "A0" and (answer_start is None or e["t"] <= answer_start) or e["agent"] in delivered:
            if e["kind"] == "unstructured":
                known_docs.add(e["source"])
            if is_triage(e):
                triage_known = True
    complete = set(member.needed) <= known_docs and (triage_known or not inst.triage)
    spawned = [e for e in events if e["type"] == "AGENT_SPAWNED" and e["agent"] == "A0"]
    reports = {e["agent"]: e["content"] for e in events if e["type"] == "MESSAGE_SENT" and e["kind"] == "report"}
    terms = {e["agent"]: e["reason"] for e in events if e["type"] == "AGENT_TERMINATED"}
    dissolved = sum(1 for e in spawned if terms.get(e["child"]) != "completed"
                    or reports.get(e["child"], "").startswith("Stopped"))
    sig = [sum(1 for e in spawned if t_reveal is None or e["t"] < t_reveal),
           sum(1 for e in spawned if t_reveal is not None and e["t"] >= t_reveal), dissolved]
    return {"info_complete": complete, "t_reveal": t_reveal, "pre_reveal": _digest(pre), "signature": sig}


def clean(rec: dict) -> bool:
    """A run counts only if it answered correctly with every needed fact delivered and no defect or starvation."""
    reasons = rec["termination_reasons"]
    return (rec["outcome"] == "answered" and rec["quality"] == 1.0 and rec["info_complete"]
            and rec["invalid_actions"] == 0 and rec["cap_hits"] == 0 and "budget_exhausted" not in reasons
            and "lifetime_expired" not in reasons)


def fitness(rec: dict, regime: Regime) -> float | None:
    """The calibration's fitness (calibrate._fitness) for a clean run; None for an infeasible one."""
    if not clean(rec):
        return None
    return (rec["quality"] - rec["money_usd"] / regime.task_value
            - regime.value_of_time * rec["elapsed_s"] / regime.task_value)
