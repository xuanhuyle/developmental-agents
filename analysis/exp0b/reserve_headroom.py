"""Experiment 0b, step 0: audit the live step reserve's headroom on a pilot's event logs. Offline, no API call.

For every live LLM step it needs the input bound the runtime reserved (`Run._input_upper_bound`), which the log does
not record. So each logged run is replayed through the unchanged runtime with a policy that returns the logged
actions and the logged API usage. The runtime then recomputes every observation, status block and reserve exactly as
in the live run. A run counts only if its replayed event log equals the original (wall-clock fields aside);
mismatches are reported and excluded.

It prints numbers only: no prompt, document text, answer, message content or key is printed or written. The --json
file adds one row of numbers per step (run, agent, step, tokens, bound, sizes).

The replay reproduces the live bound only if the prompt and observation code equal the pilot's; the output records the
checkout's identity (git HEAD, sha256 of prompts.py and runtime.py) so that this can be checked.

    python analysis/exp0b/reserve_headroom.py results/pilot [--json results/exp0b_analysis/reserve_headroom.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from devagents.config import Constants  # noqa: E402
from devagents.environment.sources import InformationEnvironment  # noqa: E402
from devagents.environment.tasks import TASKS_BY_ID  # noqa: E402
from devagents.environment.world import load_world  # noqa: E402
from devagents.agents.policies import visible_text  # noqa: E402
from devagents.runtime.events import EventLog, read_events  # noqa: E402
from devagents.runtime.runtime import REQUEST_OVERHEAD_TOKENS, Decision, Run, RunConfig  # noqa: E402

BUDGET_CAPPED = "output truncated at the budget-capped max_tokens"
TRUNCATED = "output truncated at max_tokens"
IGNORED = {"wall", "wall_s"}  # real wall-clock time, not part of the simulation


class Replay:
    """Returns each agent's logged decisions in order and records the reserve the runtime applied to each."""

    def __init__(self, events: list[dict]):
        started = {(e["agent"], e["step"]): e for e in events if e["type"] == "ACTION_STARTED"}
        completed = {(e["agent"], e["step"]): e for e in events if e["type"] == "ACTION_COMPLETED"}
        self.queue = defaultdict(list)
        steps = defaultdict(int)
        for e in events:
            if e["type"] == "RESOURCE_CONSUMED" and e["kind"] == "llm":
                steps[e["agent"]] += 1
                key = (e["agent"], steps[e["agent"]])
                self.queue[e["agent"]].append((e, started.get(key), completed.get(key)))
        self.steps = []

    def decide(self, agent, allowed, max_tokens, run):
        usage, start, done = self.queue[agent.id].pop(0)
        in_upper = run._input_upper_bound(agent)  # pure: exactly the bound _on_start just reserved
        # Share of the new turn's characters that are SQL results (sizes only; no text leaves this function).
        turn = visible_text(agent.transcript[-1]["content"])
        sql = sum(len(part) for part in turn.split("\n\n[") if part.startswith("[sql]") or part.startswith("sql]"))
        self.steps.append({"run": run.cfg.run_id, "agent": agent.id, "step": agent.steps, "first": not agent.prev_in_tokens,
                           "in": usage["in_tokens"], "out": usage["out_tokens"], "est_in": usage.get("est_in_tokens") or 0,
                           "in_upper": in_upper, "headroom": in_upper - usage["in_tokens"], "max_tokens": max_tokens,
                           "prev_in": agent.prev_in_tokens, "prev_out": agent.prev_out_tokens,
                           "new_chars": agent.new_chars + (0 if agent.prev_in_tokens else len(agent.system)),
                           "sql_share": sql / len(turn) if turn else 0.0})
        detail = start.get("detail") if start else None
        action = detail if isinstance(detail, dict) else None
        error = (done or {}).get("error", "") if action is None else ""
        truncated = error in (TRUNCATED, BUDGET_CAPPED)
        return Decision(action, usage["in_tokens"], usage["out_tokens"], json.dumps(detail),
                        error=TRUNCATED if error == BUDGET_CAPPED else error, truncated=truncated,
                        wall_s=usage.get("wall_s", 0.0), est_in_tokens=usage.get("est_in_tokens", 0),
                        est_visible_out_tokens=usage.get("est_visible_out_tokens", 0))


def comparable(events: list[dict]) -> list[dict]:
    """The simulation content of a log. RUN_STARTED's `policy` names the live policy, which the replay cannot be."""
    return [{k: v for k, v in e.items() if k not in IGNORED and not (e["type"] == "RUN_STARTED" and k == "policy")}
            for e in events]


def replay(path: Path, constants: Constants) -> tuple[bool, list[dict], str]:
    events = read_events(path)
    start = next(e for e in events if e["type"] == "RUN_STARTED")
    if not any(e["type"] == "RUN_COMPLETED" for e in events):
        return False, [], "incomplete log"
    cfg = RunConfig(TASKS_BY_ID[start["task_id"]], constants.regimes[start["regime"]], start["mode"],
                    compute=constants.compute, coord=constants.coord, repeat=start.get("repeat", 0),
                    frozen_sha=start["audit"].get("frozen_sha", ""))
    policy = Replay(events)
    run = Run(cfg, policy, InformationEnvironment(load_world(), constants.sources), EventLog(cfg.run_id))
    try:
        run.execute()
    except Exception as exc:  # a replay that raises is reported, never trusted
        return False, policy.steps, f"replay raised {type(exc).__name__}"
    if comparable(run.log.events) != comparable(events):
        first = next((i for i, (a, b) in enumerate(zip(comparable(run.log.events), comparable(events))) if a != b),
                     min(len(events), len(run.log.events)))
        return False, policy.steps, f"replayed log differs from the original at event {first}"
    return True, policy.steps, ""


