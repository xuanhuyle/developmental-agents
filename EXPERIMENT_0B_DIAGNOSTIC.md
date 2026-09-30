# Experiment 0b: diagnostic

**Status: diagnostic only.** This document changes nothing. The verdict stands permanently:

> **Experiment 0b: UNINFORMATIVE because the preregistered realized manipulation check failed.**

No API call was made, no live run was repeated, and no prompt, runtime code, constant, gate, criterion or frozen file
was modified.

## How to read the evidence

Every statement below carries one of three evidence levels.

| level | what it rests on | how to reproduce it |
|---|---|---|
| **[code]** | the repository at 67c9d50, and the rendered prompts, schema and frozen configuration | read the files |
| **[sim]** | offline, LLM-free simulation in the real runtime, at the frozen 0b constants and the frozen pilot-measured token assumptions | `python analysis/exp0b_diagnostic/offline.py` |
| **[reported]** | the live report numbers relayed by the experimenter | not yet recomputed here |

**The live event logs are not in this repository or this environment.** That covers both `results/exp0b/main` and
`results/pilot`. The per-run live facts are therefore **[pending]** until this has been run where the logs are:

```
py analysis\exp0b_diagnostic\traces.py results\exp0b\main --pilot results\pilot --out results\exp0b_diagnostic
```

It is offline and prints structure only: action types, counts, dollars, seconds, error strings, and each root's first
rationale, which is written before any document is read. It needs Steps 1, 3, 7 and 8 of the brief. §2, §4, §8 and §9
pre-declare how each possible trace outcome would change the conclusions. The script was validated on a synthetic
360-style suite and pilot made with the test suite's fake client: every section, including the recomputation against
`summary.json`, ran and agreed.

---

## 1. Executive conclusion

**Diagnosis: D, MIXED.**

| component | finding | confidence |
|---|---|---|
| **B. Oracle/live baseline mismatch** | Real and sufficient to explain the failed check. The check needs `central` to realize a parallel one-shot decomposition, but live `central` leaves the decomposition to the LLM. The live numbers match a one-child `central` almost exactly. | **high** |
| **A. Hard interface defect** | No evidence. SPAWN is available to `developmental` and `router`; one SPAWN can create 1–8 children from a documented list; costs, balance, deadline and the time price are all shown. | **low** (pending the traces) |
| **C. Substantive policy behaviour, qualified** | `developmental` and `router` never divided, and `central`, forced to divide, chose one child. The benefit of division was *derivable* from the prompt but never stated, which is by design (the prompt "never suggests an organization"). This is a behavioural observation about this model, prompt and effort level, not an interface defect. | **medium** (the rationales can raise or lower it) |

**The mechanism of the failed manipulation check.** In the four B-urgent cells:
- a `central` with one child is worse than `single` by construction. It does the same sequential reading plus spawn,
  coordination and extra LLM steps: 0.282 against 0.345 **[sim]**;
- the reported live values, 0.2830 against 0.3552 **[reported]**, match that organization to within 0.001 for
  `central`;
- had `central` instantiated the calibrated one-shot fan-out, it would have scored 0.554, and central > single would
  have held at all 18 perturbation-grid points **[sim]**.

**The mismatch predates 0b.** It has been in SPEC.md since Experiment 0's first commit (2851d2d). §6 lets `central`
spawn "1–K children", while §7.3 models `central` as "the best one-shot division" **[code]**.

**A successor experiment** is justified only narrowly: to make the fixed-decomposition baseline, and the manipulation
check that depends on it, independent of the LLM's choice of topology. It must not change the developmental treatment.
See §12.

## 2. Experiment 0b outcome

**[reported]**, from the preregistered report:

| item | value |
|---|---|
| runs | 360/360 completed, 0 failed, R = 3 |
| validity (v), B-urgent | `central` 0.2830 against `single` 0.3552; central > single required; **FAILED** |
| validity (v), B-relaxed | `central` 0.8244 < `single` 0.8771, as intended |
| validity (v), A | `single` 0.8913 ≥ `central` 0.8821, as intended |
| developmental | spawned_rate(S) = 0; parallel_rate(P) = 0; never-spawn fires; within-regime contrast 0; twin ≈ 0.03; dissociation ≈ 0.03; no cost gain vs `single` on P |
| router | reportedly never spawns |
| central | reportedly one child (two agents) almost everywhere |

