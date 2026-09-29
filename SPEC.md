# SPEC — Experiment 0: resource-aware division

**Status: pre-registration.** No LLM result exists yet.

- §7 (the calibration gate and the criteria check), §8 (falsification) and §9 (estimands) must
  not be weakened after any main-suite LLM result exists.
- Environment constants may change only through the mechanical, LLM-free procedure in §7.4.
  Every change is logged in §11.
- The freeze is a git commit of `data/frozen.json`, made before the first main run (§12).

## 1. Research question

A general agent works in an explicit resource environment and can either keep working alone or
spend its own resources to create another agent. Does it make that choice *economically*? That
is, does one lifecycle policy stay single-agent where division does not pay and divide where it
does? And does it do so because the time–money–quality trade-off differs, not because of
surface features of the task?

## 2. Hypotheses

**H (primary).** Local, resource-aware decisions about spawning and self-termination (mode
`developmental`) produce organizations that depend on the task and the resource conditions.
Those organizations improve the time–money–quality frontier relative to a fixed single agent
(`single`) and to a fixed central decomposition (`central`), without collapsing into
always-spawn or never-spawn.

**H-twin (part of criterion 3).** Hold task content fixed and change only the value of time.
The developmental policy's division then changes in the direction the calibration predicts.

**H2 (secondary, pre-registered, cannot change the §8 verdict).** `developmental` outperforms
`router`, which makes one organizational decision, at its first action, with no recursion. In this
environment no cell gives an ideal `developmental` a *robust* advantage over an ideal `router` (no I
cells, §10). So H2 asks mainly whether local, incremental decisions help *in practice*.

**H0.** Any criterion in §8 fires.

## 3. Resource model

| Resource | Exp 0 representation | Transfer |
|---|---|---|
| **Time** | Simulated, in integer microseconds. There is one run deadline, and each child has its own lifetime. Time is irreversible | none |
| **Money** | Integer micro-dollars (µ$). There is one run budget `B`, held in per-agent balances | only by allocation (SPAWN) and refund (termination) |
| **Compute** | `ComputeOption`: id, model, relative capability, prices, latency model, reasoning effort, context capacity, concurrency. Exp 0 uses **one** option for every agent in every mode (§11) | n/a |
| **Information** | SQLite (structured: cheap, fast, compact) and Markdown docs (unstructured: a fee plus latency proportional to length, with the full text entering the context). Active context is the agent's transcript, which is re-read and paid for on every LLM step. Information discovered by other agents arrives only through paid messages and reports | copying costs a fee per token |
| **Authority** | A per-agent set of readable sources. It is inherited at spawn and never widened. Nothing reads fitness when setting it | none |
| **Human attention** | Conceptual only; inactive in Exp 0 | — |

### 3.1 Normative cost and time table

Fee-bearing text is counted with the deterministic estimator (`ceil(chars/4)`). LLM steps are
charged the token usage the API reports.

| Event | Charge (paid by the actor) | Actor's clock | Effect time |
|---|---|---|---|
| LLM step (every decision) | `in·p_in + out·p_out` (reasoning included) | `+ base + in·t_in + out·t_out` | — |
| QUERY, per request | sql: `sql_fee`; doc: `doc_fee` | sql: `+ sql_base + rows·sql_row`; doc: `+ doc_base + tokens·doc_tok`. Requests are sequential, so latencies add | results enter context at COMPLETE |
| SPAWN, per child | `spawn_fee + transfer·(est(objective)+est(context))`. The allocation moves at COMPLETE | `+ spawn_latency`, once per SPAWN action | children start at COMPLETE, with deadline `min(parent deadline, COMPLETE + lifetime)` |
| MESSAGE, or a child's TERMINATE report | `msg_fee + msg_tok·est(content)` | +0 | delivered at `COMPLETE + msg_latency` |
| WAIT | 0 | blocked until woken | — |
| Lifecycle notice to a parent (expiry, forced stop) | 0; the notice carries only `id terminated (reason)` | — | delivered at `termination + msg_latency` |

The values are in `devagents/runtime/resources.py` (compute, coordination) and
`devagents/environment/sources.py`. They are frozen in `data/frozen.json`.

- **Provisional values:**
  - model `claude-opus-5-5` at $4/$20 per MTok, effort `low`;
  - LLM latency 1.5 s + 0.05 ms per input token + 20 ms per output token;
  - SQL: $0.0005 and 1 s;
  - document: $0.002, and 3 s + **0.1 s per token** (unstructured processing is deliberately slow);
  - spawn: $0.001 + 2 µ$ per token, and 1 s;
  - message: $0.0002 + 2 µ$ per token, and 0.5 s.
