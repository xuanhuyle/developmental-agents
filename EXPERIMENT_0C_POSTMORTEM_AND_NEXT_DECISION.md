# Experiment 0c: postmortem and next decision

**Status: decision memo.** It contains no implementation and no pre-registration; no API was called and no live run
was made. Experiment 0b stays UNINFORMATIVE, and Experiment 0c's result stays as recorded: X2 pilot PASS, Stage 1
NO-GO, not a full SPEC §8 verdict. This memo was revised after two independent adversarial reviews (a fact check and
a design review); their substantive findings are incorporated.

**Evidence tags.**
- **[repo]** means committed files.
- **[reported]** means the experimenter's local result directories (`results/exp0b/main`, `results/exp0c/pilot`,
  `results/exp0c/stage1`), as summarized in EXPERIMENT_STATUS.md. The directories themselves are not in the
  repository.
- **[offline]** means deterministic, LLM-free simulation in the real runtime at the 0b constants, using
  `analysis/exp0b_diagnostic/offline.py` and the calibration code. It inherits the simulator's declared assumptions.

**Naming.** In this memo, paths A–E are the five candidates of the postmortem brief. They are not the options of
EXPERIMENT_0C_DECISION.md. That memo's "option E", one legibility experiment, is **path B** here.

## 1. Executive conclusion

**The primitive mechanism line, as tested, is closed.** That mechanism was one generic LLM action policy with
metered primitives, a neutral representation, effort `low`, and organization left implicit.
- It never spawned in 192 voluntary opportunities: 0b `developmental` 90 and `router` 90, plus 0c `developmental` 12.
- 36 of those were in the four P cells, where dividing was validated live to be worth about +0.20 fitness (as a
  four-cell mean).
- When forced to spawn, it delegated rather than divided.

**What this does not settle.** It does not answer the research question. Nothing tested so far gave organization any
reason to change after execution began, and the simulator does not yet contain a cell that rewards doing so.

**Recommendation: path E, in a strict order, with a stop pre-committed at every gate.**
1. **Gate 0, offline (zero API calls).** Build and calibrate information-dependent cells, and the dissociation states
   the probe needs. If Gate 0 fails, the program stops: no API call is made.
2. **Probe stage A, at most 40 single-decision calls.** Only the most-assisted arm is run. It tests a *necessary
   condition*: that the model, at a decision point, can make organizational choices that track their economic value.
   If it fails, stop.
3. **Probe stage B, at most 60 calls,** only if A passes. It finds the least-assisted arm that still passes.
4. **At most one follow-up,** a test of O(t) on held-out Gate-0 cells, with at most 400 runs. If it fails, stop.

**The probe is a static gate, not a test of development.** The north-star property, organization as a trajectory that
responds to what is discovered, is tested only by the follow-up.

## 2. Verified evidence from 0b and 0c

