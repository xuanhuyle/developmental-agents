"""Every environment constant in one place, with a JSON round-trip.

The code defaults are *provisional*. `python -m devagents freeze` writes the frozen values to
data/frozen.json (SPEC §7.4), and the main run uses only those.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from devagents.environment.sources import SourceCosts
from devagents.environment.tasks import REGIMES, Regime
from devagents.runtime.resources import COMPUTE_OPTIONS, DEFAULT_COMPUTE, ComputeOption, CoordinationCosts

FROZEN_PATH = Path(__file__).resolve().parents[1] / "data" / "frozen.json"
SPEC_PATH = Path(__file__).resolve().parents[1] / "SPEC.md"


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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_frozen(path: Path = FROZEN_PATH) -> dict | None:
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None