**Internal-consistency flag [code].** The reported twin and dissociation contrasts (≈ 0.03) cannot coexist with the
reported spawned_rate(S) = 0 and parallel_rate(P) = 0 under the evaluator's definitions
(`devagents/evals/analysis.py:evaluate`):
- the twin contrast (3b) is parallel_rate(twin cells, urgent) − spawned_rate(twin cells, relaxed);
- the dissociation contrast (3c) is parallel_rate(P_urgent) − spawned_rate(D_urgent).

In the frozen sets, P = P_urgent = the urgent twin cells (T01, T04, T07, T10), and the relaxed twin cells and D_urgent
(T06, T13, T14 urgent) are all S cells. If both rates are exactly 0, both
contrasts are exactly 0. So either one of the rates is small but not zero, or the contrasts were quoted loosely.
`traces.py` prints the evaluator's statistics alongside an independent recomputation. The flag changes no conclusion:
every contrast is far below the 0.30 threshold either way.

**Pending [traces]:**
- completion per mode;
- spawn and parallel rates by class, regime and mode;
- mean agents;
- fitness per class, regime and mode;
- the manipulation check, recomputed independently of `build_report`;
- each fired criterion with its statistic;
- agreement with `summary.json`.

Reading rule: if the recomputation disagrees with the report beyond floating-point noise, that is a new defect, and
this diagnostic is superseded on that point.

## 3. Frozen P cells and oracle organizations

Read from `data/exp0b/frozen.json`, not hard-coded **[code]**; organization metrics are at the base point **[sim]**.
The P cells are exactly the four parallel-class urgent cells. Each best division is a fan-out that divides **at the
start**: the root's first action is SPAWN, and there is no SQL step. So it is also the best one-shot (router or
central) organization.

| cell | solo fitness | best division | fitness | children | expected agents | expected LLM calls | expected money | expected time | solo money / time |
|---|---|---|---|---|---|---|---|---|---|
| T01 urgent | 0.355 | fanout3 | 0.560 | 3 | 4 | 8 | $0.1603 | 131.3 s | $0.0667 / 343.4 s |
| T04 urgent | 0.335 | fanout4 | 0.548 | 4 | 5 | 10 | $0.1963 | 106.1 s | $0.0717 / 351.2 s |
| T07 urgent | 0.355 | fanout3 | 0.561 | 3 | 4 | 8 | $0.1597 | 131.1 s | $0.0667 / 343.4 s |
| T10 urgent | 0.335 | fanout4 | 0.550 | 4 | 5 | 10 | $0.1952 | 105.7 s | $0.0717 / 351.3 s |

Fitness by fan-out k, in `central` mode **[sim]**:

| cell | k = 1 | k = 2 | k = 3 | k = 4 | k = 5 | k = 6 | k = 7 | k = 8 |
|---|---|---|---|---|---|---|---|---|
| T01 urgent | 0.292 | 0.514 | **0.559** | 0.516 | 0.470 | 0.509 | | |
| T04 urgent | 0.272 | 0.502 | 0.527 | **0.548** | 0.501 | 0.457 | 0.412 | 0.431 |
| T07 urgent | 0.293 | 0.515 | **0.560** | 0.517 | 0.472 | 0.512 | | |
| T10 urgent | 0.272 | 0.503 | 0.529 | **0.550** | 0.503 | 0.461 | 0.416 | 0.436 |

k = 1 is worse than solo in every cell, by 0.062–0.064. **Every k ≥ 2 beats solo**, by 0.077 to 0.205.

## 4. Live organizational traces

**Pending [traces].** `traces.py` produces the full table for every P-cell run: 4 cells × 3 repeats × 4 modes. Its
columns are:
- the root's action sequence (e.g. `QUERY(6d0s) > TERMINATE`);
- every SPAWN attempt: children requested against created, known document ids named in each child objective, the
  allocation and lifetime requested against applied, and whether it was rejected, with the runtime's error;