| fact | value | source |
|---|---|---|
| 0b verdict | UNINFORMATIVE: the realized manipulation check (v) failed, B-urgent `central` 0.2830 against `single` 0.3552 | [repo] EXPERIMENT_STATUS.md, from [reported] |
| 0b behaviour | `developmental` and `router`: 0 SPAWN attempts in 90 runs each. LLM-chosen `central`: exactly one child in every main and pilot run; in the P cells, that child read all 6 or 8 documents | [repo] status and EXPERIMENT_0C_DECISION.md, from [reported] |
| 0c pre-registration | `data/exp0c/prereg.json`, LF sha `75e478ca…`. The pilot record (commit 1797759) cites that same sha | [repo] |
| 0c pilot (X2) | 4/4 completed, PASS. `central` 0.5661 against `single` 0.3667. 3 children in parallel, quality 1, about 344 s → about 133 s | [reported]; record [repo] |
| 0c Stage 1 | 36/36 completed, every gate passed. `central` 0.5583 against `single` 0.3552. `central` parallel in 12/12 runs | [reported] |
| 0c `developmental` | parallel 0/12, SPAWN 0/12. Criterion 2 fired; **NO-GO**; not a §8 verdict; no Stage 2 | [reported] |
| Prediction vs observation | predicted (live tokens): `single` 0.343, `central` 0.549. Observed: 0.355 and 0.558, consistent with the calibration | predictions [repo] SPEC_0C §5; observations [reported] |
| Behavioural caveat | A few scripted children did not read every assigned document. This counts as behaviour, not as an infrastructure failure | [reported] |
| What the neutral prompt states | The scoring formula, document latency (3 s plus 0.1 s per token), document sizes, "processed one after another" within a QUERY, and generically "different agents act concurrently". It never says that document processing overlaps across agents, and never states consequences: the model must infer and compute them | [repo] `prompts.py`, `sources.py`; EXPERIMENT_0B_DIAGNOSTIC.md §5, items 8–10 |
| Rationales | The only quoted rationale is about batching ("Read all six region reports in one query."). The rationale census was never reported | [repo] EXPERIMENT_0C_DECISION.md |
| Cell structure | Every urgent cell that needs ≥ 2 documents is P or ambiguous. No cell is urgent, needs several documents, and still favours working alone. T09/T12/T15 urgent are `ambiguous`, and I = 0 | [repo] frozen.json |
| Deliberation and division are substitutes in this simulator | Fan-out minus solo as reasoning tokens per step grow, for **every** agent (45 / 500 / 800 / 1000): T01 urgent +0.20 / +0.09 / +0.02 / −0.03; T04 urgent +0.21 / +0.07 / −0.01 / −0.07 | [offline], under the declared output latency of 0.02 s per token |

**Not in the repository:** the 0c event logs and the sha of `stage1_decision.json`. Also, SPEC_0C §10's pre-declared
wording, "does not reliably instantiate", is accurate but understates 0/12: the treatment did not instantiate
division in any run.

## 3. What we have learned

- **A. Parallel division pays here: established.** A t0 fan-out executed by live LLM agents beats `single` by about
  0.2, as predicted. This is the designed manipulation (a declared latency of 0.1 s per document token), not a fact
  about the world.
- **B. The runtime executes the multi-child organization: established, narrowly.** It did so at one level, for a
  *scripted* division made at t0, under the fixed allocation rule. No LLM decision has yet chosen a division, its
  allocation, a mid-run SPAWN or a recursion. Whether LLM-chosen topologies would execute as calibrated is unknown.
- **C. The unchanged policy does not choose advantageous division under this representation, model and effort:
  established, with strong negative evidence** (0/12 in 0c; 0/24 in the same P cells in 0b).
- **C′. When forced to spawn, the model delegates rather than divides.** In 0b's P cells, one child read all the
  documents. So the model can emit SPAWN, but it did not generate a topology that saves time.
- **D. "LLMs cannot make useful organizational decisions": not established.** The evidence covers one model, one
  effort level (about 45 reasoning tokens per step) and one representation. Division paid in only two P-cell
  templates; 0b's zero-SPAWN result covered all 15 tasks.
- **E. "Adaptive organization is not viable": not established.** No adaptive organization was ever run, and the
  environment contains no cell that rewards adapting.
- **F. "Poor salience caused the failure": not established.** It is a causal hypothesis. What was missing was not
  facts but one inference (that document processing overlaps across agents is stated only generically) and the
  computation of consequences. Effort and model are confounded with it, and none was varied.
- **G. "Restructuring after new information has been tested": false.** It was never tested.
- **H. Within this simulator, deliberation competes with division.** Suppose every agent spent about 800–1000
  reasoning tokens on every step. Then division would no longer pay.
  - This follows from the declared output latency (an assumption, not a measurement), not from any observation.
  - How many tokens a higher effort setting actually produces was not measured.
  - Two practical consequences follow. "Raise effort everywhere" is not a clean repair. And any deliberation a
    mechanism adds must be charged, and scored net of its own cost.
