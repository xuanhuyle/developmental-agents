# SPEC 0c — Experiment 0c: scripted-central instrument pilot and narrow Stage 1

**Status: pre-registration.** This document, the code that implements it and `data/exp0c/prereg.json` are committed
**before any Experiment 0c live output exists**.

- **Both stages are fixed now.** The held-out X2 instrument pilot (4 runs) and Stage 1 (36 runs) are specified in full
  here.
- **The pilot cannot change the design.** It decides only whether Stage 1 *executes*, never what Stage 1 *is*.
- **The source decision.** [`EXPERIMENT_0C_DECISION.md`](EXPERIMENT_0C_DECISION.md) (931a7c1), option B, was accepted
  as the design.
- **What applies otherwise.** [`SPEC.md`](SPEC.md) and [`SPEC_0B.md`](SPEC_0B.md) apply wherever this document does
  not say otherwise.

## 0. Scientific boundary

Experiment 0b is permanently recorded as **UNINFORMATIVE because the preregistered realized manipulation check
failed** (EXPERIMENT_STATUS.md, 2026-09-30 entry). Experiment 0c does not reinterpret it, does not change its verdict,
does not pool its data, and does not alter its frozen artefact.

These confirmed 0b facts motivate 0c:
- **Completion.** 360/360 main runs completed, with 0 infrastructure failures.
- **The failed check.** On B-urgent, `central` scored 0.2830 against 0.3552 for `single`.
- **`central`'s topology.** `central` created exactly one child in every main run and every pilot run. No pilot or 0b
  run ever had two or more children.
- **No division.** `developmental` and `router` made zero SPAWN attempts across their 90 main runs each.
- **The explanation.** Offline, at the live token statistics, one-child `central` scores 0.279, `single` 0.343 and the
  calibrated fan-out 0.548. The failed check is explained by the live one-child topology.

## 1. Question

Experiment 0c answers one narrow question in two stages.
- **Stage 0.** Does a scripted multi-child `central` instrument work? It has an offline part, the implementation
  validation (§5), and a live part, the X2 instrument pilot (§6).
- **Stage 1.** Under a live-validated B-urgent manipulation, does the **unchanged** `developmental` treatment
  instantiate parallel division in the P cells? This is SPEC §8 criterion 2, unchanged.

Stage 1 is **not** a full SPEC §8 test. It produces no SUPPORTED verdict and no full NOT SUPPORTED verdict (§9).

## 2. What does not change