def quantile(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    i = q * (len(xs) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def code_identity() -> dict:
    def sha(rel):
        return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()[:16]
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        head = "unknown"
    return {"git_head": head, "prompts.py": sha("devagents/agents/prompts.py"), "runtime.py": sha("devagents/runtime/runtime.py")}


def audit(pilot_dir: Path) -> dict:
    manifest = json.loads((pilot_dir / "manifest.json").read_text())
    constants = Constants.from_json(manifest["constants"])
    runs, steps, problems = 0, [], {}
    logs = {p.stem: p for p in sorted((pilot_dir / "events").glob("*.jsonl"))}
    for run_id in manifest.get("planned_runs", []):
        if run_id not in logs:
            problems[run_id] = "planned run has no event log"
    for run_id, path in logs.items():
        ok, s, why = replay(path, constants)
        if ok:
            runs += 1
            steps += s
        else:
            problems[run_id] = why
    errors = Counter()
    if (pilot_dir / "errors.jsonl").exists():
        for line in (pilot_dir / "errors.jsonl").read_text().splitlines():
            if line.strip():
                errors[json.loads(line)["error"].split(":")[0]] += 1  # the exception type only
    if not steps:
        return {"code": code_identity(), "replayed_runs": 0, "problems": problems, "infrastructure_errors": dict(errors)}

    ratio = [s["in"] / s["est_in"] for s in steps if s["est_in"]]
    head = [s["in_upper"] - s["in"] for s in steps]
    pct = [(s["in_upper"] - s["in"]) / s["in_upper"] for s in steps]
    # How much of the fixed request allowance each step used: input beyond the bound without the allowance.
    used = [s["in"] - (s["in_upper"] - REQUEST_OVERHEAD_TOKENS) for s in steps]
    # New input tokens per new character on later steps (the bound assumes at most 0.5). First steps carry the whole
    # fixed request overhead (schema, framing), which the allowance exists for, so they are judged by `used` instead.
    later = [s for s in steps if not s["first"] and s["new_chars"]]
    rate = [(s["in"] - s["prev_in"] - s["prev_out"]) / s["new_chars"] for s in later]
    worst = max(rate, default=0.0)
    big = [r for s, r in zip(later, rate) if s["new_chars"] >= 2000]
    sql = [r for s, r in zip(later, rate) if s["sql_share"] >= 0.5]
    doc = [r for s, r in zip(later, rate) if s["sql_share"] < 0.5 and s["new_chars"] >= 2000]
    q = lambda xs: {"median": statistics.median(xs), "p90": quantile(xs, 0.9), "p95": quantile(xs, 0.95),  # noqa: E731
                    "p99": quantile(xs, 0.99), "max": max(xs), "min": min(xs), "n": len(xs)} if xs else None
    tightest = min(steps, key=lambda s: s["headroom"])
    exhaust = lambda r: (REQUEST_OVERHEAD_TOKENS / (r - 0.5)) if r > 0.5 else float("inf")  # noqa: E731
    return {
        "code": code_identity(), "planned_runs": len(manifest.get("planned_runs", [])),
        "replayed_runs": runs, "llm_steps": len(steps), "problems": problems, "infrastructure_errors": dict(errors),
        "ratio_in_over_est": q(ratio),
        "headroom_tokens": q(head), "headroom_fraction": q(pct),
        "steps_within": {f"{int(p * 100)}%": sum(x < p for x in pct) for p in (0.10, 0.05, 0.01)},
        "violations": sum(h < 0 for h in head),
        "overhead_allowance_used_tokens": q(used),
        "overhead_allowance_used_fraction_max": max(used) / REQUEST_OVERHEAD_TOKENS,
        "first_step_allowance_used_fraction_max": max(u for u, s in zip(used, steps) if s["first"]) / REQUEST_OVERHEAD_TOKENS,
        "tightest_step": {k: tightest[k] for k in ("run", "agent", "step", "in", "in_upper", "headroom", "new_chars")},
        "later_steps_new_tokens_per_new_char": q(rate),
        "later_steps_rate_observations_ge_2000_chars": q(big),
        "later_steps_rate_sql_dominated": q(sql),
        "later_steps_rate_doc_dominated": q(doc),
        "largest_later_observation_chars": max((s["new_chars"] for s in later), default=0),
        # At the worst later-step rate, the observation size (characters) that would use up the whole allowance
        # (infinite when no later step exceeds 0.5 tokens per character).
        "chars_that_exhaust_allowance_at_worst_later_rate": exhaust(worst),
        "output": {"max_out_over_max_tokens": max(s["out"] / s["max_tokens"] for s in steps),
                   "steps_at_max_tokens": sum(s["out"] >= s["max_tokens"] for s in steps)},
        "steps": steps,  # numbers only; omitted from the printed summary
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pilot_dir", nargs="?", default="results/pilot")
    p.add_argument("--json", help="also write the numbers to this file")
    a = p.parse_args(argv)
    res = audit(Path(a.pilot_dir))
    dump = lambda x: json.dumps(x, indent=1, default=str)  # noqa: E731
    print(dump({k: v for k, v in res.items() if k != "steps"}))
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(dump(res))
    return 0 if res["replayed_runs"] and not res["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