- **I. The simulator's P structure is too easy.** "Spawn iff urgent and ≥ 2 documents are needed" is economically
  correct in every current cell. So any positive result on the current cells cannot separate economic reasoning from
  that simple rule.

## 4. What remains unknown

1. **Where the bottleneck is.** Possibilities:
   - **generation:** the model never considers dividing the work at all, since it reads SPAWN as "hand off";
   - **evaluation:** it considers division but cannot compute the consequence;
   - **deliberation:** it could compute it, but does not at about 45 reasoning tokens;
   - **presentation:** it would act if the overlap were stated and the consequence precomputed;
   - **disposition:** it computes the consequence and still works alone;
   - **demand:** it divides wherever organization is made salient, whether or not that pays.

   0b and 0c cannot separate these.
2. **Whether the model's organizational choice responds to information revealed after t0.** No division ever
   occurred, so there was nothing to change.
3. **Whether this simulator can host the research question.** That would need two kinds of cell, and neither exists
   yet:
   - robust cells where adapting after new information beats both the best organization fixed at t0 and the best fixed
     generic workflow;
   - urgent multi-document cells where division does not pay.
4. **Whether a general mechanism can produce task- and state-dependent organization without becoming orchestration in
   disguise** (§6.0).

## 5. Strongest skeptical interpretation

**S0: a fixed default that ignores time.**
- At low effort, the frozen model follows one default plan in every state: "read every named source myself in one
  batched action, then answer".
- It never computes the score's time term. That would mean taking 3 s plus 0.1 s per token for each document, summing,
  inferring that other agents' reading overlaps, and converting at value of time ÷ V, about 0.0016 score per second in
  urgent cells.
- It reads SPAWN as "hand off", not as "run concurrently".

S0 explains every observation:
- the behaviour is identical across a 16-fold change in the value of time;
- forced `central` uses one child, which is the cheapest legal SPAWN;
- the one quoted rationale is about batching;
- the scripted fan-out executes as calibrated.

**S0′: the strong skeptic.**
- Any adaptation that appears later will come from what the representation or harness spells out. That is
  architecture designed by a human one layer up, or a reaction to salience.
- The only benefit division buys here, reading documents concurrently, is what a conventional harness gets from
  parallel tool calls. It needs no organizational reasoning, and a one-line rule (§3 I) captures it.

**What would most efficiently distinguish S0/S0′ from the thesis:**
1. The strongest legitimate elicitation at a decision point, with a check that separates generation from evaluation
   (§9).
2. Dissociation states in which the one-line rule is wrong.
3. Later, require any mechanism to beat a **no-LLM controller that runs the mechanism's own rule**. Where the LLM adds
   nothing beyond the rule, S0′ wins.

## 6. Candidate next paths

### 6.0 The machinery question

**The criterion is not how much machinery.** Biological development is not mechanism-free: cells have regulatory
machinery, which was *selected over a distribution of environments*, not fitted to one instance. The useful criterion
asks two things:
- where task-specific information enters the causal path that produces the topology;
- whether the mechanism was fixed independently of the tasks it is evaluated on.

**Permitted (general, local, task-agnostic):**
- lifecycle primitives;
- resource and time sensors;
- feedback on realized costs;
- an organizational registry;
- event-triggered reconsideration at general events (t0, when information arrives, when a child terminates), never at
  moments an experimenter selects as "organizational";
- charged deliberation at those events;
- the scoring rule;
- consequence text generated by code from the environment's constants.

**Grey zone:** an evaluator that prices only candidates the agent itself proposes. If used, credit for the
organization goes to the evaluator and must be reported that way.

**Orchestration (not permitted):**
- topology templates, the number of children k, or partitions;
- rules keyed on task class or surface features;
- an optimizer that enumerates organizations and returns the best one;
- tuning on the test families.

