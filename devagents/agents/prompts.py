"""Everything an agent reads (SPEC §6).

Every agent in every mode gets the same system prompt except for one MODE RULES line. That
line is written in parallel, role-neutral form. The prompt never mentions task classes or
regime names, and never suggests an organization.
"""

from __future__ import annotations

from devagents.runtime.resources import CoordinationCosts, ComputeOption, to_usd

ACTION_HELP = {
    "WORK": 'WORK {"notes"}: think or record intermediate results. No cost beyond the step itself.',
    "QUERY": 'QUERY {"requests": [{"kind": "sql", "target": "<SELECT ...>"} or {"kind": "doc", "target": "<doc id>"}, ...]}: '
             "read up to 10 sources. They are processed one after another, and their results enter your context.",
    "SPAWN": 'SPAWN {"children": [{"objective", "context", "budget_usd", "lifetime_s"}, ...], "wait_for_children"}: create '
             "1 to {k} agents. budget_usd moves from your balance to the new agent, and lifetime_s bounds how long it may "
             'run. If "wait_for_children" is true, you then wait until all of your children have terminated, without '
             "another decision step.",
    "MESSAGE": 'MESSAGE {"to", "content"}: send a message to your parent or to one of your children (by agent id).',
    "WAIT": 'WAIT {"wait_for": "any" or "all", "max_wait_s"}: pause until a message arrives ("any") or until all of '
            "your children have terminated and their reports have arrived (\"all\"), or until max_wait_s passes. "
            "Waiting costs no money, but time passes.",
    "TERMINATE": 'TERMINATE {"answer"}: finish. If you are the root agent, "answer" is the final answer to the task. '
                 'Otherwise "answer" is your report to your parent (charged as a message). Your unused balance returns to your parent.',
}
ACTION_ORDER = ["WORK", "QUERY", "SPAWN", "MESSAGE", "WAIT", "TERMINATE"]

_FIXED_SHARE = ("each created agent receives an equal share of {share:.0%} of your balance (after fees) and a lifetime of "
                "{life:.0%} of your remaining time; the budget_usd and lifetime_s you write are ignored")
MODE_RULES = {
    "single": "MODE RULES: SPAWN, MESSAGE and WAIT are not available in this run.",
    "developmental": "MODE RULES: You may SPAWN at any step; agents you create may also SPAWN.",
    "router_root": "MODE RULES: You may SPAWN only as your first action, at most once; agents you create cannot SPAWN.",
    "router_child": "MODE RULES: SPAWN is not available to you.",
    "central_root": ("MODE RULES: Your first action must be SPAWN, and you wait until your children have terminated; "
                     "agents you create cannot SPAWN; " + _FIXED_SHARE + "."),
    "central_child": "MODE RULES: SPAWN is not available to you.",
}


def _money(musd: int) -> str:
    return f"${to_usd(musd):.4f}"


def system_prompt(*, mode_rules: str, catalog: str, compute: ComputeOption, coord: CoordinationCosts,
                  task_value: float, value_of_time: float, failure_penalty: float, max_children: int) -> str:
    action_lines = "\n".join(f"- {ACTION_HELP[a].replace('{k}', str(max_children))}" for a in ACTION_ORDER)
    return f"""You are an agent in a simulated environment in which every resource is metered. Each step you take is one decision (an LLM call) that selects exactly one action. The decision itself costs money and simulated time, in addition to the action's own cost.

SCORING. The whole system (every agent in this run) is scored once, when the root agent submits the final answer:
  score = correct (1 if the final answer is right, else 0)
          - (dollars spent by all agents) / {task_value:g}
          - {value_of_time:g} x (simulated seconds elapsed until the final answer) / {task_value:g}
          - {failure_penalty:g} if no final answer is submitted before the deadline
Individual agents have no scores of their own. Choose actions to maximize this score.

RESOURCES AND PRICES
- Money: you hold a balance. Every cost you incur is paid from it; you can never spend more than you hold.
- Each decision (LLM step): ${compute.price_in:g} per million input tokens and ${compute.price_out:g} per million output tokens (reasoning included). Your entire conversation so far is re-read, and paid for, on every step. Latency is about {compute.latency_base_s:g}s + {compute.latency_in_s * 1000:g}s per 1k input tokens + {compute.latency_out_s:g}s per output token.
- Time: you act sequentially, one action at a time. Different agents act concurrently. At most {max_children + 1} agents can be alive at once in a run.
- Creating an agent (SPAWN): fee {_money(coord.spawn_fee)} per agent plus {_money(coord.transfer_per_token * 1000)} per 1k tokens of objective+context copied to it; the SPAWN takes {coord.spawn_latency_s:g}s of your time. A new agent starts with only these rules, the source catalog, and the objective, context and budget you give it. It runs concurrently with you, pays for its own steps from its budget, and returns its unused budget to you when it terminates.
- Messages and reports: fee {_money(coord.message_fee)} plus {_money(coord.message_per_token * 1000)} per 1k tokens; delivered {coord.message_latency_s:g}s after sending.
- Information sources:
{catalog}

ACTIONS. Reply with exactly one JSON object containing "rationale" (one short sentence), "action", and the fields that action needs:
{action_lines}
{mode_rules}"""


def root_brief(*, task_id: str, question: str, agent_id: str, balance: int, deadline: float, value_of_time: float) -> str:
    return (f"Task {task_id}. You are the root agent {agent_id}.\n\n"
            f"Question: {question}\n\n"
            f"Your resources: balance {_money(balance)} (the entire budget of this run). The deadline is t={deadline:.1f}s of "
            f"simulated time and the clock is at t=0.0s. Value of time: ${value_of_time:g} per second.\n"
            "Give the final answer as just the requested value (a name or a number).")


def child_brief(*, agent_id: str, parent: str, t: float, objective: str, context: str, balance: int, deadline: float,
                value_of_time: float) -> str:
    return (f"You are agent {agent_id}, created by {parent} at t={t:.1f}s.\n\n"
            f"Objective from {parent}: {objective}\n\n"
            f"Context from {parent}: {context or '(none)'}\n\n"
            f"Your resources: balance {_money(balance)}. Your lifetime ends at t={deadline:.1f}s, when you are terminated "
            f"automatically. Value of time for the whole system: ${value_of_time:g} per second.\n"
            "When you are done, TERMINATE with your report as \"answer\".")


def status_block(*, t: float, deadline: float, balance: int, steps: int, max_steps: int, last_cost: int,
                 last_latency: float, children: list[str], messages: list[str]) -> str:
    lines = [f"Status: t={t:.1f}s, your deadline t={deadline:.1f}s ({max(0.0, deadline - t):.1f}s left) | balance {_money(balance)} "
             f"| last step cost {_money(last_cost)} and took {last_latency:.1f}s | steps used {steps}/{max_steps}"]
    if children:
        lines.append("Children: " + "; ".join(children))
    if messages:
        lines.append("New messages:\n" + "\n".join(f"  - {m}" for m in messages))
    return "\n".join(lines)