- **Every price and latency is shown to every agent.**
- Query results are never cached, and every QUERY is charged in full.

### 3.2 Event semantics: a deterministic discrete-event simulation

Events are processed in the order (time, class, agent creation index, sequence). The classes,
in order, are **COMPLETE < EXPIRE < DELIVER < WAKE < START**.

- **START:**
  1. The agent observes every message delivered since its previous observation.
  2. The runtime computes its step reserve (§3.3) and asks the policy for one action.
  3. The LLM step and the action's own charges are posted immediately, **all-or-nothing**. An
     unaffordable QUERY or SPAWN is rejected whole, and so is a SPAWN over a cap. A rejected
     action is still charged for its LLM step and counts as invalid.
  4. COMPLETE is scheduled.
- **COMPLETE:** the effects apply, only if the actor is still live. An action whose actor was
  terminated in flight keeps its charges and has no effects. A MESSAGE whose recipient terminated
  while the MESSAGE was in flight is charged, not delivered, and reported to the sender as
  undelivered.
- **EXPIRE:** the agent terminates at its deadline. For the root, the run fails.
- **Termination** proceeds in post-order (descendants first, in creation order). Each agent's
  whole balance is refunded to its parent, which is always live at that moment. The root's
  final balance is unspent money. After the run, every non-root balance is 0.
- **Run end:**
  - The run ends when the root's TERMINATE completes (the answer time), or at the root's
    EXPIRE, or when the root is force-stopped.
  - All remaining agents are then cascade-terminated at that time.
  - Nothing is charged after an agent terminates.
  - The answer counts only if its TERMINATE completes at or before the deadline.
- **WAIT:**
  - `WAIT(any)` wakes on the next delivery, or immediately if a delivered message is unread.
  - `WAIT(all)` wakes when no child is live and every child's report or lifecycle notice has been
    delivered, or immediately if both already hold.
  - An absent `max_wait_s` means the agent's own deadline. A numeric value `v` waits at most
    `max(0, v)` seconds, so 0 is an immediate poll.
  - A child's termination becomes visible in its parent's status block only once its report or
    notice has been delivered.
  - `WAIT(any)` with no live child, no live parent and nothing in flight is invalid.
- **Continuation:** SPAWN may set `wait_for_children: true`, which enters `WAIT(all)` without
  another LLM step. It is available in every spawning mode, forced in `central`, and used by
  the calibration oracle.
- **Suspension:** if an agent cannot afford a minimum step but has live children, it is
  suspended as `WAIT(any)` with no LLM call. With no live children it is terminated
  `budget_exhausted`.
- **Caps:**
  - **K**, the per-run division cap, is `max_concurrency − 1 = 8`. It is the maximum number of
    children per SPAWN in every mode and the fan-out used by the oracle.
  - At most `max_concurrency = 9` agents may be live at once, counting the root and waiting
    agents.
  - At most 16 agents per run, counting the root.
  - Both caps also count children of SPAWNs that are accepted but still in flight.
  - At most 20 steps per agent, checked at every START, whatever the previous action was. Every
    cap hit is logged.

### 3.3 Money: conservation and reserve rules

1. The root starts with `B`. Money moves only by `charge` (spent) and `transfer` (allocation
   or refund). Nothing creates money.
2. **Step reserve.** Before each LLM step:
   - `max_tokens = min(cap, (balance − in_upper·p_in − msg_fee) // (p_out + msg_tok))`.
   - `in_upper` is the previous step's input plus its output tokens, plus 1 token per 2 new
     characters, plus a fixed request overhead of 1000 tokens (for every policy, including the
     calibration oracle), which covers the injected output schema. On the first step `in_upper`
     is 1 token per 2 characters of the system prompt and first observation, plus the same
     overhead.
   - A policy may declare its own input bound for a step, and the reserve then uses the larger of
     the two, so a declaration can raise the reserve but never lower it. The calibration oracle
     declares exactly the input it is priced at (§7.1), which the 1-token-per-2-characters bound
     does not cover when r > 2. The live LLM policy declares none (§11 item 16). The status
     block's "next step needs" figure is computed before the new observation is appended, so for
     a declaring policy it can understate that step's reserve; the reserve itself is always the
     one applied at the step.
   - **The rule is disclosed.** The shared system prompt states the output cap, the reserve rule,
     and the approximate cost of a new agent's first step. Every status block shows the balance
     the agent's next step needs.
   - The step itself, and any MESSAGE or report that fits in its output, can therefore never
     overdraw.
   - A realized cost above the reserve is an **infrastructure error** (`ReserveViolation`). It
     is never absorbed as a free call.