**Operational tests of endogeneity,** pre-registered for any mechanism:
1. **Pre-commitment:** the mechanism is hashed before any held-out output.
2. **Text audit:** it contains no task vocabulary, counts or topology words.
3. **Non-predictability:** surface features (template, number of documents) predict the topology worse than the
   economic label does, on twin, shortcut and dissociation cells.
4. **Specificity:** spawned_rate(S) ≤ 0.2, including cells whose surface suggests dividing.
5. **Adaptation after t0:** on cell pairs identical up to a reveal, the organization diverges in the economically
   correct direction, and it beats the best one-shot organization that has the same t0 information.
6. **Causal ablation:** hiding the sensed state, or the trigger, changes O(t).
7. **Added value of the LLM:** the LLM beats a **no-LLM controller** running the mechanism's own rule, plus the
   heuristics SPAWN-IFF-URGENT, SPAWN-IFF-MULTIDOC and the best fixed workflow.

**If any test fails,** the organization is orchestration in disguise, whatever its machinery looks like. Development
here means regulative development: the system compensates for what it senses. It does not mean executing a template.

### 6.1 The paths

**A. Stop the research line now.**
- **Hypothesis:** the line is exhausted.
- **Measurement:** none. The outcome is fixed.
- **What it leaves open:** the null covers one effort level and one presentation. Whether it reflects generation,
  evaluation, deliberation or disposition stays unknown.
- **Decision:** a strong default, and the pre-committed outcome of every gate's failure (§10). It is not chosen now,
  only because Gate 0 is free and could show it is right without spending anything.

**B. One legibility experiment, as full runs** (the old "option E"). It would state the overlap explicitly, and
precompute per-document seconds and score per second.
- **Controls:** the treatment unchanged, scripted `central`, `single`, the relaxed twins, and the urgent shortcut
  cells (D_urgent).
- **Primary measurement:** parallel_rate(P), spawned_rate(S), and the twin and dissociation contrasts.
- **Supporting observation:** P ≥ 0.5 with contrasts ≥ 0.30.
- **Contradicting observation:** no division, or division everywhere.
- **Alternative explanation:** compliance, or reading out precomputed arithmetic. On the current cells, even a pass
  cannot be told apart from the one-line rule (§3 I).
- **Cost:** about 24 runs (100–150 calls) in a minimal P + twins version, about 75 runs in a complete one. It touches
  nothing after t0.
- **Decision:** dominated by probe stage A. Stage A tests the same factor and adds deliberation, and an emitted SPAWN
  is scored by replay. It includes a dissociation state, and costs at most 40 calls.

**C. An information-dependent environment now, with the policy unchanged.**
- **Hypothesis:** the policy reorganizes after a reveal better than a router limited to t0 information.
- **Controls:** `single`, a fixed architecture, a scripted one-shot t0 router, the best fixed workflow, an adaptive
  oracle.
- **Supporting observation:** the organization diverges after the reveal and beats the router.
- **Contradicting observation:** a floor.
- **Alternative explanation:** a floor cannot separate "insensitive to information" from "never divides", and the
  second is already known.
- **Estimated outcome:** a floor, with probability about 0.9.
- **Decision:** no live runs now. Its environment is exactly Gate 0, which goes first and is offline.

**D. An explicit, general organizational mechanism, built now.** It would add a registry, sensors, event-triggered
checkpoints, charged deliberation and more lifecycle primitives.
- **Hypothesis:** general machinery plus an LLM produces an O(t) that passes §6.0.
- **Controls:** an ablation ladder, the no-LLM controller, the heuristics, the t0 router, the oracle.
- **Supporting observation:** the full mechanism beats its ablations and the no-LLM controller on held-out I cells,
  with specificity.
- **Contradicting observation:** no gain, spawning everywhere, or topology predictable from surface features.
- **Alternative explanation:** the machinery is the real optimizer.
- **Cost:** 400–800 calls, whatever the outcome.
- **Decision:** premature. A null would not say which component failed. In the most likely world, the one where
  stage A fails, D would spend 10–20 times stage A's calls to reach the same stop. It is retained as the single
  follow-up.

