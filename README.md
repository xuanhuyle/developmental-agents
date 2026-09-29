# developmental-agents: Experiment 0

This is a small, falsifiable experiment. It asks whether a **resource-aware agent decides economically when to
divide**, that is, when to spend part of its own budget to create another agent. The test is whether the same
lifecycle policy stays single where division does not pay and divides where it does. It should do this because the
time–money–quality trade-off changes, not because the task looks a certain way.

This is not a multi-agent framework. It is the smallest controlled environment we could build in which that question
has a measurable answer, including a clean negative one. The pre-registered definition is in [`SPEC.md`](SPEC.md).
The current state is in [`EXPERIMENT_STATUS.md`](EXPERIMENT_STATUS.md).

## The hypothesis

**H.** Local, resource-aware decisions to spawn and self-terminate (mode `developmental`) produce organizations that
depend on the task and the resource conditions. Those organizations improve the time–money–quality frontier relative
to a fixed single agent (`single`) and a fixed central decomposition (`central`), without collapsing to always-spawn or
never-spawn.

H is **not supported** if any of the pre-registered criteria in SPEC §8 fires:

1. `developmental` spawns in most cells where one agent is best (always-spawn collapse).
2. It rarely divides the work in cells where division pays (never-spawn collapse).
3. Its division does not track the designed trade-offs. This is checked three ways: within a regime; across the two
   value-of-time regimes on *identical* tasks; and on *dissociation* tasks that look like parallel work but are
   answered by one cheap SQL query.
4. With identical budget, deadline, model, sources and prompts, it shows no cost gain over `single` where division
   pays, or it loses quality, or it loses cost where division does not pay.
5. The fixed `central` decomposition matches it where the two are designed to differ.

A secondary, pre-registered question (**H2**) compares `developmental` with `router`, a one-shot organizational
decision made at the start. In this environment an ideal router reproduces every optimal organization, so H2 can only
reveal practical differences (SPEC §10).

## The setup in one paragraph

A fictional company world provides one SQLite database and 15 Markdown documents, deterministic and committed under
`data/world/`. There are 15 questions with computed ground truth:

- **A** is answerable from one source.
- **B** needs 6–8 independent documents.
- **C** needs SQL and documents, in some cases with a one-query shortcut.

Each question runs under two regimes that differ only in the value of time. Every action has an explicit price and
latency, which the agent sees. The actions are WORK, QUERY, SPAWN (with budget, lifetime and context), MESSAGE, WAIT
and TERMINATE. Money is conserved in integer micro-dollars: a child's budget comes out of its parent's balance, and
unused money returns when the child terminates. Time is **simulated** by a deterministic discrete-event engine, so
results do not depend on API latency. Four modes share the same budget, deadline, model, sources and system prompt,
which differs only by one "MODE RULES" line: `single`, `central`, `router` and `developmental`.

## Running it

Requirements: Python ≥ 3.10. The core uses only the standard library. The real experiment needs `pip install anthropic`
and an `ANTHROPIC_API_KEY`. The tests need `pytest`.

**Without an API key**, these commands inspect and verify everything that does not need an LLM:

```bash
python -m devagents calibrate        # the environment's designed economics and the validity gate (~5 s)
python -m devagents criteria-check   # can the §8 criteria pass for an ideal policy and fail for collapses? picks R (~1 min)
pytest -q                            # 100 tests: accounting, lifecycle, baselines, ground truth, evaluator, pipeline
```

**The real experiment** follows the pre-registered protocol (SPEC §7.4):

```bash
pip install anthropic && export ANTHROPIC_API_KEY=...
python -m devagents pilot                          # single+central on 3 held-out tasks; measures tokens (~24 runs)
python -m devagents freeze --pilot results/pilot   # LLM-free: calibrate, gate, pick R, write data/frozen.json
git add data/frozen.json && git commit -m "Freeze Experiment 0"   # and record the sha in EXPERIMENT_STATUS.md
python -m devagents run --smoke                    # optional: all four modes on the pilot tasks (exploratory)
python -m devagents run                            # THE experiment: 15 tasks x 2 regimes x 4 modes x R repeats
python -m devagents report results/main            # verdict, validity, criteria, tables -> results/main/report.md
```

`run` refuses to start without a verified, non-provisional freeze. It can resume, so a completed run is never
repeated. `--workers N` sets how many runs execute concurrently. With `claude-opus-5-5` at effort `low`, the oracle
lower bound is about $0.03 for a single-agent run and $0.07 for a divided one. Expect a few dollars for the pilot and
roughly $25–$100 for the main suite at R = 3.

## Reading the results

`report.md` begins with a verdict:

- **SUPPORTED**: every validity condition holds and no criterion fires. This says only that, in this environment,
  this model's local division decisions tracked the designed trade-offs and paid for themselves against `single` and
  against a fixed decomposition.
- **NOT SUPPORTED**: at least one criterion fired. The report says which one, with its numbers:
  - criterion 1 means over-spawning;
  - criterion 2 means under-dividing;
  - criterion 3 means the division is not resource-driven (3b) or follows surface cues (3c);
  - criterion 4 means no frontier gain;
  - criterion 5 means a fixed decomposition suffices.
- **UNINFORMATIVE**: a validity condition failed. Examples: `single` cannot do the base task, the environment's
  designed trade-off did not materialize for real runs (the manipulation check), completion was too low, or the
  audit found unequal resources. Such a run neither supports nor falsifies H.

The per-cell Pareto frontier, H2 (`developmental` vs `router`), coordination spend and mean fitness are descriptive.
`report --value-of-time …` rescoring is stamped EXPLORATORY and never replaces the verdict. Every number is recomputed
from the append-only event logs in `results/<suite>/events/`.

## What this experiment cannot conclude

- **Generality.** It does not show that emergent organization beats well-engineered orchestration in general. It uses
  one model, one prompt, one small synthetic world, and a *designed* environment in which different organizations
  are optimal. That design is the manipulation, not a finding.
- **Latency model.** Time comes from a declared latency model. The premise is that concurrency comes only from
  multiple agents. Single-agent parallel tool calls are out of scope.
- **Local vs one-shot.** It does not show that local, incremental decisions beat a one-shot central decision. This
  environment has no cells where that difference is designed to pay (see H2).
- **No caching.** No prompt caching is used, which raises per-agent overhead. Different price ratios could change
  which organizations are optimal.

## Layout

```
SPEC.md, EXPERIMENT_STATUS.md, README.md
data/world/            committed synthetic world (structured.sql + docs/*.md); regenerate: python -m devagents build-world
data/frozen.json       frozen constants, labels and R (currently PROVISIONAL: no pilot yet)
devagents/
  environment/         world generator, task suite and regimes, information sources with costs
  runtime/             resources (money, compute options, ledger), event log, discrete-event runtime and modes
  agents/              prompts (shared across modes), LLM policy (Anthropic SDK) and scripted policy
  evals/               metrics and fitness, calibration oracle, §8 evaluator and criteria check, runner, report
  config.py            all constants, with a JSON round-trip for freezing
  __main__.py          CLI
tests/                 pytest suite
```