3. If `max_tokens < min_step_tokens`, the agent is suspended if it has live children and
   terminated `budget_exhausted` otherwise. A reply truncated at a budget-capped `max_tokens`
   also ends the agent `budget_exhausted`.
4. **Invariants, checked after every event and in tests:**
   - `Σbalances + Σspent = B`.
   - Every balance is ≥ 0.
   - Every terminated non-root agent has balance 0, and its refund equals its final balance.
   - Charges recomputed from the event log equal the ledger.
   - No action starts after its actor terminates or after the run ends.
   - No effect event appears from an action that was discarded.

### 3.4 Fitness (system-level; raw metrics are stored without weights)

```
fitness = quality − money_usd/V − value_of_time·elapsed_s/V − w_coord·coordination_usd/V − failure_penalty·[failed]
cost    = quality − fitness      (the penalty terms: the resource side of the frontier)
```

- `quality` ∈ {0,1}, frozen normalizer in `evals/metrics.py:grade`:
  - numbers: exactly one number in the answer, relative tolerance 1e-6;
  - names: casefolded, punctuation-stripped equality with the answer or a listed alias.
- `V = $0.50` is the value of a correct answer, so that money matters at the scale of these
  runs (§11). `failure_penalty = 1`. `w_coord = 0`, because spawn and message costs are already
  inside money and time.
- `failed` means the root did not submit an answer by the deadline, for any reason. Then
  `elapsed = deadline`.
- The agent is told this formula with its numeric values. The regime names are never shown.
- `report --value-of-time …` rescoring is allowed only as **exploratory** output, and it is
  stamped as such.

## 4. Task environments and run plan

There is one fictional company world, deterministic and committed to `data/world/`:

- `structured.sql`: suppliers, quarterly audits and regional revenue.
- 15 Markdown docs: 1 policy, 6 regional reports and 8 supplier profiles, each about 330–550
  tokens.

Facts sit in prose next to distractors: prior-quarter values, ISO 14001 vs 9001, former CEOs and
secondary sites. **Every task sees the same catalog**, which lists the table schemas and doc
ids with sizes. Task ids are neutral, and the class is never shown. Ground truth is computed
from the generator's fact tables. Tests check three things:

- the facts appear in the sources;
- the SQL routes return the answers;
- every argmax or argmin is unique, and every dependent filter changes the answer.

| Class | Tasks | Designed economics |
|---|---|---|
| **A** solo-friendly (4) | T02, T08 (1 doc); T05, T11 (1 SQL) | Division is overhead |
| **B** parallel-friendly (4) | T01, T07 (6 region docs); T04, T10 (8 supplier docs). All use the template "Across the six regions / eight suppliers, …", and the facts exist only in docs | Division saves time and costs money: it pays under `urgent` only |
| **C** cross-source, dependent (4) | T03 (SQL → 1 doc); T09, T15 (SQL narrows 8 suppliers to 6 docs); T12 (SQL narrows 6 regions to 5 docs, or read all 6) | T03 is solo. For T09, T12 and T15, division after the SQL pays under `urgent`, but not robustly (§7.2) |
| **C** cross-source, shortcut (3) | T06, T13, T14. Same template as B, but one SQL query answers the question, and the facts are also in 6–8 docs | Solo via SQL. These are the **dissociation cells**: surface cues say "divide", economics say "don't" |

That makes 15 tasks: 4 in class A, 4 in class B and 7 in class C. Three held-out **pilot
tasks** (X1–X3) are used only by the pilot and the smoke run.

**Regimes** differ **only** in `value_of_time`. The provisional values are `relaxed` =
$0.00005/s and `urgent` = $0.0008/s. Both regimes share one budget ($1.00) and one deadline
(1500 s). The deadline is at least 2× the pilot's p95 elapsed time for `single`, so it does not
bind in normal operation.

**Run plan:**

- Grid: 15 tasks × 2 regimes × 4 modes × R repeats. R is fixed by §7.3 and recorded in
  `data/frozen.json`.
- Compute: `claude-opus-5-5`, effort `low`. Sampling parameters are unavailable on this model.
- Order: each (task, regime, repeat) block runs all four modes in a seeded random order.
- A failed run counts in the plan. No runs are added after main results are seen.

## 5. Lifecycle actions

Each step is one policy decision, which selects one action.