**E. Gate 0, then a staged decision-point probe (recommended; §8–§9).**
- **Hypothesis:** at a decision point, under the strongest legitimate elicitation, the model makes organizational
  choices that track their economic value, and not surface features.
- **Intervention:** single API calls at reconstructed decision states. Every emitted SPAWN is scored by offline
  replay. A check separates generation from evaluation.
- **Supporting observation:** replay-validated division where it pays, and no spawn where it does not, including the
  dissociation state.
- **Contradicting observation:** no division, or division that also fires where it does not pay.
- **Alternative explanation:** a single decision is not a run. Replay with scripted children approximates execution.
  0c validated only the scripted fan-out, and live children sometimes skipped assigned documents. This is declared.
- **Decision:** every outcome of each gate is pre-assigned (§9). Each failure is a stop.

## 7. Comparison of information value

All probabilities are subjective estimates by the review lenses, not measurements.
- P(Gate 0 passes) ≈ 0.5.
- P(stage A passes | Gate 0) ≈ 0.25.
- P(follow-up passes | A) ≈ 0.3.

| path | engineering | live calls | likely outcomes | what each outcome changes | relevance to the north star |
|---|---|---|---|---|---|
| A stop | 0 | 0 | — | nothing new; the bottleneck stays unknown | none (an end point) |
| B legibility, full runs | 3–5 days | 100–450 | none 0.6 / discriminating 0.25 / indiscriminate 0.15 | one factor; a pass is confounded with the one-line rule | low (t0 only) |
| C info-dependent now | 6–10 days | 800–1500 | floor about 0.9 | almost nothing; the floor is already known | high in form, nil in practice |
| D mechanism now | 3–6 days | 400–800 | null 0.5 / works 0.35 / indiscriminate 0.15 | a null cannot say which component failed | medium to high |
| **E staged** | offline Gate 0, then 1–2 days | **A ≤ 40; B ≤ 60 if A passes; follow-up ≤ 400 runs (at least about 1,600 calls; computed in Gate 0) if A passes** | stop at Gate 0 ≈ 0.5; stop at A ≈ 0.375; follow-up ≈ 0.125 | Gate 0 and stage A each stop or license the next step; stage B only selects | low for the probe (static); high for the follow-up |

**Expected live calls for E:** about 0.5 × 40 + 0.125 × (60 + 1,800), roughly 250 or more. In 7 of 8 worlds E stops after at
most 40 calls, with a labelled reason.

**Why E dominates:**
- Its first step is free and can end the program honestly.
- Its first live step is the cheapest one able to stop the program, and it stops it with a stated reason.
- It spends follow-up-scale money only after a necessary condition has passed.
- No cheaper live step could either license the follow-up or stop the program with a stated reason.

## 8. Recommendation

**Path E, run in order: Gate 0, then probe stage A, then stage B, then at most one follow-up.**
- **Maximum live budget for the next step: 40 single-decision API calls, retries included.** These are stage A's
  calls, with **0 agent runs**.
- **Stage B is at most 60 further calls,** only after A passes. With a 16k-token output cap on high-effort calls, the
  100 calls together cost at most about $40 at the declared prices.
- **The follow-up is at most 400 runs,** only after A passes and Gate 0 has passed.

**Gate 0 (offline, zero API calls; it may be built now, and must pass before any call).**
- **Templates.** At least 2 information-dependent task templates, motivated by work in which needs are discovered
  along the way. For example, a cheap triage reveals which subproblems matter and how much parallel or specialist work
  each needs.
- **Reveal pairs.** Pairs of cells identical up to the reveal: same question, same catalog, same t0 state, same number
  of follow-up sources. Only the revealed content differs, and it flips the optimal organization.
