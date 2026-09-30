"""Every environment constant in one place, with a JSON round-trip, and the experiments that use them.

The code defaults are *provisional*. `python -m devagents freeze` writes the frozen values to
data/frozen.json (SPEC §7.4), and the main run uses only those. Experiment 0b (SPEC_0B.md) changes four
monetary constants and keeps its own spec, frozen file and results; Experiment 0 is the default everywhere.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable

from devagents.environment.sources import SourceCosts
from devagents.environment.tasks import REGIMES, Regime
from devagents.runtime.resources import COMPUTE_OPTIONS, DEFAULT_COMPUTE, ComputeOption, CoordinationCosts

ROOT = Path(__file__).resolve().parents[1]
FROZEN_PATH = ROOT / "data" / "frozen.json"
SPEC_PATH = ROOT / "SPEC.md"

# Experiment 0b, amendment 0b-1 (SPEC_0B.md): B, V and both values of time scaled by s = 1.392. Nothing else changes.
EXP0B_BUDGET_USD = 1.392
EXP0B_TASK_VALUE = 0.696
EXP0B_VALUE_OF_TIME = {"relaxed": 0.0000696, "urgent": 0.0011136}


@dataclass(frozen=True)
class Constants:
    regimes: dict  # name -> Regime
    compute: ComputeOption
    coord: CoordinationCosts
    sources: SourceCosts

    def to_json(self) -> dict:
        return {"regimes": {k: asdict(v) for k, v in self.regimes.items()}, "compute": asdict(self.compute),
                "coord": asdict(self.coord), "sources": asdict(self.sources)}

    @staticmethod
    def from_json(d: dict) -> "Constants":
        return Constants(regimes={k: Regime(**v) for k, v in d["regimes"].items()}, compute=ComputeOption(**d["compute"]),
                         coord=CoordinationCosts(**d["coord"]), sources=SourceCosts(**d["sources"]))

    def with_value_of_time(self, regime: str, value: float) -> "Constants":
        regimes = dict(self.regimes)
        regimes[regime] = replace(regimes[regime], value_of_time=value)
        return replace(self, regimes=regimes)


def default_constants(compute: str = DEFAULT_COMPUTE) -> Constants:
    return Constants(regimes=dict(REGIMES), compute=COMPUTE_OPTIONS[compute], coord=CoordinationCosts(),
                     sources=SourceCosts())


def exp0b_constants(compute: str = DEFAULT_COMPUTE) -> Constants:
    base = default_constants(compute)
    regimes = {k: replace(r, budget_usd=EXP0B_BUDGET_USD, task_value=EXP0B_TASK_VALUE,
                          value_of_time=EXP0B_VALUE_OF_TIME[k]) for k, r in base.regimes.items()}
    return replace(base, regimes=regimes)


@dataclass(frozen=True)
class Experiment:
    """What `freeze`, `run` and `report` read and write for one pre-registered experiment."""
    name: str
    spec: Path
    frozen: Path
    results: Path  # relative to the working directory, like every results path
    constants: Callable[[str], Constants]


EXPERIMENTS = {
    "0": Experiment("0", SPEC_PATH, FROZEN_PATH, Path("results"), default_constants),
    "0b": Experiment("0b", ROOT / "SPEC_0B.md", ROOT / "data" / "exp0b" / "frozen.json", Path("results") / "exp0b",
                     exp0b_constants),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_frozen(path: Path = FROZEN_PATH) -> dict | None:
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None