- `WORK(notes)`
- `QUERY(requests: [{kind: sql|doc, target}] ≤ 10)`
- `SPAWN(children: [{objective, context, budget_usd, lifetime_s}] ≤ K, wait_for_children?)`
- `MESSAGE(to: parent|child, content)`
- `WAIT(wait_for: any|all, max_wait_s?)`
- `TERMINATE(answer)`. The root's answer is the final answer; a child's answer is its report to
  its parent. **Termination is self-termination.** A parent reclaims a child's money only when
  the child terminates, its lifetime expires, or a cascade ends it.

The semantics and costs are in §3.

## 6. Modes

**Prompt parity.** Every agent in every mode gets the **same system prompt**: all six actions,
the full price and latency table, the reserve rule, the catalog and the scoring formula. Every LLM
request carries the **same output schema** (all six actions); actions a mode does not allow are
rejected by the runtime as invalid, charged steps, not made impossible by the schema. The only exception is
one **MODE RULES** line, written in parallel form and neutral in role ("root agent", never
"coordinator" or "worker"). A test renders every mode's prompts for the same (task, regime) and
asserts that they differ only in that slot. It also asserts that the equal-resource audit
record is identical: budget, deadline, value of time, compute option, caps, sources, catalog
hash, repeat, and the frozen hash. Every run logs the audit record and the prompt fingerprint.

| Mode | Allowed | Organization |
|---|---|---|
| `single` (Baseline A) | WORK, QUERY, TERMINATE | fixed: one agent |
| `central` (Baseline B) | The root's first valid action **must** be SPAWN of 1–K children, with `wait_for_children` forced. Allocation and lifetime follow a fixed rule: an equal share of 50% of the balance left after fees (floor division), and a lifetime of 60% of the remaining time. The root then continues without SPAWN. Children cannot spawn | fixed decomposition, decided before any look at the data |
| `router` (H2) | Same as `developmental`, with exactly two restrictions: SPAWN is allowed only as the root's **first valid action**, at most once; and children cannot spawn. The LLM chooses allocations, lifetimes and WAITs | one-shot organization decided at the start |
| `developmental` (C) | Any agent may use any action at any step | local, incremental, recursive |

## 7. Calibration, criteria check, and freeze (LLM-free, except for token measurement in the pilot)

### 7.1 Oracle organizations

The oracle runs scripted organizations through the **same runtime and `developmental`
prompts** as the experiment. It reasons perfectly and knows each task's solution routes. Each
organization uses its own best route. For shortcut tasks, `solo` may use SQL, and a fan-out may
use SQL or the docs.

- `solo`: one agent. It queries the route's sources (SQL first when the docs depend on it) and
  answers.