- invalid actions;
- WAIT and MESSAGE counts;
- agents, parallel division, time, money and fitness;
- the root's first rationale.

It also produces an all-cell census (children per `central` SPAWN; SPAWN attempts by `developmental` and `router`) and
the live main run's token statistics.

What the code fixes regardless of the traces **[code]**:
- **`central`.** The only action allowed as the root's first valid action is SPAWN (`runtime.py:237`). The number of
  children is `len(action["children"])`, taken from the LLM's own list (`runtime.py:452`). The runtime overrides only
  each child's budget and lifetime (the fixed rule, `runtime.py:466`) and forces the wait (`runtime.py:482`). It never
  changes the number of children. With the fixed rule a SPAWN of up to 8 children is always affordable, and root + 8
  children fits the concurrency cap of 9 live agents (`runtime.py:455`). **A one-child `central` is therefore the
  LLM's choice, not imposed by code.**
- **`router`.** SPAWN is allowed as the root's first valid action only, once. Children cannot spawn.
- **`developmental`.** SPAWN is allowed at any step, including recursively.

Pre-declared readings of the traces:
- **central.** If B-urgent `central` requested one child in nearly all 12 runs, B is confirmed as the mechanism. That is
  the expected result, since the live mean matches k = 1 to within 0.001. If it requested ≥ 2 children but they were
  starved, rejected or ran sequentially, the mechanism is an implementation defect instead, and A rises.
- **developmental/router.** If any SPAWN was rejected for syntax, schema or affordability, A rises to high. If no SPAWN
  was ever attempted, A stays low.

## 5. SPAWN affordance audit

All fragments are quoted from the rendered 0b system prompt and schema **[code]**. The frozen prompt fingerprint
(53790f89…) recomputes from the code at 67c9d50, and `verify_frozen` reports no problems, so these are the prompts the
live run used. Every mode gets the same system
prompt except for one MODE RULES line, and the same six-action output schema (`action_schema(ALL_ACTIONS)`).

1. **Is the model told it may spawn multiple children?** Yes:
   `SPAWN {"children": [{"objective", "context", "budget_usd", "lifetime_s"}, ...], "wait_for_children"}: create 1 to 8 agents.`
2. **The exact structure** is one object with `"action": "SPAWN"` and a `"children"` array of k objects, each with
   `objective`, `context`, `budget_usd` and `lifetime_s` (all four required by the schema), plus
   `"wait_for_children": true|false`. One, three or four children differ only in the array's length.
3. **One SPAWN creates all the children** in its list. No repeated calls are needed.
4. **Repeated SPAWNs:**
   - `developmental`: any step ("You may SPAWN at any step; agents you create may also SPAWN").
   - `router`: "only as your first action, at most once".
   - `central`: "Your first action must be SPAWN". It happens once, because later SPAWNs are not allowed.
5. **Is the cost per child explicit?** Yes: "fee $0.0010 per agent plus $0.0020 per 1k tokens of objective+context
   copied to it", and
   "a newly created agent needs about $0.0224 for its first step". Each child "pays for its own steps from its budget".
6. **Is the latency benefit of parallel source processing explicit?** **No.** It is derivable, not stated:
   - "They [QUERY sources] are processed one after another";
   - "Different agents act concurrently";
   - each document's size and "latency 3s + 0.1s per document token" are listed;
   - the score charges "0.0011136 x (simulated seconds …) / 0.696".

   For T01, six region documents of about 530 tokens each take about 6 × 56 s ≈ 336 s in one QUERY. That costs about
   0.54 of the score, and spreading the reading across children would save most of it. The model has to do all of this
   arithmetic itself.
7. **Is the current time and resource budget explicit?** Yes. The brief gives the balance, the deadline and the value of
   time, and every status line gives the time, deadline, balance and "a step now needs a balance of at least".