- **Margin.** The adaptive oracle beats both the best t0 organization and the best fixed generic workflow ("triage,
  then fan out over everything plausible") by ≥ δ = 0.03 at every grid point, in at least 4 cells.
- **Controls.** The set must include:
  - **urgent multi-document cells where division does not pay.** One of them is the probe's state D: a twin of
    T01 or T04 with the same template and question form, whose documents are short enough that spawn overhead exceeds
    the time saved;
  - S-type controls;
  - an opportunity to redirect or dissolve work: a branch revealed as dead while children are alive.
- **A new primitive.** The runtime has no parent-initiated stop; children end only by their own TERMINATE or their
  lifetime. If dissolution needs such a stop, it is added as a general lifecycle primitive and frozen within Gate 0.
- **Rounds.** The grid, δ and the acceptance criteria are hashed before any template is designed. Every oracle
  evaluation is logged append-only, and each logged evaluation of a template set counts as one round. At most 2
  rounds.
- **Follow-up feasibility.** Gate 0 also computes, offline, the follow-up's calls per run and its power. Calls per run
  include high-effort checkpoints and up to 8 children. Power is for every pass criterion in §9, at the number of
  arms, cells and repeats that 400 runs allow. If power is below 0.8, Gate 0 fails.
- **Failure.** If Gate 0 fails, the program stops, and no API call is made.

**Prior commitments, and the deviations declared from them.** EXPERIMENT_0C_DECISION.md §7 allows at most one
option-E (legibility) experiment on these cells, in full-run form with a scripted-`central` check, and its stop
rule fires on criterion 2.
- **Where this plan relaxes that commitment** (declared):
  - single decision calls instead of full runs;
  - effort added as a factor, which that memo classed as a separate treatment change;
  - three arms of which the least-assisted passing one is chosen;
  - presentation text written after 0c output, though generated by code from the constants.
- **Where it tightens it:**
  - indiscriminate spawning is a stop;
  - effort and model are closed as rescue knobs;
  - a free gate comes first, including the follow-up's power;
  - one follow-up at most.
- **The wording allowance.** The probe's single presentation generator consumes it. No full-run legibility
  experiment follows a probe failure.

## 9. Falsifiable design sketch: the staged probe

This is a sketch to pre-register later, not a pre-registration. It runs only after Gate 0 passes.

**Unit.** One API call at a reconstructed decision state. Each state is built by the existing harness with the frozen
0b constants and the `developmental` MODE RULES. Nothing executes afterwards.

**Offline check before any call:** every reconstructed t0 request must be byte-identical to the corresponding logged
0b/0c first request. On a mismatch, fix the reconstruction only. This replaces a live anchor: 0/192 already is the
anchor.

**States (6), all at t0:**
- **P:** T01 urgent and T04 urgent.
- **S:** T01 relaxed and T04 relaxed (twins: identical text, lower value of time), and T06 urgent (a shortcut: same
  template, one SQL suffices).
- **D:** the urgent twin of T01 or T04 with short documents, from Gate 0. Division does not pay there, so the one-line
  rule (§3 I) is wrong; only the economics differs from P. It is never reused as a held-out follow-up cell.

**Arms:**
- **Effort:** `low` (frozen), or `high` at the t0 decision only. That is a general event, not one chosen for being
  organizational. The raised output cap is declared, and truncation is reported.
- **Presentation:** neutral (frozen), or **factual**. The factual text is generated by code from the constants:
  per-source seconds and score per second, plus one fixed sentence saying that document processing by different
  agents overlaps in time. It is hashed at pre-registration, applies unchanged to any cell, and names no plan, agent
  count or organization-level time. A lint rejects advice words and organization-level numbers.
- **Stage A** runs only (factual, high), the most-assisted arm.
- **Stage B** runs (neutral, high) and (factual, low).
- **Monotonicity is assumed and declared:** if the most-assisted arm fails, the less-assisted ones are presumed to
  fail too.

**Generation check (stage A only).** In the stage-A arm, at T01 urgent and T04 urgent, the model is
asked to list the plans it would consider and estimate each one's elapsed seconds and score. It is not told any plan.
Its answers are scored against a key computed offline: does a time-saving division appear, and is it ranked
correctly?
- **Generation:** a time-saving division appears in fewer than 3 of the 6 P-state answers.
- **Disposition:** it appears in at least 3, and is ranked above solo in at least half of those.
- **Evaluation:** otherwise.

**Samples:**
- stage A: n = 5 at each P state (10), n = 4 at each S state (12) and n = 6 at D, which is 28 calls. Add 2 × 3
  generation calls, for 34. The cap is **40**.
- stage B: 2 arms × 28, for 56. The cap is **60**.

**Readouts.**
- **Divide:** a SPAWN with ≥ 2 children whose offline replay beats the replay of solo by ≥ 0.03.
  - The replay runs scripted children over the documents their objectives name, with the emitted budgets and
    lifetimes.
  - **Both replays charge the same probed decision's actual tokens.** The decision's cost is sunk at that point, so
    this scores the choice, not the deliberation.
  - An objective that names no document does not count.
- **Deliberation cost** is reported separately, not gated. That is the fraction of decisions whose own tokens exceed
  the break-even against low-effort solo: about 2,800 output tokens at the declared prices and latency. It bounds the
  follow-up mechanism, which is scored net of all deliberation.
- **Spawn:** any SPAWN.
- **An arm passes** iff all three hold:
  - it divides in ≥ 5 of 10 P samples;
  - it spawns in ≤ 2 of 12 S samples;
  - it spawns in ≤ 1 of 6 D samples.
- **Power.**
  - An arm that truly divides at 0.7, with spurious spawns at 0.05, passes with probability 0.90.
  - At 0.5 and 0.1, it passes with probability 0.49. A weak true effect is likely to be stopped, by design.
  - A follower of the one-line rule (dividing at P 90%, never spawning at S) passes with probability 0.005 if it spawns
    at D 75% of the time, and 0.11 at 50%.
  - An arm that spawns uniformly at random passes with probability ≤ 0.017, and ≤ 0.05 for any of three arms.

**Decision tree, pre-declared, evaluated in order:**

| gate | outcome | reading | decision |
|---|---|---|---|
| A | (factual, high) passes | a necessary condition holds under the strongest legitimate elicitation | run stage B |
| A | it divides in ≥ 5/10 P, but fails the S or the D limit | division follows salience, demand or the one-line rule, not value | **STOP** (label: indiscriminate) |
| A | it divides in < 5/10 P; generation shows no time-saving division | the model does not generate division (S0) | **STOP** (label: generation) |
| A | the same, but division is generated and ranked correctly | it knows and does not act | **STOP** (label: disposition) |
| A | the same, but division is generated and misranked | it cannot evaluate the mechanics | **STOP** (label: evaluation) |
| B | the least-assisted passing arm is chosen in the order (neutral, high), then (factual, low), then (factual, high) | it defines the one follow-up mechanism; stage B selects and cannot stop | follow-up |

**The one follow-up,** licensed by stage A and stage B together:
- **What is tested:** one frozen, general mechanism embodying the chosen arm. Deliberation becomes charged checkpoints
  triggered at general events (t0, each new information arrival, each child termination). Presentation becomes the
  code-generated text as a fixed environment feature, with claims stated as "given computed consequences". If only
  (factual, high) passes, the mechanism has both components.
- **Where:** on Gate-0 cells held out from mechanism development.
- **Controls:** `single`, the best fixed t0 architecture (scripted), a one-shot router restricted to t0 information
  (scripted), the best fixed workflow, the no-LLM controller, and the adaptive oracle.
- **Pass criteria:**
  - all the endogeneity tests of §6.0;
  - an adaptation contrast ≥ 0.30 on the reveal pairs;
  - on information-dependent cells, fitness above both the router and the fixed workflow, with a bootstrap CI lower
    bound > 0.
- **Budget:** ≤ 400 runs. The size and power were fixed in Gate 0.

**What the probe cannot establish:** trajectories, adaptation, aggregation or dissolution; realized fitness; any
verdict on H; motive. A passing stage A is a necessary condition, not evidence for the thesis.

## 10. Explicit stopping rule

This is committed before any further live output.

1. **The primitive line is closed** (neutral presentation, effort low, organization implicit). No edit to the prompt,
   effort or model on these cells reopens it.
2. **Gate 0 fails → the program stops,** with zero API calls.
3. **Stage A fails → the program stops** for the current model generation. The failure is labelled per §9.
4. **One follow-up at most.** It tests one mechanism, chosen by stage B, with at most 400 runs. If it fails, the
   program stops for the current model generation.
5. **No rescue knobs.**
   - No second presentation generator, no examples, no further planner or controller variants, no other model, no
     other effort setting, and no changed economics, cells or thresholds after any failure.
   - **Asymmetry rule:** new variants are allowed only to test whether a *success* generalizes.
6. **Tripwire, the only exception, and it is report-only.** A stop "for the current model generation" is permanent
   for this program, unless a tripwire positive is followed by a new decision memo.
   - When the provider releases a new major model version, the frozen 0c Stage 1 may be re-run unchanged, once.
   - A negative changes nothing.
   - A positive (parallel_rate(P) ≥ 0.5, with spawned_rate(S) ≤ 0.2 on a pre-declared S set) permits only a new decision
     memo. It does not reopen the probe or the follow-up automatically.
7. **No testbed switch belongs to this program.** A different testbed would be a new proposal with its own
   justification, not a continuation.
8. **Total remaining live budget before a final conclusion:**
   - 40 calls if stage A fails;
   - 100 calls if it passes;
   - plus at most 400 runs in one follow-up.

**The direct answer: what result should end this formulation.** Any one of three:
- **Gate 0 fails.** This simulator cannot express cells where adapting after new information beats the best t0
  organization and the best fixed workflow.
- **Stage A fails.** Under the strongest legitimate elicitation, with the overlap stated, consequences precomputed,
  and deliberation at the decision, the model still does one of the following:
  - it does not choose replay-validated division where division pays;
  - it divides where division does not pay, including the state that defeats the one-line rule.
- **The follow-up fails.** The one general mechanism does not beat, on held-out reveal pairs, the strongest
  architecture selectable at t0, the best fixed workflow, and its own no-LLM controller.

**Documents this rule supersedes:**
- EXPERIMENT_0C_DECISION.md §7. Its rule fired only on criterion 2 and left effort and model open. This rule relaxes it
  in the ways declared in §8, and tightens it as stated there.
- The pre-0b "Recommended next experiment" in EXPERIMENT_STATUS.md. That section stays as written, because the log is
  append-only.

## 11. Relationship to the overall research objective

**The research question is unanswered,** and 0c was never able to answer it. What 0b and 0c measured was a static t0
choice, using one lever (concurrent reading under a declared latency). A conventional harness solves that with
parallel tool calls, and a one-line rule captures it. A positive result would have been weak evidence for the thesis.
The negative result is strong evidence against one weak formulation of it.

**Development means organization as a trajectory, O(t),** that changes because of what is discovered. It spawns when
a discovery opens independent work, and redirects or dissolves when a branch dies.
- **The probe does not test this.** It tests only a necessary condition: whether organizational choices at a decision
  point track their value.
- **The follow-up tests it,** on Gate-0 reveal pairs.
- **Gate 0 comes first** because without such cells the question cannot be asked in this simulator.

**Sanity check against the motivating use** (an AI-native forward-deployed engineer). What matters there is
discovering which subproblems, expertise and bottlenecks exist, and creating and dissolving specialists as they
appear. Concurrent reading is the easy part of that job. For that reason Gate 0's templates are chosen for discovery,
and the follow-up must beat the best fixed workflow a team would actually ship.

**A testbed-bound lesson from H.** Under these constants, deliberation is itself a resource to be allocated. If that
holds more widely, a system that organizes itself must decide where to think as well as how many agents to run.