- `fanout-k` (1 ≤ k ≤ min(K, #docs)): "divide after looking". The root runs any SQL itself,
  then spawns k children with `wait_for_children`. The docs are assigned round-robin, and
  allocation uses the §6 `central` rule, applied by the runtime itself (`fixed_rule_spawns`), so
  the oracle and `central` share one implementation. Each child reads its docs and reports, and the root
  answers. On a doc-free route, `fanout-1` gives the SQL to one child.
- `atstart-k` (dependent routes only): "divide before looking". The root spawns k children
  over all candidate docs, and each child runs the SQL and reads only its qualifying docs. The
  best division available to `router` and `central` is the best of `atstart-k` and `fanout-k`
  on routes without an SQL-first step.

Every oracle step is priced as `(estimator tokens × r)` input plus `(JSON action tokens +
reasoning tokens)` output.

### 7.2 Labels and validity gate

The perturbation grid is:

- `r ∈ {0.75, 1, 1.25} × base r` (base r = 1 without a pilot, the pilot's measured r after it)
- reasoning tokens ∈ {0.5, 1, 2} × base
- extra WORK steps per agent ∈ {0, 1}

A cell (task, regime) is labelled as follows:

- **S** if the best `solo` beats the best division by ≥ **δ = 0.03** at every grid point.
- **P** if the best division beats `solo` by ≥ δ at every grid point.
- **ambiguous** otherwise. Ambiguous cells are excluded from S and P, but they stay in 4b and
  4c.
- **I** ("incremental") if a cell is P *and* the best `developmental` organization beats the
  best one-shot organization by ≥ δ at every grid point. I cells are reported for H2.

**Gate** (all must hold at freeze):

- (a) Every A cell is S.
- (b) Every B-urgent cell is P, and every B-relaxed cell is S.
- (c) Every shortcut cell is S.
- (d) At the base point, the best organization's fitness is ≥ 0.5 and `solo`'s fitness is
  ≥ 0.3 in every cell. So answering always beats giving up, and reading alone beats guessing,
  whose expected fitness is ≤ 0.17.
- (e) S_urgent, P_urgent, the twin set and D_urgent are all non-empty.
- (f) At the base point every oracle organization, and at every grid point every `solo`
  organization, runs with zero invalid actions, zero cap hits and no starved agent. An organization
  that cannot complete cleanly at some other grid point (for example, a child starved by the fixed
  allocation rule) counts as infeasible there.

### 7.3 Criteria check (power and specificity)

The actual §8 `evaluate` is fed seeded synthetic run sets: 200 per policy, with 400 bootstrap
resamples instead of 10,000. In each run:

- The organization is chosen by the policy.
- `quality ~ Bernoulli(p_class)`, with `p_class` equal to the pilot's `single` accuracy, or 0.9
  if there is no pilot.
- `fitness = quality − cost_org × N(1, cv)`, where `cost_org` comes from calibration at the
  base point and `cv = max(0.25, pilot cost CV)`.
- `single` always stays solo, and `central` always uses the best one-shot division.

The developmental policies are:

- IDEAL follows the base-point optimum.
- NEVER always stays solo.
- ALWAYS always divides.
- RANDOM divides in half of its runs.
- SPAWN-IFF-URGENT divides whenever the regime is `urgent`.
- SPAWN-IFF-MULTIDOC divides whenever the doc route has ≥ 4 docs.
- WASTEFUL organizes like IDEAL but, where it stays solo, pays as much as the fixed
  decomposition. It targets criteria 4c and 5.

**R** is the smallest value in {3, 5, 8, 10} for which two conditions hold. First, IDEAL is
judged "supported" in ≥ 80% of simulations. Second, every other policy is judged "not
supported" in ≥ 95%.

### 7.4 Protocol

1. **Pilot** (`python -m devagents pilot`): `single` and `central` only, on pilot tasks X1–X3,
   both regimes, 2 repeats. No developmental or router output exists before the freeze, and
   `freeze` refuses a pilot that contains any. The pilot measures:
   - `r` (API input tokens ÷ estimator tokens, on identical prompts);
   - median reasoning tokens per step (output − visible reply);
   - p90 output tokens, which gives `min_step_tokens = max(256, p90)`;
   - `single` p95 elapsed time, which gives `deadline = max(1500 s, 2 × p95)`;
   - `single` accuracy per class, which gives `p_class`;
   - the cost CV: a pooled relative variance with n−1 sample variances across (task, regime,
     mode) groups, on the §3.4 resource cost without the failure penalty.

   The token ratio r is measured on the visible text only: thinking blocks are excluded, as in
   the oracle's count.
2. **Freeze** (`python -m devagents freeze --pilot DIR`): calibrate, then gate. If needed,
   apply **mechanical repair**, then run the criteria check, and write `data/frozen.json`
   (constants, assumptions, labels, calibrated values, sets, R, pilot statistics, and the prompt
   fingerprint). Commit the file, and record its SHA-256 in `EXPERIMENT_STATUS.md` and §11.

   **Mechanical repair** walks the candidates in lexicographic order of (doc steps, urgent
   steps, relaxed steps), each from 0 to 6:
   - `doc_tok`: +0.005 s/token per step;
   - urgent `value_of_time`: ×1.25 per step;
   - relaxed `value_of_time`: ×0.8 per step.

   The first candidate that passes both the gate (with an exact re-simulation) and the
   criteria check is frozen.
3. **Main run** (`python -m devagents run`). It refuses to start in three cases: when the
   recomputed calibration differs from `data/frozen.json` (labels, sets, any calibrated value, or
   the prompt fingerprint), when no freeze exists, or when the freeze is provisional (made without
   a pilot). A results directory can only be resumed by the identical suite (same manifest: planned
   runs, freeze, policy configuration, constants). Exploratory runs default to a separate
   directory.

## 8. Falsification criteria (pre-registered)

**Estimands.**

- A *cell* is a (task, regime) pair.
- The per-cell rate of an indicator is its mean over completed runs.
- `rate(X)` is the **unweighted mean over (class, regime) strata** of the mean cell rate
  within each stratum of X.
- **Indicators.** `spawned` means ≥ 1 child was created; it is used on the S side.
  `parallel` means ≥ 2 agents had overlapping QUERY source processing; it is used on the P
  side.
- **Contrast θ(X, c, metric).** For each task, `d_task` is the mean over its cells in X of
  (mean `developmental` metric − mean comparator metric). θ is the unweighted mean over classes
  of the mean `d_task`. The metrics are `fitness`, `−cost` and `quality`.
- **CI.** The 95% percentile bootstrap has two levels (tasks within classes, then runs within
  each cell and mode): 10,000 resamples, seed 0.

The hypothesis is **NOT supported** if any criterion below fires:

1. **Always-spawn collapse:** `spawned_rate(S) > 0.50`.
2. **Never-spawn collapse:** `parallel_rate(P) < 0.50`.
3. **No task- or resource-dependent differentiation:**
   - (a) within a regime, for every regime r where both P_r and S_r are non-empty:
     `parallel_rate(P_r) − spawned_rate(S_r) < 0.30`;
   - (b) twin: on the tasks whose label is P under `urgent` and S under `relaxed`,
     `parallel_rate(urgent) − spawned_rate(relaxed) < 0.30`;
   - (c) dissociation: `parallel_rate(P_urgent) − spawned_rate(D_urgent) < 0.30`, where D is
     the set of shortcut cells.
4. **No frontier gain over `single` once resources are equalized:**
   - (a) **no cost gain where division pays:** θ(P, single, −cost) has a CI lower bound ≤ 0;
   - (b) **quality loss:** θ(all cells, single, quality) has a CI upper bound < 0;
   - (c) **cost loss where division does not pay:** θ(cells not in P, single, −cost) has a CI
     upper bound < 0.
5. **A simple central strategy suffices.** On S cells, the cells where a fixed decomposition is
   designed to differ from an adaptive one, `central` matches `developmental`: θ(S, central,
   −cost) *and* θ(S, central, quality) both have CI lower bounds ≤ 0.

Mean fitness, the per-cell Pareto frontier, coordination spend, `central` on P cells, and H2
(`developmental − router` on fitness, cost and quality, over all cells and over I cells) are
all reported and never change the verdict.

**Validity conditions.** If any fails, the run is *uninformative*: neither supported nor
falsified.

- (i) The §7 gate holds, and `data/frozen.json` matches.
- (ii) `single` accuracy is ≥ 0.75 in every class.
- (iii) Audit parity and the prompt fingerprint are identical across modes in every block.
- (iv) Per mode, ≥ 90% of planned runs complete without an infrastructure error, and every
  cell has ≥ R − 1 completed runs in every mode.
- (v) **Realized manipulation check:**
  - on B-urgent, `central` fitness > `single`;
  - on B-relaxed, `central` < `single`;
  - on A, `single` ≥ `central`.
- (vi) `single` hits the step or context cap in ≤ 5% of runs in every class.

**Infrastructure errors** are exactly: a network failure; HTTP 429 or 5xx after the SDK
retries; an SDK transport exception; and `ReserveViolation`. An errored run is retried with the
identical config up to 3 times. Everything else is a policy outcome, including refusals,
unparseable output and context overflow.

## 9. Metrics and events

**Event types.** Each event carries `seq`, `run_id`, `type`, `t` (simulated seconds), `wall`,
and `agent` and `parent` where relevant.

| Type | Additional fields |
|---|---|
| `RUN_STARTED` | task_id, task_class, regime, mode, repeat, budget, deadline_s, value_of_time, compute, audit, prompt_sha, policy |
| `AGENT_CREATED` | depth, objective, deadline, permissions |
| `AGENT_SPAWNED` | child, allocation, fee, context_tokens, objective |
| `RESOURCE_ALLOCATED` | source, target, amount, kind (`allocation` or `return`) |
| `RESOURCE_CONSUMED` | kind (`llm`, `query`, `spawn` or `message`), amount (µ$); for llm also in/out tokens, est_in_tokens, est_visible_out_tokens, compute, latency_s, wall_s |
| `INFORMATION_QUERIED` | source, kind (`structured` or `unstructured`), ok, tokens, rows, fee, latency_s |
| `MESSAGE_SENT` | to, kind (`message` or `report`), tokens, fee, deliver_at, content |
| `ACTION_STARTED` | step, action, detail, llm_latency_s, action_latency_s |
| `ACTION_COMPLETED` | step, action, ok, error, duration_s, discarded |
| `AGENT_TERMINATED` | reason, returned, returned_to, steps |
| `RUN_COMPLETED` | answer, outcome, quality, elapsed_s, total_spent |

**Per-run metrics, all recomputed from the log only.** Tests check them against the ledger.

- correctness and outcome;
- money spent, split into llm, query, spawn and message spend;
- coordination spend;
- simulated elapsed time and wall time;
- LLM calls and input and output tokens;
- agents, spawned, maximum number live at once, and maximum depth;
- the `spawned` and `parallel` indicators;
- messages, reports and message tokens;
- SQL and doc queries, and tokens by kind;
- invalid and discarded actions;
- cap hits;
- termination reasons;
- lineage edges.

**Reports** count only the manifest's planned runs. Reports made with other weights, a
non-default number of bootstrap resamples, an exploratory suite, or an unverified freeze are
stamped EXPLORATORY. They give per-(class, regime, mode) means, the §8 evaluation with its numbers, the
validity conditions, H2, the per-cell Pareto frontier over (quality↑, money↓, time↓), and
agreement between the developmental organization and the calibrated labels.

## 10. What this experiment cannot show

- **Declared latency model.** Conclusions are conditional on it, especially on the premise that
  concurrency comes only from multiple agents. Single-agent parallel tool calls are out of scope.
- **Narrow setting.** It uses one model, one prompt, one small synthetic world, and no prompt
  caching, which raises per-agent overhead. Results do not transfer to open-ended work.
- **The environment is designed** so that different organizations are optimal. That design is
  the manipulation, not a finding. A positive result shows only that an LLM *can* make these
  decisions economically here.
- **Local vs one-shot decisions are not separated robustly.** The calibration found no I cells.
  Every cross-source narrowing step is a cheap SQL query that children can replicate themselves.
  At the base point, dividing after the SQL does beat the best one-shot division by more than δ on
  T09 and T15 under `urgent`, but those cells are not robustly P across the perturbation grid, so
  they are ambiguous and not I. Exp 0 can therefore test *adaptive vs fixed* organization
  (criteria 1–5), but **not** robustly *local and incremental vs central and one-shot*. The latter is H2, and it is informative only about
  practical behaviour. This is the main recommended extension (EXPERIMENT_STATUS.md).
- **Few designed P cells** (the 4 class-B `urgent` cells). Criteria 2, 3 and 4a rest on them.

## 11. Deviations from the brief, and change log

1. **Added `WAIT`, plus the `wait_for_children` continuation.** Without them, a parent could
   collect results only by busy-polling with paid steps. `WAIT` is **not dormancy**: an idle
   agent already costs nothing, and `WAIT` suspends no accounting and changes no other state.
2. **Simulated time.** Real API latency is noise unrelated to the environment, and LLM calls
   run sequentially.
3. **Added `router`** as an extra, stronger baseline. Its comparison is secondary (H2); see
   item 13.
4. **Two value-of-time regimes per task**, with a shared deadline. They separate
   resource-driven organization from organization driven by task content.
5. **Multi-source QUERY** is processed sequentially. This is the strongest fair form of
   `single`.
6. **`w_coord = 0`**, which avoids double-counting.
7. **Package at the repo root (`devagents/`), not `src/`.** The experiment runs with
   `python -m devagents` and no install. The core uses only the standard library. The
   `anthropic` SDK is imported only by the LLM policy.
8. **No refusal fallback.** A fallback would change the model mid-run, so a refusal is a policy
   outcome, logged as an invalid step.
9. **One compute option.** The `ComputeOption` abstraction is kept, but model choice is not
   tested.
10. **Authority is inert.** Every agent can read every source, and there is no narrowing
    parameter. Tests assert that permissions are inherited and never widened.
11. **Design review before implementation.** A five-lens adversarial review of the first draft
    produced these changes:
    - a single deadline shared by both regimes;
    - the within-regime and dissociation criteria (3a and 3c);
    - margin- and perturbation-stable labels;
    - the criteria check;
    - task-cluster CIs;
    - an event model split into START and COMPLETE;
    - a shared continuation mechanism and a shared cap K;
    - neutral, parallel prompts;
    - a pilot that runs only `single` and `central`;
    - an enforced freeze.
12. **Criteria 4 and 5 test cost and quality separately**, not one fitness scalar. In the
    criteria check, the scalar-fitness version of criterion 4 judged an IDEAL policy
    "supported" in only 1–45% of simulations at R ≤ 10, because Bernoulli quality noise swamps
    the 0.05–0.2 organizational effects. Criterion 4 averaged over all cells had the same
    problem. The decomposed form tests exactly the frontier claim: lower cost where division
    pays, no significant quality loss, and no significant cost loss elsewhere. It keeps 0%
    "supported" for every collapse and heuristic policy.
13. **The `router` comparison moved from criterion 5 to H2.** No cell gives an ideal
    `developmental` a robust advantage over an ideal `router` (§10). Every robust P cell is reached
    equally by a one-shot division, and the base-point gaps on T09 and T15 are not robust. Under
    criterion 5 over all cells, H would therefore be unsupportable even by a perfect agent. Criterion 5 keeps the
    brief's `central` baseline. It drops the brief's "with lower coordination overhead" clause,
    because coordination is already priced inside cost, and dropping it makes the criterion
    fire more easily.
14. **Calibration-driven design changes**, all LLM-free and made before any LLM output:
    - `δ = 0.03`, because 0.05 was infeasible together with gate (d);
    - `V = $0.50`, because at $1 money differences were below δ in `relaxed`;
    - doc processing at 0.1 s/token, because at 0.02 no B-urgent cell was robustly P;
    - dependent tasks widened from 4 to 5–6 docs, because at 4 they were never P;
    - Ivel's plant year set to 1990, so that T09's filter changes the answer;
    - gate (d)'s solo floor of 0.3 added, so that reading beats guessing.

15. **Code review before any LLM run.** A five-lens adversarial review of the implementation, with
    every finding re-verified by a skeptic, led to these fixes:
    - the step cap is enforced at START (ACC-1);
    - the caps count in-flight SPAWNs (ACC-2);
    - WAIT(all) waits for lifecycle notices (ACC-3);
    - undelivered messages are reported honestly (ACC-4);
    - one allocation rule is shared by the oracle and `central` (ACC-5);
    - fees are stamped at START (ACC-6);
    - the pilot token ratio uses visible text only (VAL-1);
    - the reserve rule is disclosed, and the oracle uses the same request overhead (VAL-2);
    - `max_wait_s = 0` means an immediate poll (VAL-4);
    - replies are cleaned before they are re-sent (VAL-5);
    - the pilot CV estimate is unbiased (STAT-1);
    - reports use only planned runs, and resuming is limited to the identical suite (STAT-2);
    - non-default bootstrap sizes are exploratory (STAT-3);
    - H2 is also reported over I cells (STAT-4);
    - the pilot guard covers incomplete logs (STAT-5);
    - the policy configuration is recorded and parity-checked (STAT-6);
    - `verify_frozen` checks calibrated values and the prompt fingerprint (SPEC-3);
    - the catalog shows latencies exactly (SPEC-5);
    - there are 3 retries after the first attempt (SPEC-6);
    - the output schema is identical across modes (SPEC-7).

    The disclosure of the reserve rule lengthened the prompt, so the calibration changed and the
    provisional freeze was redone.

16. **Infrastructure fix at the first pilot freeze: the oracle declares its input bound.** With the
    pilot's r = 2.0052, `freeze --pilot` raised `ReserveViolation` at the grid point
    r = 1.25 × 2.0052 = 2.5065. The oracle is priced at estimator tokens × r (§7.1), but the §3.3
    bound allows 1 token per 2 new characters, which is about r ≤ 2. On T01's solo read that is
    8,302 tokens against 6,623 allowed, beyond the 1,000-token overhead. The runtime now reserves
    the larger of its bound and a bound the policy declares (§3.3). `ScriptedPolicy` declares
    exactly the input it will report, and `LLMPolicy` declares none, so the live reserve is
    unchanged. Over the full grids for base r = 1 and for the pilot's base, all 8,752 oracle runs
    that the previous code completed have identical simulated metrics. The 464 runs it aborted,
    all at r = 2.5065, now complete. No prompt, task, constant, label rule, gate, criterion or
    fitness rule changed.

**Change log** (constants and freeze):

- *Provisional freeze 1, made without a pilot because no API credentials were available:* gate
  passed with no repair steps, R = 3 (from p = 0.9 and cv = 0.25). Superseded.
- *Provisional freeze 2, after the code review:* the disclosed reserve rule lengthened the prompt,
  and mechanical repair took one step (`doc_tok` 0.100 → 0.105 s/token). R = 3. See
  EXPERIMENT_STATUS.md for the sha. The main run refuses a provisional freeze.

## 12. Deliverables and freeze

- `README.md` explains the hypothesis, how to run the experiment, how to read the results, and
  what the experiment cannot conclude.
- `EXPERIMENT_STATUS.md` is append-only. It records what is implemented and tested, the freeze
  hash, the pilot and main run ids, the validity outcomes, and the §8 verdict with its numbers.
- Every run's `RUN_STARTED` event carries the audit record, the prompt fingerprint and the hash
  of the frozen file.