8. **Can the model infer what runs concurrently?** Yes, by inference: sequential within an agent, concurrent across
   agents.
9. **Does the model know child QUERY processing overlaps in simulated time?** Only generically ("It runs concurrently
   with you"). Nothing says that document processing, the dominant latency, overlaps across agents.
10. **Is spawn, versus actual parallel processing, versus sequential delegation, distinguishable?** **Not explicitly.**
    Nothing warns that one child reading everything saves no time and adds overhead.
11. **Wording that makes SPAWN look risky or expensive?**
    - None that targets SPAWN.
    - The prompt does foreground per-decision costs: "The decision itself costs money and simulated time"; "Your entire
      conversation so far is re-read, and paid for, on every step".
    - A solo QUERY of all six documents is a single decision, whereas division takes more decisions.
    - The step-reserve paragraph warns that an under-funded agent is "suspended … otherwise terminated". That applies
      to children given too little budget.
    - These can make the solo path look cheap. The time cost that outweighs them sits in the catalog and must be
      computed.
12. **Is child allocation intuitive?**
    - `developmental`/`router`: the model picks `budget_usd`. It sees the first-step cost ($0.0224) and that "unused
      budget returns to you", so over-allocating is safe. What a child's whole job costs is not stated.
    - `central`: the budget is not the model's choice ("equal share of 50% of your balance (after fees) … the budget_usd
      and lifetime_s you write are ignored").

**Assessment.** The action is available, its syntax and multi-child form are explicit, and its costs are explicit. What
is *not* explicit is the one fact the parallel cells turn on: splitting document reads across agents cuts elapsed time
roughly by the number of agents. This is the pre-registered design, since the prompt "never suggests an organization"
(`prompts.py` docstring; SPEC §6). So it is not a defect of implementation. It does mean the treatment asks the model to
discover the parallel-time benefit from the latency formula, and the pilot measured a **median of 36 reasoning tokens
per step at effort `low`** **[reported pilot]**.

## 6. Central oracle/live mismatch

**Verified [code]:**

| where | how `central` is defined |
|---|---|
| **live** (SPEC §6; `runtime.py:237, 452, 466, 482`) | the root must SPAWN first; **the LLM chooses the children** (count, objectives and context); code fixes only allocation, lifetime and waiting |
| **calibration and criteria check** (SPEC §7.3; `analysis.py:249`) | "`central` always uses the best one-shot division", i.e. `router_div`, the oracle's best spawn-first organization (fanout3 or fanout4 in the B-urgent cells) |
| **realized manipulation check** (SPEC §8 (v); `analysis.py:validity`) | mean `central` fitness > mean `single` fitness over the B-urgent cells, computed from **live** `central` runs |

The answers to your questions:
- **Is it a substantive mismatch?** Yes. The check assumes `central` realizes a parallel division, but live `central`
  realizes whatever topology the LLM writes.
- **Was it in SPEC.md before 0b?** Yes. Both clauses are in 2851d2d, the first commit of Experiment 0; SPEC_0B carried
  them forward unchanged.
- **Does condition (v) implicitly assume live `central` approximates the oracle's one-shot organization?** Yes. It was
  meant to check that the designed trade-off *materializes* in live runs, but it measures the trade-off through an LLM's
  topology choice. It therefore tests the environment and `central`'s organizational competence together.
- **Could `central` pass B-urgent with one child?** No. k = 1 scores below `single` in every B-urgent cell (by
  0.062–0.064 at the base point), and the B-urgent mean stays below `single` at every one of the 18 grid points (by at
  least 0.051) **[sim]**. One child reads
  sequentially, exactly like `single`, and adds a spawn, a report, a wait and three more LLM steps.
- **What did the oracle expect?** fanout3 in T01/T07 urgent and fanout4 in T04/T10 urgent: 4–5 agents, about 106–131 s,
  fitness 0.548–0.561.
- **What did live `central` instantiate?** One child, two agents, almost everywhere **[reported]**. The live B-urgent
  mean is 0.2830 against the oracle's one-child mean of 0.2822. **[traces]** gives the per-run child counts.

**The size of the difference [sim].** The oracle's one-shot `central` beats `single` by +0.209 (0.554 against 0.345).
The one-child `central` loses by −0.063 (0.282 against 0.345). The live gap was −0.072 (0.2830 against 0.3552)
**[reported]**. The one-child organization accounts for almost all of it; the remaining ≈ −0.01 is live `single` doing
slightly better than the oracle's solo (0.3552 against 0.345).

## 7. Offline counterfactual

**Method [sim].** Each B-urgent cell was simulated in the **real modes** of the runtime: `single` with the oracle's solo
plan, and `central` with every fan-out k. The fixed allocation rule is applied by `central` mode itself. Everything
used the frozen 0b constants and the frozen pilot-measured assumptions (r = 2.0052, 36 reasoning tokens). The oracle
reasons perfectly and always answers correctly, so this isolates organization. It does not predict live quality.

| B-urgent mean fitness | value |
|---|---|
| `single`, oracle solo | 0.345 |
| `central`, one child | 0.282 |
| `central`, two children | 0.509 |
| `central`, the frozen one-shot organization (fanout3/fanout4) | **0.554** |
| live `single` **[reported]** | 0.3552 |
| live `central` **[reported]** | 0.2830 |

Across the 18-point grid (r × {0.75, 1, 1.25}, reasoning × {0.5, 1, 2}, extra WORK steps {0, 1}):
- the one-shot `central`'s B-urgent mean beats `single`'s at every point, by at least +0.059;
- the one-child `central`'s never does, and at best still trails by 0.051.

**Answer.** If `central` had instantiated the calibrated one-shot organization, the preregistered manipulation
**central > single on B-urgent would have held**, robustly. Any fan-out of two or more children would have been enough.

This is a counterfactual about the baseline's organization. It does not alter the 0b verdict.

**Live token assumptions** can be substituted where the logs are. `traces.py` prints the main run's measured r and
reasoning tokens, then run:

```
python analysis/exp0b_diagnostic/offline.py --input-scale R --reasoning-tokens N
```

## 8. Developmental/router non-spawn diagnosis

The information available at the moment of choice is the same for all modes except MODE RULES (§5) **[code]**.

| possible cause | assessment | evidence |
|---|---|---|
| 1. SPAWN unavailable | **no** | MODE RULES; the schema includes SPAWN with `children` in every mode **[code]** |
| 2. SPAWN syntax or interface unclear | **no evidence** | The syntax is shown explicitly. **[traces]**: if any rejected or invalid SPAWN attempts appear, this rises to yes. |
| 3. Multi-child SPAWN unclear | **unlikely** | "create 1 to 8 agents", with a list of children **[code]** |
| 4. Benefit of parallelism not visible | **partly** | Derivable, but never stated, and the difference between one child and many is never drawn (§5 Q6, Q9, Q10) **[code]** |
| 5. Resource economics not visible | **no** | Prices, score formula, value of time, balance and deadline are all shown **[code]** |
| 6. Task decomposability not visible | **no** | "Across the six regions …"; the catalog lists the six region reports with their token counts **[code]** |
| 7. A locally reasonable solo path, despite visible incentive | **possible, pending** | Solo is one QUERY decision and division is several. Only the rationales can show whether the time cost was weighed and rejected. |
| 8. Organizational/resource information ignored | **possible, pending** | Suggested by `central`: when forced to divide, it reportedly chose one child, a topology with no possible time benefit **[reported]**. Also the 36-token median reasoning budget **[reported pilot]**. |
| 9. Other | effort `low` | A pre-registered treatment setting, not a defect |

**Pre-declared reading of the traces** (the rationale keyword counts and first rationales in `traces.py`):
- rationales for the root's decisions that mention time, parallel work or agents, and then choose QUERY → cause 7,
  "considered and declined": C holds;
- rationales that never mention organization or time → causes 4 and 8, "not perceived": C holds, qualified by the
  benefit not being explicit;
- any rejected SPAWN → cause 2: A rises.

Nothing here infers motives from absent evidence. Causes 7 and 8 stay open until the rationales are read.

## 9. Pilot warning signs

The pilot ran `single` and `central` on X1–X3 **[code]**. **X2 has the same structure as T01**: "Across the six
regions, …", with six region documents to read. Its four `central` runs (two regimes × two repeats) were a direct early
test of B-urgent-style division.

At the pilot's own constants (Experiment 0: B = $1, V = $0.50) and the pilot's measured assumptions **[sim]**:

| X2 regime | `single` | `central` k = 1 | k = 2 | k = 3 | k = 4 | k = 5 | k = 6 |
|---|---|---|---|---|---|---|---|
| urgent | 0.317 | **0.235** | 0.439 | 0.466 | 0.405 | 0.342 | 0.363 |
| relaxed | 0.832 | 0.765 | 0.720 | 0.664 | 0.602 | 0.540 | 0.484 |

**Pending [traces]:** the children per pilot `central` run, whether any used more than one child, and single against
central mean fitness per pilot task and regime.

Pre-declared reading:
- if X2-urgent `central` used one child and scored below `single`, **the pilot already showed the failure mode**
  before the freeze;
- if it fanned out and beat `single`, the 0b behaviour is new, and this section's conclusion reverses.

**Should it have been caught?** The pilot's role in the protocol (SPEC §7.4) was to measure token physics: r,
reasoning tokens, p90 output, p95 time, accuracy and cost CV. Nothing examined realized organizations. The 0b proposal
and pre-registration (EXPERIMENT_0B_PROPOSAL.md, SPEC_0B.md) re-used the pilot for those statistics only, and neither
inspected `central`'s organizations. If the traces confirm one child on X2, the information was in hand before the
freeze. A check that realized baseline organizations match the calibration's assumptions would have caught it. In
hindsight that check should have been part of the protocol.

## 10. What the synthetic criteria check actually established

**The code [code].**
- `criteria_check` feeds synthetic run sets to `evaluate` only (`analysis.py:279`). It never calls `validity`.
- In those runs:
  - `single` is the oracle's solo;
  - `central` is `router_div`, the best one-shot division;
  - `router` is the better of solo and `router_div`;
  - developmental follows IDEAL, NEVER, ALWAYS, RANDOM, SPAWN-IFF-URGENT, SPAWN-IFF-MULTIDOC or WASTEFUL, each placed
    exactly at the organization's calibrated fitness.
- Noise is Bernoulli quality (accuracy 1.0 from the pilot) and a multiplicative cost CV of 0.25.

**What it established.** The **statistical power and specificity of the §8 evaluator**. With R = 3 and 200
simulations, IDEAL is judged supported in 85.5%, WASTEFUL in 0.5% (1 of 200), and every other policy in none
(`data/exp0b/frozen.json`, `criteria_check`). That holds *if* the live
runs reproduce the calibrated fitness of whatever organizations are chosen, and *if* the baselines behave as assumed.

**What it did not establish:**
- that an LLM policy would discover the right organization;
- that `central` or `router` realize their assumed organizations;
- that the validity conditions, including (v), would pass. Condition (v) was never simulated.

**Power only?** Yes: power and specificity of `evaluate`, conditional on idealized baselines and calibrated fitness.

**Did it assume away the hardest behavioural problem?**
- **For developmental, no.** Non-discovery is modelled as NEVER, which was judged supported in 0 of 200 simulations. The live developmental behaves like NEVER, so the evaluator was not the weak link.
- **For the baselines, yes.** It assumed `central` and `router` solve the organizational problem optimally. Condition
  (v) is computed from live `central`, so the one part of the pre-registration that depends on a baseline's
  organizational competence was never stress-tested.

## 11. Defect vs substantive failure assessment

| diagnosis | verdict | confidence | basis |
|---|---|---|---|
| **A. Clear interface defect** | not supported by the evidence so far | **low** | The action, its multi-child syntax and its costs are all explicit [code]. It rises to high only if the traces show rejected or malformed SPAWN attempts. |
| **B. Oracle/live baseline mismatch** | **true, and sufficient for the failed check** | **high** | Code and SPEC show it [code]; one-child central equals the live mean to within 0.001 [sim + reported]; the calibrated one-shot central passes (v) at all grid points [sim]. |
| **C. Substantive policy failure** | true in qualified form | **medium** | `developmental` and `router` never divided, with every action and all economics available [code + reported]. The benefit had to be inferred, and forced `central` chose a topology without a time benefit [reported]. The rationales decide between "declined" and "not perceived". |

**Overall: D, MIXED.** The failed check (the reason the run is UNINFORMATIVE) is explained by B. The absence of
division in the treatment is a separate observation, best described as C, qualified.

For context only, and **not as a verdict**: had (v) held, the criteria as reported would have fired, among others,
criterion 2 (never-spawn). So the live treatment behaviour would not have supported H. Experiment 0b remains
UNINFORMATIVE.

## 12. Whether a successor experiment is scientifically justified

1. **Is there a defensible reason?** Yes, narrowly. There is a concrete mismatch between the intended and the
   operationalized experiment:
   - SPEC §6 calls `central` a "fixed decomposition";
   - the calibration and power study (§7.3) model it as the best one-shot division;
   - the validity check (v) relies on it to show that division pays;
   - yet the live implementation lets the LLM choose `central`'s topology.

   As a result the manipulation check cannot distinguish "the trade-off did not materialize" from "the baseline LLM did
   not parallelize".
2. **What it must address:** the fixed-decomposition baseline, and the realized manipulation check built on it, must
   not depend on an LLM's topology choice. The pilot must also verify, before the freeze, that realized baseline
   organizations match the calibration's assumptions.
3. **What would change:**
   - **the baseline definition**, and with it the operationalization of validity (v);
   - **instrumentation**: a pilot gate on realized organizations;
   - **not** the developmental policy prompt;
   - **not** the scientific hypothesis.
4. **Would it test the same core hypothesis?** Yes. H compares local, resource-aware division against `single` and
   against a fixed decomposition.
5. **Would repeating after a fix be tuning?**
   - **Fixing the baseline is not tuning towards support.** 0b already shows the developmental treatment never
     dividing, so a valid successor with an unchanged treatment would most likely yield NOT SUPPORTED. The fix makes a
     negative result *possible*. A successor must say in its pre-registration that this outcome is anticipated from 0b.
   - **Changing the developmental prompt, effort level or schema to elicit spawning would be tuning after observing
     failure.** Examples: stating the parallel-time benefit, raising the effort, or suggesting organizations. That
     would be a **different hypothesis** (for example, "given explicit parallelism information, …"), and it must be
     pre-registered as such, not as a repair.

**The single most important change before any successor:** make the fixed-decomposition baseline fixed by
construction, so that the realized manipulation check tests the environment's designed trade-off, not the baseline
LLM's choice of topology. Then check realized organizations in the pilot before freezing.

## 13. Limitations

- **Live logs not read here.** Steps 1, 3, 7 (the rationales) and 8 rest on the reported numbers until `traces.py` runs.
  The pre-declared readings in §2, §4, §8 and §9 state how each outcome would change the conclusions.
- **The oracle is idealized.** It reasons perfectly and answers correctly, so it isolates organization and does not
  predict live quality. Live `single` (0.3552) and the oracle's solo (0.345) are close, which supports using the oracle
  for organization.
- **Rationales are short** at effort `low` (a median of 36 reasoning tokens per step in the pilot). Absence of an
  organizational rationale is weak evidence, and no motive is inferred from it.
- **The reported twin and dissociation values** are arithmetically inconsistent with the reported rates (§2). The
  traces resolve this.
- **Author's accountability.** The 0b proposal and pre-registration (written in this repository's working sessions)
  reused the pilot without inspecting `central`'s realized organizations, and did not flag the §6/§7.3 mismatch. That
  was a missed check, not a hidden change: both texts were public in SPEC.md from the first commit.
- **Scope.** Nothing here changes Experiment 0b. Its record stands: **UNINFORMATIVE because the preregistered realized
  manipulation check failed.**