**Treatment identity.** The `developmental` treatment in 0c is identical to 0b's. The change is exactly **none**:
- **Policy.** `LLMPolicy` with structured output (0b's CLI default), the model and the effort `low` in the frozen 0b
  constants (`compute.model`, `compute.effort`).
- **Prompts.** The system prompt, the `developmental` MODE RULES line, the action schema and action semantics, the task
  text, the resource display and the briefs.
- **Economics and caps.** B = $1.392 and V = $0.696; the value of time, relaxed $0.0000696/s and urgent $0.0011136/s;
  prices and latencies; the 1500 s deadline; caps (20 steps, 16 agents, 9 live, 10 requests per QUERY); K = 8.
- **Mechanics.** Allocation mechanics and the runtime's lifecycle semantics.

Nothing is added: no hint to spawn, no recommendation to parallelize, no estimated action times, no topology
suggestion, no extra reasoning instruction, no higher effort, and no rewording of parallelism, QUERY or SPAWN.

**How this is enforced:**
- Experiment 0c's constants *are* the constants in `data/exp0b/frozen.json`, read from that file.
- `devagents/` was byte-identical to the 0b pre-registration commit (67c9d50) before this work, and the changes below
  do not touch any prompt text, schema or price.
- `data/exp0c/prereg.json` records the hashes of what the treatment sees:
  - the prompt fingerprint per cell, plus the 0b freeze's reference fingerprint `53790f89…f524b6`;
  - the full `developmental` root and child system prompts per cell;
  - the root briefs;
  - the MODE RULES, the action help and the action schema;
  - the constants.

  `exp0c verify` recomputes all of these, and the tests pin them.
- **Pinned to 0b's own code, not only to the current checkout.** `exp0c verify` checks three things against values
  computed at commit 67c9d50, the 0b pre-registration:
  - the files that define what the treatment sees, reads and is charged are byte-identical (CRLF normalized to LF) to
    67c9d50: `prompts.py` (the system prompt, briefs, status display and observations), `policies.py` (the API
    request), `tasks.py`, `sources.py`, `world.py`, `resources.py`, `metrics.py`, and every world document and the SQL
    world;
  - a deterministic, offline probe drives `single` and `developmental` (dividing and not) in the five 0c cells through
    the 0c policy wrapper, and the sha256 of every API request and every event equals the value the same probe gives
    with 0b's own code (`29a6a2c4…1000b3`);
  - the caps are 0b's literal values: 20 steps per agent, 16 agents, K = 8, 10 requests per QUERY, shares 0.5 and 0.6.
- **The deciding code is pinned too.** `prereg.json` records the sha256 of every file that runs or evaluates 0c
  (`code_sha`). `verify` refuses to run if any differs, every manifest records it, and a stage that ran under other
  code fails its identity check (§9.2), so the pilot gate refuses it.
- Every live run's `RUN_STARTED` record is checked against 0b's configuration (§9.2). Its policy configuration, compute
  option (model, effort, prices, latencies), prompt fingerprint, resource audit (constants, environment identifiers,
  caps, task text), budget, deadline and value of time must all match.

**Byte-unchanged artefacts:** `data/frozen.json` (Experiment 0, `910bf202…dbb6f9`) and `data/exp0b/frozen.json`
(Experiment 0b, `0d10865d…ec50ff`). `SPEC.md`, `SPEC_0B.md` and every Experiment 0/0b result path are also unchanged.

## 3. The only scientific change: a scripted `central`

**The first step is scripted.** The `central` root's first step no longer asks the LLM for a topology. It is a
deterministic SPAWN: the oracle's pre-existing one-shot organization for the cell.

**After that first step everything is live:**
- the root waits, then decides live: it aggregates the reports and answers;
- every child is an ordinary live LLM agent that must do its assigned work;
- no answer and no reasoning result is scripted.

**The topologies.** They are derived from pre-existing committed artefacts and code, without a new search and without
any 0b main-run output:

| cell | organization | k | source |
|---|---|---|---|
| X2 urgent (pilot) | `fanout3@r0` | 3 | the unchanged calibration rule (`calibrate.label`, `router_div` at the base point) applied to X2 at the frozen 0b constants and assumptions; pre-declared as k = 3 in EXPERIMENT_0C_DECISION.md §6 |
| T01 urgent | `fanout3@r0` | 3 | `data/exp0b/frozen.json`, `calibration.cells["T01\|urgent"].router_div` |
| T04 urgent | `fanout4@r0` | 4 | idem, `T04\|urgent` |
| T07 urgent | `fanout3@r0` | 3 | idem, `T07\|urgent` |
| T10 urgent | `fanout4@r0` | 4 | idem, `T10\|urgent` |

**The X2 derivation.** X2's base-point calibration table at the frozen 0b constants and assumptions is solo 0.3545,
fanout1 0.2926, fanout2 0.5138, **fanout3 0.5577**, fanout4 0.5140, fanout5 0.4672 and fanout6 0.5059. The code
refuses to continue if any derived k differs from the pre-declared one.

**Partition.** `route.docs[i::k]`, over the route order committed in `devagents/environment/tasks.py`:

| cell | child 1 | child 2 | child 3 | child 4 |
|---|---|---|---|---|
| X2, T01, T07 | region-northland, region-westreach | region-eastmarch, region-midlands | region-southvale, region-coastal | — |
| T04, T10 | supplier-brisk, supplier-fenwright | supplier-calloway, supplier-galloway | supplier-dunmore, supplier-harrow | supplier-eskerfield, supplier-ivel |

**The SPAWN action.** It is produced by the oracle's own code (`calibrate.oracle_script`, then `_spawn`), byte for
byte:
- the objective of child i is `Find the facts needed for: <question> Read only the sources named in this objective: <id>; <id>`;
- every context is empty;
- the rationale is `Split the work across agents.`;
- `wait_for_children` is true;
- `central` mode ignores the action's budget and lifetime fields, as it always has. The oracle's placeholders
  (`budget_usd` 0.0, `lifetime_s` 1.0) are part of the fixed action, and the live root re-reads them in its
  transcript; the `central` MODE RULES line tells it that these fields are ignored and the fixed share applies.
- `prereg.json` keeps the oracle's key order, so the SPAWN the live root re-reads is the oracle's serialization byte
  for byte.

**Allocation and lifetime.** These follow the existing fixed rule, unchanged: each child gets an equal share of 50% of
the balance left after fees (floor division), and a lifetime of 60% of the remaining time.

**Information used (t0 only).** The question text, the catalog document ids, the frozen constants and the pre-existing
oracle organization.
- **Not used:** document contents, SQL text or results, the answer, anything generated during execution, and anything
  from 0b live output.
- **Why this is t0-only.** All four P cells and X2 are document-only routes, and their documents are identified by the
  question and the catalog.
- **How it is checked.** `exp0c verify` removes the question and the document ids from every objective and requires
  exactly the template to remain. It also checks that no answer text, no SQL and no line of any document appears.

**The scripted step is charged** (`devagents/agents/scripted_central.py`):
- **Decided by an internal `ScriptedPolicy`.** It is priced exactly as the calibration prices oracle steps (SPEC
  §7.1): estimator input tokens × r, plus the JSON action's tokens and the reasoning tokens, at the **frozen 0b
  assumptions** r = 2.0052 and 36 reasoning tokens.
- **Charged like any step.** The runtime charges it as an LLM step, with its latency, and it enters the root's
  transcript.
- **Logged.** A `SCRIPTED_ACTION` event logs it explicitly, before the normal `RESOURCE_CONSUMED` (kind `llm`) and
  `ACTION_STARTED` events.
- **Cost bias.** Pricing at the frozen rather than the live token statistics makes the step slightly cheaper: below
  0.001 fitness offline (§5).
- **The reserve of the root's next step.** The runtime bounds a later step's input from the previous step's reported
  usage. After the scripted step that usage is simulated, and it does not measure how the real API tokenizes the
  re-read SPAWN. So for the `central` root's first live step only, the wrapper declares the runtime's own first-step
  rule over the whole input: 1 token per 2 characters plus the 1000-token request overhead. The runtime reserves the
  larger of this and its own bound, so the reserve only grows. The status line's "a step now needs a balance of at
  least" figure for that step reflects the same bound. This is part of the `central` instrument; no other mode or step
  is affected.
- **Token statistics.** The scripted step's `RESOURCE_CONSUMED` (kind `llm`) is a charge, not an API call. Any token
  statistic over 0c logs must exclude the charge that follows a `SCRIPTED_ACTION`, and the reports give `api_calls`
  (LLM charges minus scripted steps) for every run.

**The declared asymmetry.** `central` runs log the policy configuration of the other modes plus exactly one declared
entry, `central_first_step = "scripted"`.
- Manifests record `declared_asymmetries = {"central": {"central_first_step": "scripted"}}`.
- Audit parity (`report.audit_parity(..., declared=...)`) permits exactly that entry, in exactly that mode, with
  exactly that value. Any other difference still fails, and a run of the declared mode that lacks the entry fails.
- Without a declaration (Experiments 0 and 0b), parity is unchanged.

## 4. Infrastructure-only changes

None of these changes any number of Experiment 0 or 0b; `verify_frozen` on the 0b freeze still passes.

1. **UTF-8 report files.** On Windows, `Path.write_text()` used cp1252 and failed on U+2212 (−) in the report. The
   user-facing report writes now pass `encoding="utf-8"`:
   - `report`'s `report.md` and `summary.json`;
   - `calibrate --json`;
   - `analysis/exp0b_diagnostic/traces.py`;
   - every Experiment 0c report.
2. **`runtime.policy_config(policy, mode)`.** It accepts the run's mode, and a policy may report a per-mode
   configuration (`config_for_mode`). Existing policies are unaffected.
3. **`report.audit_parity(..., declared=None)`.** It gains an opt-in declared-asymmetry argument (§3).
4. **The event log** accepts the `SCRIPTED_ACTION` type.

## 5. Stage 0: offline implementation validation (no API)

`python -m devagents exp0c verify` recomputes everything. If any check fails: **STOP.** The design is never changed to
make a check pass.

1. Experiment 0 and 0b frozen files are byte-unchanged, and the 0b freeze verifies (`verify_frozen` → no problems).
2. The prompt fingerprint equals the 0b freeze's (`53790f89…`).
3. `prereg.json` equals its recomputation, field for field (except `created_at`).
4. The topology k and the partitions are exactly those of §3.
5. Every objective uses t0 information only (§3).
6. The suites are 4 pilot runs and 36 Stage 1 runs.
7. **Mechanics**, in an LLM-free run of scripted `central` in every cell, at both token assumptions:
   - exactly k children and the pre-registered objectives;
   - spawn fees equal to `spawn_fee + transfer_per_token × tokens`;
   - allocations exactly equal to the fixed rule, and lifetimes exactly 60% of the remaining time;
   - no agent-cap or concurrency-cap breach, no cap hit, no invalid action, no exhausted budget, and no reserve
     violation;
   - the scripted step logged once and charged as an LLM step.
8. **Geometry.** In every cell, scripted `central` > `single` > one-child `central`, at both the frozen 0b assumptions
   and the observed 0b main-run token statistics (r = 2.0277, 45 reasoning tokens). The k is never searched here.
9. Under the frozen assumptions, scripted `central` reproduces the oracle fan-out's fitness exactly.
10. The treatment files equal 67c9d50's; the probe's request and event stream equals 0b's (§2); the caps are 0b's.
11. `prereg.json`'s `code_sha` equals the current code (part of check 3).
12. Every pre-registered SPAWN serializes exactly as the oracle's action, key order included.

Hashes of committed text files are taken with CRLF normalized to LF, so a Windows checkout (Git's default
`core.autocrlf`) verifies exactly as committed. Every sha256 this document, `prereg.json`, the manifests and
EXPERIMENT_STATUS.md record for a committed text file is that LF-normalized hash; on a CRLF checkout it differs from
what `Get-FileHash` or `certutil` print for the file on disk.

**Expected geometry** (LLM-free, real runtime modes, 0b constants; fitness):

| | frozen assumptions: `single` | one-child `central` | scripted `central` | live 0b tokens: `single` | one-child | scripted |
|---|---|---|---|---|---|---|
| X2 urgent (pilot) | 0.3545 | 0.2914 | 0.5569 | 0.3526 | 0.2880 | 0.5524 |
| T01 urgent | 0.3547 | 0.2922 | 0.5588 | 0.3528 | 0.2888 | 0.5542 |
| T04 urgent | 0.3352 | 0.2717 | 0.5475 | 0.3332 | 0.2682 | 0.5420 |
| T07 urgent | 0.3548 | 0.2927 | 0.5600 | 0.3529 | 0.2892 | 0.5554 |
| T10 urgent | 0.3350 | 0.2721 | 0.5497 | 0.3331 | 0.2687 | 0.5442 |
| **Stage 1 mean** | **0.3449** | **0.2822** | **0.5540** | **0.3430** | **0.2787** | **0.5490** |

The oracle reasons perfectly and aggregates perfectly. The live check exists because live children and a live root
might not.

The tests additionally run the whole pipeline (§12) with a fake client: no network and no API.

## 6. Stage 0 live pilot: the X2 instrument pilot

**Design:**

| | |
|---|---|
| task | X2, held out (a pilot task, never in a main suite), regime `urgent` only |
| modes | `single`, scripted `central` |
| repeats | R = 2, in seeded shuffled blocks (seed 0), as in SPEC §4 |
| runs | **4**: X2-urgent-{single, central}-r{0, 1} |
| results | `results/exp0c/pilot/` |

**Purpose.** Only to validate that the scripted multi-child `central` instrument works live. It is not a test of the
developmental hypothesis: it has no `developmental` run, and it is never pooled with Stage 1, 0b or the Experiment 0
pilot.

**PASS/FAIL rule.** The pilot PASSES iff all of the following hold. Otherwise it FAILS.

0. **Preconditions.** All 4 planned runs completed (infrastructure errors are retried as in SPEC §8, up to 3 times;
   interrupted attempts count against the same budget, §11). A run whose attempts are spent is final: it is never
   attempted again, and the pilot FAILS as "incomplete (infrastructure)", reported separately from A. Every run passes the treatment-identity checks of §9.2, and audit
   parity holds with only the declared asymmetry.
1. **A. Instrument integrity.** *Every* scripted-`central` run satisfies all of these:
   1. the scripted SPAWN is accepted: logged once as `SCRIPTED_ACTION`, equal to the pre-registered action, and its
      `ACTION_COMPLETED` is ok and not discarded;
   2. exactly k = 3 children are created;
   3. their objectives are exactly the pre-registered partition;
   4. no child starved, i.e. none was terminated `budget_exhausted` before its first step;
   5. no cap failure: no agent in the run hit the step or context cap, and no child was terminated by the runtime
      (budget, steps, context, lifetime or ancestor termination) before it had queried all its assigned documents;
   6. every child actually QUERYied every document in its assignment (successful `INFORMATION_QUERIED` events);
   7. the run completed with a submitted answer (`outcome = answered`). Correctness enters through fitness (B).
2. **B. Realized manipulation.** Mean scripted-`central` fitness > mean `single` fitness on X2 urgent (strict;
   fitness with the frozen 0b urgent weights).

**Reported for both modes:** quality, money, elapsed time, fitness, number of children, the `parallel` indicator and
the API calls. Also reported, per child of every `central` run: its assignment, the documents it queried, any reads
outside its assignment, and how it terminated; and the infrastructure errors per run.

**The decision is final.** The pilot's own run writes `pilot_decision.json` and `pilot_report.md` once. `exp0c pilot`
refuses to run again into a directory that holds a decision, and a later `exp0c report` writes separate
`pilot_recomputed_*` files.

**The pilot record.** When the pilot finishes, it writes `data/exp0c/pilot_record.json`: the `prereg.json` sha, the
pilot manifest's `created_at`, the verdict and the sha256 of `pilot_decision.json`.
- This record is committed (with an EXPERIMENT_STATUS.md entry) before Stage 1.
- `exp0c pilot` refuses to run while the record exists, so deleting the gitignored results directory cannot produce a
  second pilot unnoticed.

**If the pilot FAILS: STOP.**
- Do not run Stage 1.
- Do not change a threshold, k, the partition, the child objective or `developmental`.
- Do not create a second X2 pilot under this pre-registration.
- Report the failure.

`exp0c stage1` refuses to start unless all of these hold:
- the pilot at `results/exp0c/pilot`, under the *same* pre-registration (same `prereg.json` sha, same planned runs) and
  the same code, finished with a final PASS decision;
- `data/exp0c/pilot_record.json` matches that pilot;
- a recomputation from its event logs agrees.

## 7. What may change after any X2 output exists

**Allowed:** only the correction of a genuine implementation defect: in the runtime, the scripted action, the
evaluator, or the logging, that keeps the pre-registered design from executing or being evaluated as specified. If
that happens:
- record the defect;
- do not overwrite or delete the failed pilot;
- put a new, explicit pre-registration boundary (a new `prereg.json` and commit) in place before any rerun.

An infrastructure-only gap (a run whose retries are spent) is a FAIL like any other: there is no second pilot under
this pre-registration.

**Not allowed:**
- changing k, the source partitions, the allocation or the lifetime;
- changing the child-objective wording, the rationale, the context, the wait flag or the scripted-step pricing, for
  any reason (except under a new pre-registration after a recorded genuine defect);
- changing the `developmental` prompt, the effort, the model, the economics, QUERY semantics or SPAWN wording;
- making parallelism more salient;
- changing Stage 1's cells, modes or R;
- changing any GO/NO-GO threshold.

**The same rules hold after any Stage 1 output.** A Stage 1 decision is final. An UNINFORMATIVE Stage 1 (completion,
identity, `single` validity or integrity) is not repeated or topped up under this pre-registration; anything further
needs a new pre-registration boundary.

**A behavioural result is not an implementation defect.** That covers a child that receives a valid objective but
reasons or acts poorly: misreads, reads too much or too little, or reports badly.

## 8. Stage 1: design

| | |
|---|---|
| cells | T01, T04, T07 and T10, urgent (= P = P_urgent = B-urgent in the 0b freeze) |
| modes | `single`, scripted `central`, unchanged `developmental` |
| repeats | R = 3, in seeded shuffled blocks (seed 0) |
| runs | **4 × 3 × 3 = 36** |
| results | `results/exp0c/stage1/` |

**Router is intentionally excluded:**
- it is not needed for the narrow criterion-2 test, and it never enters criteria 1–5 or (v);
- with I = 0, no cell gives an ideal `developmental` a designed advantage over `router` (SPEC §2, §10), so H2 can show
  at most practical differences, and H2 never changes a verdict;
- this exclusion was decided after `router`'s 0b result (zero SPAWN attempts) was seen; it is declared as such
  (EXPERIMENT_0C_DECISION.md §5);
- `router` returns, as pre-registered in SPEC.md, in any future full benchmark or stronger information-dependent
  experiment.

**No pooling.** Stage 1 is a fresh 36-run dataset. The X2 pilot, Experiment 0b and the Experiment 0 pilot never enter
it. The evaluator reads only the planned run ids of a suite whose manifest names experiment `0c`, stage `stage1` and
this pre-registration's sha. Any other log in the directory is ignored, and any other suite is refused.

## 9. Stage 1: the dedicated evaluator

This is not the SPEC §8 evaluator. It never presents its output as a full H verdict. The steps are evaluated **in
this order**, and the first failing step decides.

**9.1 Completion.** At least 90% of planned runs completed per mode (11 of 12), and at least 2 completed repeats in
every cell × mode. Otherwise **UNINFORMATIVE**. A run whose infrastructure retries are spent is final and is never
attempted again; nothing is topped up. Infrastructure errors per run are reported.

**9.2 Treatment identity.** Every run's `RUN_STARTED` record must equal Experiment 0b's configuration:
- the policy configuration: `LLMPolicy`, structured output, the 0b model and effort;
- the compute option: model, effort, prices and latencies;
- the prompt fingerprint for the cell;
- the resource audit: constants, source costs, the catalog sha, source ids, task text, caps and allocation shares, and
  the 0b frozen sha;
- the budget, deadline and value of time.

The caps must be 0b's literal values (§2). A log whose `RUN_STARTED` predates the suite's manifest is foreign (for
example a copied 0b log, which would otherwise look identical) and fails identity. The manifest must carry the
pre-registered action-schema sha, prompt fingerprint, constants, declared asymmetry, 0b frozen sha, SPEC_0C sha and
`code_sha`, and the code must still match `code_sha`.
Audit parity must hold with only the declared asymmetry, and only `central` may have a scripted step. `central` may
differ only by `central_first_step = "scripted"`. Any other drift → **UNINFORMATIVE**.

**9.3 `single` validity.** This is the rule of EXPERIMENT_0C_DECISION.md §7 (2):
- `single` accuracy ≥ 0.75, i.e. ≥ 9 of 12 correct;
- the `single` cap-hit rate ≤ 5%, SPEC §8 (vi). With 12 runs, one cap hit already fails.

Otherwise **UNINFORMATIVE**.

**9.4 Scripted-`central` integrity (mechanical).** A run is intact iff all of these hold:
- the scripted SPAWN was accepted;
- exactly k children were created;
- the objectives are exactly the pre-registered assignments;
- no child starved;
- no child was terminated by the runtime (budget, steps, context, lifetime or ancestor) before it had queried its
  assigned documents.

If **2 or more** completed scripted-`central` runs are not intact → **UNINFORMATIVE (implementation failure)**. The
causes are listed per run. A runtime termination before the assigned QUERY counts as non-intact even when the child's
own choices led to it (for example WORK until the step cap); the cause list makes that visible.

A child that receives a valid assignment but chooses not to query it, or reads outside it, is **behaviour**. That is
not a mechanical failure: it is reported separately per run and counts in 9.5. The report also gives the number of
runs in which every child read exactly its assignment. This matters because the mean alone would still pass with up to
9 of 12 runs degraded to one-child fitness.

**9.5 Live manipulation.** Mean fitness of scripted `central` > mean fitness of `single`, over the completed runs of
the four P cells (strict; frozen 0b urgent weights).
- **If it fails: STOP.** There is no Stage 2.
- The report decomposes the shortfall into its fitness components: quality (quality − failure penalty), money
  (−money/V) and time (−value of time × elapsed/V).
- The shortfall is said to be *primarily associated* with the component of the most negative mean difference:
  **quality / aggregation**, **money** or **elapsed time**.

**9.6 `developmental` criterion 2, unchanged.** parallel_rate(P) is SPEC §8's rate: `analysis.Runs.rate` over the four
P cells, with the indicator **`parallel`**. That means ≥ 2 agents with overlapping QUERY source processing. It is never
a SPAWN attempt, a successful SPAWN or a child count. The criterion **fires iff parallel_rate(P) < 0.50**.
- With 12 complete runs: **0–5 parallel runs → NO-GO; 6–12 → GO** (if everything else holds). With 11 (one run
  missing), the rate is still SPEC §8's mean of per-cell rates, so the count that crosses 0.50 depends on which cell
  lost the run.
- A spawned organization that does not satisfy `parallel` does not count.
- If criterion 2 fires, the report states exactly:

  > Under a live-validated B-urgent manipulation, the unchanged developmental treatment triggers the preregistered
  > never-spawn criterion. Under the full SPEC §8 design this criterion alone would make H NOT SUPPORTED in a valid
  > full experiment, but this narrow Stage 1 does not itself constitute a full §8 verdict.

  It never writes "H refuted", "adaptive architectures do not work", or any broader conclusion.

**9.7 GO** requires all of 9.1–9.5 to hold, and parallel_rate(P) ≥ 0.50. **If GO: STOP.** Nothing is launched
automatically: there is no Stage 2 command. A Stage 2 requires explicit user approval and a new pre-registration
decision.

## 10. Pre-declared research interpretation

This is declared before any new live output exists. Suppose all of the following hold:
- the X2 instrument pilot passes;
- the Stage 1 `central` manipulation passes;
- Stage 1 is otherwise valid;
- the unchanged `developmental` has parallel_rate(P) < 0.50.

Then the primitive Experiment-0 mechanism receives a substantive negative result:

> Under the current neutral representation, current model/effort, and a live-validated environment in which division
> is advantageous, the unchanged developmental policy does not reliably instantiate parallel division.

This does **not** imply that adaptive architectures have no value, that developmental computation is impossible, or
that information-dependent restructuring cannot work.

It **does** mean: do not run another version of the same primitive experiment with incremental prompt tuning. The
next defensible choice is either:
- **A.** stop this mechanism line; or
- **B.** formulate a separately pre-registered **new** mechanism hypothesis, for example making the computational
  consequences explicitly legible.

That would be a new experiment, not a repair of 0c. As EXPERIMENT_0C_DECISION.md §7 declared, at most **one** such
representation experiment may follow; its single variant would be the only prompt variant ever run on these cells.

## 11. Results isolation and manifests

- **Paths.** Experiment 0c uses `data/exp0c/prereg.json`, `results/exp0c/pilot/` and `results/exp0c/stage1/`. It never
  reads or writes `results/pilot`, `results/exp0b/…`, `data/frozen.json` (except to hash it) or any Experiment 0/0b
  result.
- **Directory guard.** Inside `results/`, a stage refuses any directory other than its own.
- **Manifests.** Every manifest records:
  - the experiment (`0c`) and the stage;
  - the planned run ids (the suite identity) and the cells, modes and repeats;
  - the `prereg.json` sha, the SPEC_0C.md sha and the 0b frozen sha;
  - the constants, the action-schema sha, the prompt fingerprint, the declared asymmetry and the policy configuration.
- **Resume.** A stage resumes only into a directory whose manifest matches the requested suite exactly (every field but
  `created_at`), and only while it holds no final decision. Otherwise it refuses. Completed runs, and runs whose
  attempts are spent, are never attempted again.
- **Interrupted and failed attempts lose no live output** (Experiment 0c's own runner, `run_suite_0c`; the shared runner
  of Experiments 0 and 0b is unchanged):
  - every failed attempt is written to `errors.jsonl` when it happens;
  - a partial event log, left by an infrastructure error or by an interruption (Ctrl-C, a killed process, a crash), is
    moved to `events/aborted/<run_id>.<n>.jsonl`, never deleted, and counts as one failed attempt;
  - an interrupted run is retried within the same budget: the original attempt plus 3 retries, counted from
    `errors.jsonl` across sessions;
  - a log that reached `RUN_COMPLETED` before the interruption is kept as a completed run, not run again.
- **Manifests** also record `code_sha`. Each invocation appends the git commit (with `+dirty` if tracked files differ)
  to `invocations.jsonl`, for information; it is never compared.
- **Paths.** Experiment 0c's result paths are anchored at the repository root, whatever the working directory.
- **Not in `EXPERIMENTS`.** Experiment 0c is not registered for the generic `run`/`report`/`freeze` commands (`--experiment` accepts only 0 and 0b), so
  no generic command can run a full 0c benchmark.

## 12. Commands

```
python -m devagents exp0c verify          # Stage 0, offline: every check of §5 (exit 1 on any failure)
python -m devagents exp0c pilot           # the 4-run X2 instrument pilot (API key needed)  <- the next live action
python -m devagents exp0c stage1          # the 36-run Stage 1; refuses unless the pilot PASSED
python -m devagents exp0c report DIR      # recompute a stage's decision from its event logs (separate files)
```

`python -m devagents exp0c prereg` wrote `data/exp0c/prereg.json`; it refuses to run while that file exists.

`pilot` and `stage1`:
- verify the pre-registration, then check that API credentials are configured, before writing anything;
- take no directory argument;
- write their decision files (`<stage>_report.md`, `<stage>_decision.json`) and print the decision.

The command exits 0 for PASS, GO or NO-GO, and 1 for FAIL, STOP or UNINFORMATIVE.

**Expected size:**
- the pilot: about 18 API calls (`single` 2 per run; `central` 1 live root step plus 2 per child);
- Stage 1: about 144 API calls, up to about 190 with extra steps.

The scripted step is charged and counted in the simulated `llm_calls`, but it is not an API call.

## 13. Deviations from EXPERIMENT_0C_DECISION.md

The accepted decision is option B. Where this pre-registration differs from the memo's sketch, the experimenter's
later instructions decide, and the difference is declared here:

1. **The pilot also gates on the manipulation** (B: central > single on X2), not only on instrument integrity.
2. **No identical repeat** after an incomplete pilot or an UNINFORMATIVE Stage 1 (the memo allowed one); no second
   pilot under this pre-registration. An *interrupted* run is not a repeat: it continues within its retry budget
   (§11).
3. **The objective wording is fixed** and is not revised on X2 (the memo allowed revising it on X2 before Stage 1).
4. **No option-E variant text** is committed with this pre-registration (the memo suggested it); any E is a separate,
   future pre-registration.
5. **The reserve of the central root's first live step** follows the runtime's first-step rule (§3); the memo did not
   address it.
6. **The Stage 1 integrity rule** is the experimenter's (§9.4); a child that does not read its assignment is behaviour,
   counted in the manipulation check, as the memo also intended.

## 14. Limitations

- **4 cells from 2 task templates, one model at effort `low`.** Stage 1's runs are clustered, and its probabilities
  assume independence.
- **The oracle assumes perfect aggregation.** The live manipulation check is where the calibration is least tested.
- **R = 2 in the pilot is a sign check, not a test.** It gates on instrument integrity and on the direction of the
  manipulation only.
- **Pricing of the scripted step.** It is priced at the frozen token assumptions (§3), which favours `central` by under
  0.001 fitness.
- **The reserve after the scripted step.** It follows the runtime's first-step rule (§3). Offline, with tokenization
  denser than that rule (0.5225 tokens per character for text, 0.7 for the JSON, plus 70 tokens on the system prompt)
  and 3000-character child reports, its headroom is 3–6% in every cell. Much denser tokenization could still raise a
  `ReserveViolation`. That is an infrastructure error, so it is retried; if the retries are spent the stage is
  incomplete, and correcting it is a defect correction under §7.
- **The live 0b logs are not in this repository.** The 0b facts in §0 are as recorded in EXPERIMENT_STATUS.md.
