"""Resource primitives: money units, compute options, coordination prices, and the budget ledger.

Money is stored as integer micro-dollars (µ$) so conservation checks are exact.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MICRO = 1_000_000


def usd(x: float) -> int:
    """Dollars -> integer micro-dollars."""
    return int(round(x * MICRO))


def to_usd(musd: int) -> float:
    return musd / MICRO


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate (≈4 chars/token). Used for sizes shown to agents and for
    offline (scripted/oracle) policies; real LLM steps are charged with API-reported usage."""
    return max(1, math.ceil(len(text) / 4)) if text else 0


@dataclass(frozen=True)
class ComputeOption:
    """One way of turning money and time into reasoning. Exp 0 uses a single option for all agents."""
    id: str
    model: str
    capability: float  # relative, informational only in Exp 0
    price_in: int  # µ$ per input token
    price_out: int  # µ$ per output token (reasoning tokens included)
    latency_base_s: float
    latency_in_s: float  # seconds per input token (prefill)
    latency_out_s: float  # seconds per output token
    effort: str  # reasoning effort requested from the model
    context_capacity: int  # tokens
    max_concurrency: int  # max simultaneously live agents using this option
    max_output_tokens: int = 2048  # per step cap before budget capping
    min_step_tokens: int = 256  # below this an agent cannot afford to think

    def step_cost(self, in_tokens: int, out_tokens: int) -> int:
        return in_tokens * self.price_in + out_tokens * self.price_out

    def step_latency(self, in_tokens: int, out_tokens: int) -> float:
        return self.latency_base_s + in_tokens * self.latency_in_s + out_tokens * self.latency_out_s


# Prices are the providers' list prices ($/MTok == µ$/token). Latencies are declared
# modelling assumptions (SPEC §3.1), not measurements.
COMPUTE_OPTIONS = {
    "opus": ComputeOption("opus", "claude-opus-5-5", capability=1.0, price_in=4, price_out=20,
                          latency_base_s=1.5, latency_in_s=0.00005, latency_out_s=0.02, effort="low",
                          context_capacity=1_000_000, max_concurrency=9),
    "sonnet": ComputeOption("sonnet", "claude-sonnet-5-5", capability=0.8, price_in=2, price_out=10,
                            latency_base_s=1.0, latency_in_s=0.00004, latency_out_s=0.012, effort="low",
                            context_capacity=1_000_000, max_concurrency=9),
}
DEFAULT_COMPUTE = "opus"


@dataclass(frozen=True)
class CoordinationCosts:
    spawn_fee: int = usd(0.001)  # per child: instantiating an agent
    transfer_per_token: int = 2  # µ$ per token of context copied into a child
    spawn_latency_s: float = 1.0
    message_fee: int = usd(0.0002)
    message_per_token: int = 2  # µ$ per token of message content
    message_latency_s: float = 0.5


class InsufficientFunds(Exception):
    pass


class Ledger:
    """Per-agent balances inside one fixed run budget. The only ways money moves are
    `charge` (spent, gone) and `transfer` (between agents). Nothing creates money."""

    def __init__(self, budget: int, root: str):
        if budget < 0:
            raise ValueError("budget must be non-negative")
        self.budget = budget
        self.balance: dict[str, int] = {root: budget}
        self.spent: dict[str, int] = {root: 0}

    def open(self, agent: str) -> None:
        if agent in self.balance:
            raise ValueError(f"account {agent} already exists")
        self.balance[agent] = 0
        self.spent[agent] = 0

    def charge(self, agent: str, amount: int) -> None:
        if amount < 0:
            raise ValueError("negative charge")
        if amount > self.balance[agent]:
            raise InsufficientFunds(f"{agent}: charge {amount} > balance {self.balance[agent]}")
        self.balance[agent] -= amount
        self.spent[agent] += amount

    def transfer(self, src: str, dst: str, amount: int) -> None:
        if amount < 0:
            raise ValueError("negative transfer")
        if amount > self.balance[src]:
            raise InsufficientFunds(f"{src}: transfer {amount} > balance {self.balance[src]}")
        self.balance[src] -= amount
        self.balance[dst] += amount

    @property
    def total_spent(self) -> int:
        return sum(self.spent.values())

    def check(self) -> None:
        held = sum(self.balance.values())
        assert all(b >= 0 for b in self.balance.values()), "negative balance"
        assert held + self.total_spent == self.budget, f"conservation violated: {held} + {self.total_spent} != {self.budget}"
        assert self.total_spent <= self.budget
