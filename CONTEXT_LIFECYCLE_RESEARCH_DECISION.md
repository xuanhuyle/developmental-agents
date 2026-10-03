# Context lifecycle: research decision

**Date:** 2026-10-03.
**Status:** research decision. It is not an experiment, a pre-registration or a continuation of the closed program.
**Repository state when written:** HEAD 6d1c6e4, 239 tests passing, `python -m devagents.gate0 verify` ok.
**What was spent:** zero API calls. No experiment code was written into the repository, and no historical
specification or result was changed.

**The question examined.** Can a persistent agent *learn through experience* how to organize its own finite
cognition over time? That covers deciding what to keep active, compress, archive, park, resume, branch, preserve as
a specialization, merge back or retire.

## Decision: NO-GO

Stop this line as posed. No paid experiment is proposed, and none is authorized. Re-entry is possible only as a new
proposal under postmortem rule 7, on a substrate that first passes the zero-API gate R0 (§9.1).

**Why, in five points:**

1. **The literature already covers most of the question.**
   - Learned within-episode branch, fold, compress and archive exist: Context-Folding/FoldGRPO, MemexRL and others.
   - Learned memory CRUD exists: Memory-R1 (README; the paper was not read) and its successors (search snippets
     only).
   - Outer-loop learned memory designs exist: ALMA, MemEvolve.
   - Prompted lifecycle tools exist: Letta.
   - *Online, within-lifetime* learning of an organization policy is reported, by a bandit (MemCon) and by LLM
     reflection (AdaMem). This rests on their abstracts; the bodies were not read (§3.10).
   - What may remain untested is a methods comparison (§3.11): LLM-mediated learning against simple learners given
     identical feedback, with a distillation test. This holds only if ContextEvo (known from two list snippets) and
     the bodies of MemCon and AdaMem (abstracts only) do not already contain it.
2. **The strongest null wins against learning within a lifetime.** No organization learned *within a lifetime* beat
   "store everything immutably, retrieve well, add fixed typed side-indexes" on any dataset that could be computed.
   - Where anything beat it, fixed structure, or a population-level model trained on *other* lifetimes, was enough.
     On BEAM-1M a cross-fitted population pin classifier beat the null by +0.028 to +0.047 (95% CIs above 0).
   - That is ordinary offline supervised learning, not learning through experience.
   - The exception is aggregation beyond the read budget, which nothing tested here closed (§4.1).
3. **On every substrate where it was measured, almost nothing is left to learn within one lifetime.**
   - Those substrates are LoCoMo, BEAM-1M/10M, the PM-Bench generator and git streams. Learning inside a lifetime
     adds at most +0.008 over a population prior fitted on other lifetimes, and on BEAM the gain is negative.
   - The large oracle headroom that does exist is knowledge of future needs; on LoCoMo it was shown to be about
     *when*, not *whether*. No feedback channel examined here reaches it (§4.2).
   - The other reachable substrates were rejected in §6:
     - uniform or stationary demand (AgingBench, LifelongAgentBench);
     - templated truth (Memora);
     - fixed routing solves it (PrefEval);
     - no lifetime structure (Supersede, MQuAKE).
4. **The alternative explanations cannot be separated at affordable scale** (§8.2). "Learning the organization"
   versus "learning the task distribution" is ill-posed for retention, because the optimal policy *is* a demand
   model. Own-experience versus population-prior effects would need 128-1,133 lifetimes. No natural source examined
   here offers more than 41 valid ones, and the open-ended one (git) has only 4-12 after the model cutoff. Synthetic
   lifetimes make the designer's chosen regime the manipulation, which is Gate 0's failure.
5. **Every conditional LLM run designed for a substrate reachable here** (E-PARK-L, BEAM-L, git) either cannot
   produce a positive, is mostly inconclusive, or is decisive only toward a predicted negative (§12.2). E1 (§9.2) can
   be reached only through an R0 pass, and no substrate has one.

**Evidence base.** All numbers labelled [COMPUTED] are exploratory, zero-API analyses run in this session on
third-party data: LoCoMo, BEAM, PM-Bench weeks, PrefEval, MQuAKE, git commit streams, AgingBench, Memora and
LifelongAgentBench. Their scripts live in the session scratchpad and are **not** committed (Appendix A). They are
proxies (evidence sufficiency, hit rate, F1 of a deterministic actor), not measured LLM accuracy. Every threshold in
this session was set after those data were examined. The decision therefore rests on results that hold for any
smallest effect of interest at or above 0.01, the lowest any design here proposed. Those results are absolute
ceilings, wrong-signed intervals, upper bounds of at most +0.007, and properties of the data. The decision would
not survive a smallest effect of interest below 0.008.

**Evidence labels:**
- **[REPO path:line]**: this repository;
- **[CODE]**: a cloned third-party repository;
- **[PAPER]**: a paper PDF that was read;
- **[README]**: a project's own documentation;
- **[ABSTRACT]**: a full abstract read from an arXiv-listing mirror or a conference paper list;
- **[SNIPPET]**: a search snippet or a third-party list summary, not re-verified;
- **[DATA path]**: a third-party dataset file inspected directly;
- **[UNVERIFIED]**: recalled from memory, with no source read;
- **[COMPUTED]**: this session, offline;
- **[INFERENCE]**: our reasoning.

**Access.** arXiv, openreview and Hugging Face were blocked from this session, and the web-search quota ran out
partway through (§3, Appendix B).

## 1. Inherited evidence

### 1.1 What was tested, and what it showed

| Line | Question actually tested | Outcome | Where |
|---|---|---|---|
| Exp 0 | One resource-aware lifecycle policy: does it stay single when division does not pay and divide when it does? | Calibration failure after the live pilot; no hypothesis test | `EXPERIMENT_STATUS.md:156-180` |
| 0b | Same, after rescaling the economics | UNINFORMATIVE (check (v) failed); developmental and router made 0/90 SPAWN attempts each | `EXPERIMENT_STATUS.md:208-223` |
| 0c Stage 1 | Same unchanged treatment under a live-validated division benefit | NO-GO (criterion 2): central parallel 12/12; developmental parallel 0/12, spawned 0/12 | `EXPERIMENT_STATUS.md:273-291` |
| Postmortem | What to do next | Primitive SPAWN line closed; §10 stopping rules | `EXPERIMENT_0C_POSTMORTEM_AND_NEXT_DECISION.md:417-452` |
| Gate 0 | Can a small credible environment show organizational adaptation beating strong precommitted alternatives? | FAIL, zero API calls; program stops | `GATE_0_REPORT.md:1-44`; `data/gate0/audit.jsonl` (6 entries; `python -m devagents.gate0 verify` ok) |

Exp 0, 0b and 0c concern one lever: a static t0 decision to divide work (SPAWN) among concurrent readers under a
declared latency model. Gate 0 added offline post-reveal adaptation over two levers, concurrent reading and release,
in the same runtime and cost model (`GATE_0_REPORT.md:448-450`). In the closed line no context was ever under pressure. Capacity was 1,000,000 tokens
(`devagents/runtime/resources.py:58,61`; `data/exp0b/frozen.json:2526`), and a probe run in this session found that a single agent re-reading
ten documents per step runs out of its $1 budget after 8 steps at about 37k input tokens. Reaching the window limit
would take 194 steps and about $389 [COMPUTED: read-only probe over `devagents.runtime`]. Nothing persists across
tasks, and the simulator has no eviction, summary, archive, retrieval, park or resume.

### 1.2 The conclusions this decision inherits

Each was checked against the documents. None is contradicted. Three (a, d and e) need a narrower reading than their
usual paraphrase.

| # | Conclusion | Status | Scope note |
|---|---|---|---|
| a | The primitive SPAWN line is closed | Confirmed | Closed "as tested": one model, effort low, neutral presentation, organization implicit (`EXPERIMENT_0C_POSTMORTEM_AND_NEXT_DECISION.md:21-26, 76-78`). Rule 1 forbids reopening it by prompt, effort or model. |
| b | 0b/0c did not test adaptive organization as a trajectory | Confirmed | "Nothing tested so far gave organization any reason to change after execution began" (postmortem:28-29). There were no I cells. |
| c | Gate 0 environments were compressible into simple contingent rules | Confirmed, and partly by construction | One-line rules reproduce A\* within 0.0065 (A) and exactly (B) (`GATE_0_REPORT.md:23-28`). This was forecast before evaluation (`GATE_0_SPEC.md:221-226`). In any fully specified simulator a deterministic contingent controller implements the oracle. |
| d | Deliberation is costly | Partly | Confirmed inside the simulator: 0.147 fitness per urgent high-effort checkpoint, deliberation power 0.000 (`GATE_0_REPORT.md:306-315`). But it rests on a declared output latency, "an assumption, not a measurement" (postmortem:87-88), and more than half of the 0.147 is the ratio of call price to task value ($0.056 / $0.696), which was a design choice. "Nothing here is evidence about an LLM" (`GATE_0_REPORT.md:265`). |
| e | An LLM adds no scientific value if a simple controller with the same information reproduces it | Partly | It rules out any advantage claim (`GATE_0_SPEC.md:555-558`). The documents keep a narrower claim open: autonomy, i.e. matching the controller *without being given its specification* (`GATE_0_SPEC.md:123-129`). |
| f | Strong conventional baselines are mandatory | Confirmed | The most conventional baseline of all, single-agent parallel tool calls, was excluded by design (`SPEC.md:475-476`). |
| g | Organization must earn its cost | Confirmed | Each child cost about 0.043-0.045 fitness (`GATE_0_REPORT.md:313`; `GATE_0_SPEC.md:220`). Relaxed cells had zero value (`GATE_0_REPORT.md:20`). |
| h | Adaptive organization is not shown to be impossible | Confirmed | Postmortem D and E (`:76-80`). The Gate 0 negative covers two templates, two levers, one change point, one round and one cost model (`GATE_0_REPORT.md:448-450`). |

### 1.3 Behavioural priors that transfer, and how far

1. **The one model tested, at effort low with neutral presentation, did not use an optional organizational
   action.** It made no SPAWN attempt in 192 voluntary opportunities: 0b `developmental` 90, `router` 90, and 0c
   `developmental` 12 (postmortem:23; `EXPERIMENT_STATUS.md:220, 278`). When forced, it took the cheapest legal form.
   In every 0b main and pilot run `central` made exactly one child, and in the P cells that child read all 6 or 8
   documents (`EXPERIMENT_STATUS.md:222-223`; `EXPERIMENT_0C_DECISION.md:57-58`).
2. **Outside evidence points the same way.**
   - In PM-Bench, 7 of 8 models never enabled the optional heartbeat [CODE: PMBench run logs, `heartbeat_enabled`].
   - The Kimi K2.5 report names the same failure "serial collapse ... the orchestrator defaults to single-agent
     execution". The report mitigates it with a designer-shaped instantiation reward [PAPER: Kimi K2.5 tech report PDF in the
     cloned `MoonshotAI/Kimi-K2.5` repository, p.5].
   - Context-Folding states that outcome reward alone was "insufficient for learning effective context folding"
     [PAPER v1 p.5].
3. **What does not transfer.** The closed line never put the context window under pressure. It therefore says
   nothing about whether a model under real window pressure organizes its context. What it does say is that
   optional actions go unused when no constraint makes them pay, and that "using the action" and "the action paying" must be
   measured separately (postmortem:103, the "demand" risk).

### 1.4 Process facts that constrain this proposal

- **The program is stopped.** Postmortem §10 rule 2 fired: "Gate 0 fails → the program stops, with zero API calls"
  (postmortem:423). The remaining live budget is zero, apart from the report-only tripwire of rule 6: one unchanged re-run of the frozen
  0c Stage 1 on a new major model version (`GATE_0_REPORT.md:414-419`; postmortem:431-436).
- **This document is not a continuation.** Rule 7 says "a different testbed would be a new proposal with its own
  justification, not a continuation" (postmortem:437-438). Rule 5 forbids rescue knobs: presentation, examples,
  controller variants, model, effort, economics. Nothing here re-asks the SPAWN question, re-runs a 0b/0c cell, or
  uses Gate 0's worlds. It inherits method, plus the behavioural prior in §1.3, which is used only as a prior.
- **What "a new proposal" has to do**, inferred from the program's practice; the documents do not define it. It
  needs:
  1. a different question and lever;
  2. its own justification, not "the old testbed failed";
  3. a separate pre-registration, with no pooling of data and no reporting as support for H;
  4. its own offline gate, with criteria hashed *before* any environment or data is examined (Gate 0 broke this
     order; `GATE_0_SPEC.md:382-385`);
  5. no inherited budget, and explicit user approval for any paid call.
- **Ledger hygiene items found while reconstructing**, disclosed here and not fixed:
  - Commit 6d1c6e4 edited the Gate 0 entry of `EXPERIMENT_STATUS.md` in place after 59977f0 had appended it, although
    that file declares itself "Append-only" (`EXPERIMENT_STATUS.md:3`). It was not the first such edit: b76cbcd
    rewrote the 2026-09-29 pilot entry about 54 minutes after 520947a appended it. Both were corrections made shortly
    after the append. They were still in-place edits, and each should have been an appended erratum. The status note
    that accompanies this document records them as errata.
  - The sha256 of `results/exp0c/stage1/stage1_decision.json` is still unrecorded
    (`EXPERIMENT_STATUS.md:292, 324-326`).
  - `README.md` is stale: it says 100 tests and a provisional freeze (`README.md:60, 118`). The "Implemented"
    section of `EXPERIMENT_STATUS.md` still says 109 tests (`EXPERIMENT_STATUS.md:37`). The suite has 239 tests.
  - Recorded live API calls total 1,068: 80 in the Exp 0 pilot (`EXPERIMENT_STATUS.md:157`) and 988 in the 0b main
    run (`EXPERIMENT_0C_DECISION.md:62`). The 0c call counts and the actual dollar spend of every live run were never
    recorded.

### 1.5 Methodological inheritance (binding on anything proposed below)

1. Pre-register before any output. Pin treatment identity by hash. Use an append-only, hash-chained audit. Allow
   at most two rounds. Never change a threshold after output.
2. Fix baselines by construction. Never let the LLM choose a baseline's organization; 0b failed that way.
3. Include the strongest conventional baseline, and a no-LLM controller with the same information.
4. Charge deliberation and organization overhead to the arm that incurs it, and score net of it.
5. Never present simulator-derived power as empirical power.
6. Expect compressibility. Test for it before spending money, and report it as a result if it holds.

## 2. Revised question

### 2.1 From first principles

The conceptual form is

(M[t+1], O[t+1]) = F(M[t], O[t], experience[t], feedback[t]),

where M is what the agent has and O is how it is organized. Read literally, almost every memory system satisfies it:
any system that writes notes updates M, and any system with a reflection step updates something. To make it a
research question, each symbol has to be pinned to something that can be measured. Each must also be split into the
part that needs judgement and the part that is bookkeeping.

**State.** A persistent agent has six stores. They are distinguished here because the lifecycle verbs act on
different ones, and confusing them is how "organization" becomes unfalsifiable. None of them is an agent.

| Store | What it is | Mutable? | Who maintains it |
|---|---|---|---|
| Immutable evidence log L | Every observation, action, model call and organizational operation, with timestamp and provenance | Append-only, hash-chained | Infrastructure |
| Data storage | External artefacts the agent works on (files, documents, tool state) | Mutable by tools | Infrastructure plus tools |
| Episodic memory | Indexed views of specific past events, all derived from L and pointing back into it | Derived, rebuildable | Index by infrastructure; *what gets an episodic summary* is policy |
| Semantic memory | Abstractions: current-state beliefs with validity intervals, lessons, procedures | Derived, versioned | Content by LLM; supersession bookkeeping by infrastructure |
| Unfinished intentions | Typed records (action, resumption condition, context pointer, expiry) | Versioned | Condition evaluation by infrastructure when machine-checkable, by LLM grounding when semantic; *registration* is policy |
| Active working context A | The tokens the next model call sees, \|A\| ≤ B | Rebuilt per call | Composition is policy; assembly is infrastructure |

A "persistent specialized context" is not a seventh store. It is a named, durable *selection* over the stores above:
a namespace of semantic and episodic items plus a standing instruction, loaded together into its own model call.
See §2.4.

**Organization O** is the policy that, at each event, decides:
- **D1. Composition:** what goes into A, and at what fidelity (verbatim, summary, pointer).
- **D2. Derivation at write time:** which derived items to create (summaries, beliefs, supersession links, index
  cues).
- **D3. Intention registration:** what to register as unfinished, under which resumption condition, and when to
  retire it.
- **D4. Partitioning:** whether to run part of the work in a separate context (branch); what to give it and what to
  fold back; whether to keep the partition (namespace).

**Learning F_O** is whatever changes the policy O, as opposed to the content of M, as a function of the consequences
of the agent's own earlier D1-D4 decisions.

### 2.2 Infrastructure, not intelligence

These functions are deterministic in every design below, and no result may be credited to them:

| Function | Deterministic implementation | Why it must not be "intelligence" |
|---|---|---|
| Timestamps, sequence, provenance | Log fields; each derived item records the log entries it came from | Correctness must not depend on the model remembering where something came from |
| Logging and immutability | Append-only, hash-chained JSONL, as in `devagents/gate0/audit.py` | Makes every compression reversible and every decision auditable |
| Versioning of memory and policy | Each policy version is a log entry, and diffs are applied deterministically | Prevents the "context collapse" of wholesale LLM rewrites (ACE warns of it; DC on AppWorld fell from 18,282 to 122 tokens [SNIPPET, prior pass]) |
| Wake-ups and timers | A scheduler evaluates time and event conditions | A scheduler needs no learning for timing. On PM-Bench, privileged clock triggers alone reach 45.7% Set-F1 at precision 1.0; adding privileged cue detection and channel polling reaches 100% [COMPUTED] |
| Storage, indexing, retrieval mechanics | BM25 and/or dense index over L and the derived stores | The retriever is a baseline, not a mechanism |
| Budget accounting | A token, call, latency and money meter, generalizing the money-only `Ledger` in `devagents/runtime/resources.py` (integer micro-dollars, conservation checked) | Resource claims must come from a meter, not from the model |
| Applying an operation | `apply(op, store)` is code; the LLM only proposes `op` | Lets operations be audited, replayed and counted |
| Garbage collection of expired items | Validity intervals and expiry fields | Expiry by date is not a judgement |

**What remains for intelligence** is narrower than the lifecycle vocabulary suggests:
- (i) predicting future need under semantic uncertainty (D1, D2);
- (ii) constructing representations whose value is the cues and integrations they create (D2);
- (iii) grounding semantic conditions: does this event satisfy that intention? (D3);
- (iv) deciding what a partition needs and what it should return (D4);
- (v) **learning**: attributing a later failure to an earlier organizational decision and generalizing the
  correction (F_O).

Items (iii) and much of (ii) are *grounding*, done per call by a frozen model. They are not organization learned
through experience. Only (v) is the question posed here, and (i) is where it would show.

### 2.3 What an immutable log does to the lifecycle vocabulary

If L is immutable and retrievable, then ARCHIVE, COMPRESS and RETIRE are never destructive:
- ARCHIVE is eviction from A;
- COMPRESS is eviction plus a derived summary;
- RETIRE is eviction plus a validity end, so that retrieval stops surfacing the item.

Eviction is therefore not costly in itself. It costs something only through four channels:
1. **Cue failure.** When the item is needed, nothing in A, in the query or in a trigger leads anyone to retrieve it.
   Retrieval only helps an agent that knows to ask.
2. **Retrieval cost.** Extra calls, tokens and latency to recover the item.
3. **Interference and staleness.** Items in A, or retrieved, that mislead: superseded facts, distractors.
4. **Integration cost.** Re-deriving a current state from many scattered items on every use.

**Consequence.** A lifecycle policy can earn value only through these four channels. A benchmark in which every
question carries its own retrieval cue, and nothing is stale, closes channels 1 and 3. On such a benchmark,
store-everything plus retrieval should dominate any lifecycle policy, learned or not, and Mem0 v2's move to ADD-only
plus hybrid retrieval [README: mem0 changelog; vendor claim] is what that predicts. Channel 1 in its pure form is
prospective memory: no question arrives to cue the retrieval.

### 2.4 Is SPECIALIZE distinct from a named persistent context?

**No, not as a primitive.** Mechanically, a persistent specialization is three things:
- a namespace, i.e. a persistent named selection of semantic, episodic and procedural items;
- a standing instruction;
- a separate model call that loads them.

**Where its claimed benefits come from:**
- *Isolation from interference.* This is FOCUS by scoped retrieval into one context.
- *Parallel or extra capacity.* These are additional context windows and compute, which §7 charges.
- *Prompt-cache economics.* A stable prefix per namespace. This is a pricing effect: cache reads cost $0.20/MTok
  against $2-4/MTok uncached input for Sonnet 5.5 and Opus 5.5 [README: Anthropic API reference bundled with Claude
  Code, cached 2026-09-25].
- *Accumulated procedure.* This is a namespaced playbook.

**Where it could be distinct.** Only in its decisions:
- when to create a namespace;
- when routing to it beats loading it into the main context;
- when two should MERGE;
- when one should RETIRE.

Those decisions are D4 with persistence. They can be tested only after D1-D3 show that learning matters at all, and
their benefit is confounded with extra windows unless every arm is held to equal total tokens. **SPECIALIZE, MERGE
and whole-context RETIRE are therefore out of scope for the first experiment.** BRANCH and FOLD are also out of
scope as learning targets: learning them within an episode is published (§3).

### 2.5 The revised question

> **RQ.** In a persistent agent whose raw experience is kept in an immutable, retrievable log, can the policy
> that decides what to hold active, what to derive at write time, and what to register as unfinished be improved
> by learning from the *delayed consequences of the agent's own earlier organizational decisions* by more than:
> - the same agent with that policy frozen;
> - simple learning controllers given identical feedback;
> - the best fixed policy chosen with hindsight?
>
> The comparison is at equal active-context budget and equal total compute, in a regime the designer did not
> construct to favour the answer.

It is answered by a ladder of conditions. Q0 and Q2 are necessary for Q3-Q5. Q1 is necessary only for claims about
non-stationary demand. The first three rungs can fail cheaply:

| Rung | Question | Can be tested without paid calls? |
|---|---|---|
| Q0 Headroom | On natural longitudinal data, under a binding active budget, does store-all + retrieval + deterministic triggers leave a measurable gap to an evidence oracle, and through which of the four channels? | Yes |
| Q1 Non-stationarity | Within that gap, does the hindsight-best fixed policy change over the agent's lifetime? If not, learning has nothing to track beyond what a one-time choice would capture. | Yes |
| Q2 Simple learnability | Do simple online learners using the same delayed feedback close the gap? | Yes |
| Q3 Learning | Does experience-driven revision of the policy beat the frozen policy? | No |
| Q4 LLM-specificity | Does LLM-mediated revision beat the simple learners, without being reproduced by a pre-registered distilled controller on held-out data? | No |
| Q5 Net value | Does it pay net of its own reflection and organization overhead? | No |

**How to read the outcomes:**
- Only Q3, Q4 and Q5 positive together support the hypothesis in its interesting form: an LLM agent learning to
  organize its own cognition.
- Q3 positive with Q4 negative answers a weaker question: "online retention learning works, and it is ordinary
  cache or memory management". That is a legitimate and useful result, but it is not the hypothesis, and it must be
  reported as the weaker result.
- If Q0 or Q2 kills the line, no paid call is justified. If Q1 fails, only the non-stationarity claim is dropped
  (R0.7).
- **A refinement forced by §8.2 (U1).** For D1 and D2, "learns the organization rather than the task distribution"
  is not a well-posed contrast: the optimal retention policy *is* a model of demand and of one's own reader. RQ is
  therefore tested only in its Q4 form, LLM-mediated learning against a plug-in learner with the same feedback. That
  is never claimed as "organization, not demand".

### 2.6 What this is not

- **Not content learning.** Writing better lessons into memory is ACE, Dynamic Cheatsheet, ReasoningBank and AWM
  territory. ACE (as released) and ReasoningBank apply ADD only [CODE]. Dynamic Cheatsheet and AWM regenerate their
  whole memory with an LLM on each update [CODE], which is the failure mode ACE warns against.
- **Not within-episode RL of context operations.** That is Context-Folding/FoldGRPO, MEM1, MemAct, MemexRL and
  AgeMem.
- **Not outer-loop search over memory designs across fresh runs.** That is ALMA, MemEvolve and MemSkill.
- **Not a prompted agent that has the operations.** That is MemGPT/Letta.
- **Not a test of whether a frozen model *uses* lifecycle actions.** That is the closed line's question; §1.3 gives
  the prior.

## 3. Adjacent-work comparison

**Access.** arXiv, openreview, Hugging Face and most paper hosts were blocked from this session, and the web-search
quota ran out partway through. Sources were obtained as follows:
- code from GitHub clones;
- papers from PDFs mirrored in GitHub repositories (Context-Folding v1, Evo-Memory, MemAct, the Kimi K2.5 report, and
  MemGPT v2 from a Letta release tag);
- everything else from READMEs and earlier search snippets.

Each entry asks two things: which part of the lifecycle exists, and which part is untested *relative to RQ*. Labels
are as in the header.

### 3.1 Context-Folding / FoldGRPO (Sun, Lu, Ling, Liu, Yao, Yang, Chen; arXiv 2510.11967)

Read from paper v1 (13 Oct 2025, via a GitHub mirror) and from `sunnweiwei/FoldAgent` at 58a2d69.

**Semantics** [PAPER p.3-5; CODE `agents/fold_agent.py:149-207`, `tool_spec.py:240-279`]
- `branch(description, prompt)` forks a sub-context that inherits main's full context plus a role template.
- `return(message)` *folds* it: every branch token is discarded and main keeps its branch-call turn plus the return
  message.
- The design is depth 1 and sequential, and branches cannot finish or branch.
- The fold is irreversible and all-or-nothing. Folded content cannot be retrieved by the agent; it survives only in
  logs.

**Learned vs hard-coded**
- *Learned in weights by RL* [PAPER; CODE]:
  - when to branch;
  - the branch prompt;
  - the work inside the branch;
  - when to return;
  - what the return message says.
- *Hard-coded* [CODE]:
  - the operator;
  - the caps (10 branches in the scripts, 5 by default);
  - the forced-return prompt;
  - heavy role scaffolding. For example, "Your primary function is planning and synthesis, not direct research"
    (`prompts.py:227`); the SWE phases are pre-tagged `[BRANCH]`; and at HEAD a one-shot demonstration of the whole
    cycle is included.
- Before any RL the base model already branches 3.51 (BrowseComp-Plus) and 3.05 (SWE) times per task
  [PAPER Table 2]. So RL tunes a behaviour the scaffold induces; it does not discover it.

**Training signal** [PAPER p.5]
- Outcome reward R ∈ {0, 1}. The paper states it alone "is insufficient for learning effective context folding".
- So three hand-designed process rewards are added:
  - an *unfolded-token penalty*: −1 on main-thread tokens once main exceeds 50% of the working context;
  - an *out-of-scope penalty*: −0.2, judged by GPT-5-nano;
  - a *failure penalty*: −1 on failed tool-call turns.
- Outcome-only GRPO raised accuracy but made organization worse:
  - BrowseComp-Plus main length 12,195 → 22,285 tokens, Finish 0.806 → 0.738;
  - SWE Finish 0.781 → 0.612 [PAPER Table 2].
- [CODE `verl/trainer/ppo/core_algos.py:422-437`] The released advantage differs from the paper's.
- [CODE git, 85391fa → 0aa8ff1] A mask bug present from January to May 2026 would, by our reading, have given every
  token the group-max advantage [INFERENCE, not executed].

**Results** [PAPER Table 1], pass@1:

| Benchmark | ReAct 32K | ReAct 327K | Folding, no RL | Folding + GRPO | Folding + FoldGRPO |
|---|---|---|---|---|---|
| BrowseComp-Plus (N=150) | 0.286 | 0.478 | 0.420 | 0.567 | 0.620 |
| SWE-Bench Verified (N=500) | 0.436 | 0.552 | 0.492 | 0.564 | 0.580 |

- *Context savings.* The main trajectory is about 8K tokens "while processing over 100K in total", described as an
  "active context 10× smaller" [PAPER p.1, p.8].
- *Compute.* Tool calls rise from 12.9 to 19.2 (BC) and 72.8 to 96.5 (SWE).
- *Significance.* We infer single runs. The unpaired SE of the FoldGRPO−GRPO gap is about 0.057 (BC) and 0.031 (SWE),
  so +5.3 and +1.6 points are under 1 SE [INFERENCE].
- *Internal inconsistency.* The paper's "+7.7% on BrowseComp" matches neither the absolute nor the relative gap in its
  own Table 1.

**Persistence, dormancy, lifetime** [CODE `fold_agent.py:70-108, 149-191`]
- Branches are ephemeral and are never dormant.
- Main is suspended during a branch only as call/return. That is a fixed implicit resumption condition, not a PARK.
- A folded branch is never re-entered.
- Environment and contexts are rebuilt for every task. Nothing persists across tasks except weights from offline RL
  (50 steps).
- The lifetime topology is a fixed star: main plus sequential depth-1 branches.

**Exists.** Learned BRANCH, FOLD and fold-time COMPRESS within one episode, trained offline over i.i.d. episodes.

**Untested relative to RQ:**
- anything beyond one episode;
- outcome-only learning of organization (the paper's own evidence is negative);
- ARCHIVE with retrieval;
- PARK, and resumption of folded work;
- persistence of any context;
- non-stationary demand;
- ablation of the scaffold itself.

### 3.2 PM-Bench (arXiv 2607.12385; authors Genglin Liu and Saadia Gabriel per search snippets [SNIPPET]; code by genglinliu)

Read from the `PMBench` code, data and released run logs. The paper body was inaccessible.

**What it is**
- One synthetic week: 80 steps and 83 intentions. Each intention has a time, narrative-cue or hidden-channel
  resumption condition, plus reschedules, overrides and cancellations.
- The agent selects due actions from a menu and may query channels [CODE `sim/pm_bench.py`].

**Lifecycle coverage**
- PARK/RESUME is the benchmark's object, but parking is always imposed by the user's text. The agent never parks its
  own work or chooses its own condition [CODE; INFERENCE].
- Nothing is learned. Every cell is a single frozen-model run.

**Findings that bound RQ** [COMPUTED: scripted policies through the unmodified scorer]

| Policy | Set-F1 |
|---|---|
| Clock scheduler with privileged registered times | 45.7% |
| + privileged narrative-cue detection | 89.8% |
| + privileged hidden-channel matching, polling all 11 channels every step | 100% (TP 81 / FP 0 / FN 0) |

- Storage and timing are therefore solved by infrastructure. The residual difficulty is natural-language
  *registration* and semantic *matching*: grounding, not organization.
- The whole week is about 17-18.5k tokens, so there is no capacity pressure [INFERENCE from code].
- Queries are free in F1.
- Misses have no downstream consequence; each day's state is rebuilt [CODE `pm_bench.py:1757-1786`].
- 7 of 8 models never enabled the optional heartbeat [CODE logs].
- Defects:
  - a ground-truth fallback (`pm_bench.py:1944-1958`) substitutes the true due set after invalid output;
  - one released run (Qwen3-8B heartbeat-proactive, 71.9%) falls to 16.1% when signature steps are stripped
    [COMPUTED].
- The PIS follow-up (deterministic lifecycle plus LLM grounding, nothing trained) reports 82.9% [SNIPPET].

**Untested relative to RQ:**
- agent-initiated PARK with an opportunity cost;
- a binding budget;
- delayed consequences;
- any learning;
- multiple weeks and seeds.

### 3.3 Memory-R1 (Yan et al., arXiv 2508.19828) and its neighbours

Sources: the official README (no code has been released), a third-party re-implementation, the LoCoMo data file, and
snippets. The paper PDF was not read.

**What is learned**
- A Memory Manager learns ADD/UPDATE/DELETE/NOOP over a flat fact bank, and an Answer Agent learns to filter
  retrieved memories. Both use PPO or GRPO from an exact-match outcome reward [README; SNIPPET].
- Training is on 152 QA, which we infer is one LoCoMo conversation [DATA `locomo10.json`; INFERENCE].
- The manager acts on GPT-4o-mini-built memory snapshots, not on its own accumulated bank [SNIPPET].
- Each reward is immediate; it is not delayed.
- There is no budget, and the policy is frozen at deployment.

**Reported gain** [README]
- LoCoMo with LLaMA-3.1-8B: F1/B1/J 45.0 / 37.5 / 62.7, against Mem0 at 30.4 / 22.2 / 45.7.
- Mem0's own paper reports J 66.9 with GPT-4o-mini [SNIPPET]. So the baseline is weak relative to that.

**Neighbours**
- Successors attack delayed credit [SNIPPET]:
  - Memory-R2, with local re-rollouts over the same ADD/UPDATE/DELETE/NOOP set;
  - Mem-T, with operation-tree hindsight credit;
  - MemBuilder, with synthetic session-level questions for dense rewards.
- Mem-α trains typed core/episodic/semantic writes under a memory-size penalty [README `Mem-alpha/README.md:120-146`].
- Mem0 v2 made its automatic add() path ADD-only (caller-level update and delete remain) and added hybrid retrieval.
  It claims LoCoMo 71.4 → 91.6 and LongMemEval 67.8 → 93.4 [README, vendor claim]. The change was bundled with a retriever and a default-model change, so it does
  not isolate the effect of dropping UPDATE/DELETE.

**Exists.** Learned write-gating and single-entry UPDATE/DELETE from outcomes, trained offline.

**Untested relative to RQ:**
- credit from the agent's *own* trajectory over long delays (successors approach this);
- a hard active budget;
- non-destructive states (archive, park);
- online, in-lifetime learning;
- whether the writer or the reader carries the gain.

### 3.4 ACE: Agentic Context Engineering (arXiv 2510.04618)

Sources: code (`ace-agent/ace`, `ace-appworld`) and the released artefacts. The paper PDF was unreadable.

**How it works**
- A Generator, a Reflector and a Curator grow a sectioned "playbook" from task feedback.
- In the released code only ADD is applied [CODE `playbook_utils.py:96-216`; `adaptation_react.py:340-341`].
- Helpful/harmful counters exist in the finance pipeline only, and no rule consumes them.
- The token budget is advisory text.

**Released AppWorld online playbook** [COMPUTED: diff over the released snapshots]
- Across the snapshots in the initial commit it grew from 8 to 398 bullets with *zero* edits and *zero* removals. The
  released "trained" file is the 359-bullet task-150 snapshot.
- 266 of the additions came in the first 30 tasks.
- At about 33-36k tokens, it never approached the advisory 80k.

**Collapse warning.** The paper warns of "context collapse" under whole-context rewrites. The Dynamic Cheatsheet case
on AppWorld went from 18,282 to 122 tokens and from 66.7% to 57.1% [SNIPPET, prior pass].

**Exists.** Experience-driven *content* learning by LLM, with deterministic append, persistent and online.

**Untested relative to RQ:**
- any learned RETIRE, MERGE, ARCHIVE or PARK;
- a binding budget;
- drift that makes old items harmful;
- delayed feedback;
- whether the *curation policy* itself improves (the Curator prompt is fixed).

**Bearing on our design.** ACE is the strongest evidence that, on its benchmarks, "append distilled lessons" is
enough. It is also evidence that a lifecycle has to be applied as deterministic deltas, never as wholesale LLM
rewrites.

### 3.5 MemGPT / Letta, and sleep-time compute

Sources: MemGPT paper v2, read in full from a PDF in Letta release tag 0.3.25 [PAPER]; `letta-ai/letta` (archive
branch), `letta-ai/letta-code`, `letta-ai/sleep-time-compute`.

**What exists**
- Every lifecycle verb exists as a *prompted* LLM tool around an immutable recall log [CODE]:
  - core-memory edit, archival insert and search, recursive summarization triggered at a fixed fraction of the
    window;
  - Wake: time-conditioned self-resumption, i.e. PARK with a clock condition;
  - fork;
  - a reflection prompt that names archiving to ARCHIVE.md, tier moves between core and deferred memory, and skill
    extend/deprecate/split (`reflection-v2.md:47, 104-127, 166-167`).
- Context Doctor is a user-invoked, prompted procedure that attributes behavioural failures to stale memory,
  compaction or retrieval, then repairs content. It is unevaluated.
- Sleep-time compute precomputes re-representations before queries arrive. The claim that its benefit tracks query
  predictability is recalled from memory only; the paper could not be accessed [UNVERIFIED]. The released code lacks its own test-time-only baseline [CODE].
- "Mod learning" is a score-driven search over harness plug-ins. It is user-invoked and spec-driven.

**What is not learned.** In every inspected codebase, thresholds and cadences are hand-set constants, and decisions
are zero-shot prompted. Letta frames self-editing as "learning in token space", and concedes that such updates
"will often not have an explicit reward or verification" [README `context-constitution/CONSTITUTION.md:144`].

**Exists.** The full operational vocabulary, prompted.

**Untested relative to RQ:**
- whether any lifecycle policy improves with experience;
- whether LLM-decided memory management beats OS-fixed rules (no such ablation was found);
- drift;
- whether consolidation helps downstream.

**Unverified possible prior art.** A June 2026 Letta post, "Memory Models: Towards Agents That Learn ... memory-native
RL", is known by title only [README `awesome-letta`].

### 3.6 Automated agent design and self-modifying agents

Covered: ADAS, Gödel Agent, Darwin Gödel Machine, AFlow, HGM, SICA, ALMA, MemEvolve.

**ALMA and MemEvolve: memory organization learned in an outer loop**
- ALMA has a meta-agent search memory designs written as code. Fitness is measured after an accumulation phase, so
  the signal is delayed.
- ALMA beats hand designs [README `alma/README.md`]:
  - 12.3 vs 8.6 with gpt-5-nano;
  - 53.9 vs 48.6 with gpt-5-mini;
  - on ALFWorld, TextWorld, BabaIsAI and MiniHack.
- But collection is open-loop and deployment frozen in all shipped training configs, and each evaluation gets a fresh
  memory [CODE `alma/training.sh`; `launch.py:181-186`].
- MemEvolve's evolved designs keep per-item usage and success counts and prune by them [CODE
  `lightweight_memory_provider.py:922-990`]. Storage is reset across rounds by default.

**The self-modifiers rarely touch context handling unless a designer points them at it** [CODE]
- DGM can select (p = 0.25) a hard-coded `solve_contextlength` diagnosis when a task log shows two consecutive
  "Input is too long" errors (`DGM_outer.py:36-48, 136-141`).
- The Gödel Agent never edited its 10-message window in the stored runs.

**Exists.** Learned memory *architecture* and per-item outcome statistics, via search over fresh runs.

**Untested relative to RQ:**
- one persistent agent revising its own organization online;
- continuity of content across redesigns;
- a binding active budget;
- PARK;
- credit to organizational decisions as opposed to memory items.

### 3.7 Simple learning controllers and published nulls

These set the bar any LLM learner must clear.

| Work | What it shows | Basis |
|---|---|---|
| MemRL | Online, runtime per-memory utility values on LifelongAgentBench. Every memory is kept. With the shipped γ = 0 the "Q-learning" is an exponential moving average of reward per item, i.e. a bandit. The FIFO code at `memory_service.py:850-865` evicts from a database cache, not from memory (corrected; an earlier pass misread it) | [CODE `memrl/service/value_driven.py:29-30, 180-215`; `memory_service.py:300-302`] |
| Memory Worth; TraceRetain | Outcome co-occurrence counters drive deprecation. A learned retention scorer ties FIFO/LRU/LFU on clean ALFWorld and helps only under 75% distractor writes | [SNIPPET] |
| The Complexity Trap | Keeping the last 10 observations matches LLM summarization on SWE-bench Verified (N=500), both about 50% cheaper than raw; paired CIs released | [README; CODE `auxiliary-data/*.csv`] |
| Provider primitives | Server-side context editing, compaction (default trigger 150K), a memory tool, and persistent memory stores | [README: Anthropic API reference bundled with Claude Code] |
| PBWM (computational neuroscience) | Learning *when* to gate working memory from delayed reward is established in non-LLM models | [README `leabra/PBWM.md`] |

### 3.8 Lifetime-structured evidence (snippet level, except AgingBench code)

- **Ground Truth First.** Budgeted curated memory leads at 3 weeks and loses evicted content by 9 weeks (96% → 72%):
  a "tenure crossover" [SNIPPET].
- **"Closing the Feedback Loop".** Ungoverned accumulated verbal experience falls *below zero-shot* under
  non-stationarity [SNIPPET].
- **AgingBench.** Pluggable memory policies over 8-200 sessions with compression, interference, revision and
  maintenance shocks. Its threshold controller observes ground-truth probes, and "learned controllers" are listed as
  future work [CODE `core/controller.py:1-17`].

At the outset of this review, these were the only places where the best fixed policy plausibly *inverts over a
lifetime*, the property Gate 0's worlds lacked. §6 later finds AgingBench's demand uniform: every past probe is
re-asked every session. Ground Truth First and "Closing the Feedback Loop" could not be inspected.

### 3.9 Status of each lifecycle part

| Part | Learned within an episode (offline RL) | Learned in an outer loop | Learned online within one lifetime | Prompted | Deterministic |
|---|---|---|---|---|---|
| FOCUS / composition (D1) | AgeMem, MEM1, MemAct | MemEvolve (injection) | MemRL (retrieval utility only) | Letta | Masking, context editing |
| COMPRESS | FoldGRPO (at fold), MEM1 | ALMA, MemEvolve | — | Letta, ACE | Compaction thresholds |
| ARCHIVE + retrieve | MemexRL | ALMA | — | Letta | Immutable log + index |
| RETIRE (item) | Memory-R1 DELETE | MemEvolve (counts) | Memory Worth (counters) | Letta | Expiry |
| PARK / RESUME (agent-chosen condition) | — | — | — | Letta Wake (clock only), PIS | Scheduler |
| BRANCH / FOLD | FoldGRPO, Kimi PARL (shaped) | ADAS/HGM ensembles | — | Letta fork, CLM | — |
| SPECIALIZE / MERGE / RETIRE whole contexts | — | — | — | Letta reflection names skill split and deprecate (no merge) | Managed memory stores; EvoChamber (fixed thresholds) |
| Learning the organization policy online within one lifetime (generic form) | — | ContextEvo? (two list snippets only; online or offline unknown) | **MemCon (bandit), AdaMem (LLM reflection), AEL (bandits + reflection)** [ABSTRACT; AEL CODE] | — | — |
| **… against simple learners given identical feedback, with lagged credit, under demand that inverts the best fixed policy, plus a distillation test** | — | — | **not found** | — | — |

### 3.10 Prior art found by a second, deeper search, and threats still unresolved

**How the second search worked.** It used three sources:
- a GitHub-hosted mirror of arXiv listings, with 92,059 abstracts from 2025-03-18 to 2026-09-07;
- the ICLR and ICML 2026 paper lists (papercopilot/paperlists);
- clones of every repository that could be located.

It changes the picture [ABSTRACT unless marked]:

| Work | What it does | Effect on the claim |
|---|---|---|
| **MemCon** (arXiv 2607.13591) | An online tabular contextual bandit (UCB) that learns, *within one deployment*, when to retrieve, inject a plan, consolidate and forget. It uses per-task binary feedback, "converges within tens of tasks", and is tested on 6 benchmarks, 3 frameworks and 3 LLMs | **The generic form of RQ is already tested, with a non-LLM learner.** Credit appears to be one-step (bandit), not lagged [INFERENCE] |
| **AdaMem** (arXiv 2606.21144) | An explicit per-role "Memory Policy" that an LLM rewrites by reflection from weekly QA feedback over simulated weeks, with rollback on failure | **The LLM-mediated form is already tested.** The only comparator mentioned is uniform Mem0; no simple learner given the same feedback |
| **AEL** (arXiv 2604.21725) | Online bandits (LinUCB, Thompson sampling) plus LLM reflection over 208 episodes | **Mixed.** Memory plus LLM reflection beats the stateless baseline (Sharpe 2.13 ± 0.47 vs 1.35 ± 1.03, 5 seeds) and, per the abstract, all non-LLM baselines. Removing reflection hurts (0.89 ± 1.44). Every further mechanism added on top, LLM and non-LLM alike, degrades it ("less is more"). Weak evidence either way: overlapping SDs [CODE `results/paper_results.json`; ABSTRACT] |
| **EvoChamber** (arXiv 2605.11136) | Specialize, fork, merge, prune and genesis on persistent agents, with *fixed* thresholds checked every 10 tasks | **The hand-coded multi-context lifecycle exists**, with a no-lifecycle ablation [CODE `evopool/lifecycle.py:44-53`] |
| **"Don't Lose the Thread"** (openreview NBGlItueYE) | Is **CORAL**: within-episode checkpoint, clear and resume, trained with RL (MARPO). **Withdrawn from ICLR 2026** (ratings 2/2/4/4) [ABSTRACT: papercopilot/paperlists] | Not a lifetime method. Resumption is immediate, not conditional |
| AdaCoM (arXiv 2605.30785) | "Learning Agent-Compatible Context Management for Long-Horizon Tasks": an offline RL-trained manager for a frozen agent, within an episode | Within-episode only |
| "Rethinking Harness Evolution" (2607.12227) | Harness evolution does not beat simple test-time scaling under matched feedback and budget | Null |
| Language-driven bandits (2604.05859) | Numerical bandits match LLM bandits | Null |
| "Useful Memories Become Faulty" (2605.12978) | An episodic-only control matches LLM consolidation. Agents given Retain/Delete/Consolidate keep raw episodes by default | Null, and the program's 0/192 prior again |
| "Delivery, Not Storage" (2607.20972) | Cue-anchored triggers checked by the harness; voluntary memory use was 0 in 114 turns | Same prior |

**Still unresolved.** These items would have to be read before any claim of novelty:

| Item | Known content | What must be checked |
|---|---|---|
| ContextEvo (arXiv 2609.34649, 28 Sep 2026) | "Learns context-management policies from long-horizon failures ... reconstructs decision-time context and targets policy updates at information-management errors"; "fixed and locally evolved strategies remain sensitive to context pressure" [SNIPPET, two list summaries] | Online or offline? Does it compare against counter or bandit learners given the same feedback? If both, the residue below is gone |
| MemCon, AdaMem bodies | Abstracts only | Whether forget/consolidate decisions receive lagged credit; whether demand shifts; whether a best-fixed-arm-in-hindsight or an LLM-controller baseline is reported; whether AdaMem-Bench's user interests drift |
| CLM (arXiv 2609.37725) | Context-as-file. The ICL outer loop and one-epoch GRPO were read [README/CODE]. Archive, sub-agent and swarm features were removed from the release (`harness.py:111-124`) | The 24-hour multi-repository swarm section |
| Letta "Memory Models" (June 2026) | Title only | Whether a memory model was trained with lifecycle-level RL |

**Coverage gap.** arXiv between 2026-09-08 and 2026-10-03 is indexed only through one curated list, which runs to 2026-09-30.

### 3.11 What survives as untested

- **Already done, so not a contribution:**
  - learned within-episode BRANCH, FOLD, COMPRESS, ARCHIVE and checkpoint/resume;
  - learned memory CRUD;
  - content learning from experience;
  - outer-loop learned memory designs;
  - prompted lifecycle tools;
  - online item-utility learning;
  - **online within-lifetime learning of an organization policy, by a bandit (MemCon) and by LLM reflection (AdaMem)**;
  - hand-coded multi-context lifecycles (EvoChamber).
- **What survives,** provided ContextEvo, MemCon and AdaMem do not cover it: *LLM-mediated* organization learning
  **compared against simple learners given identical feedback and a population prior**, on organizational decisions
  whose consequences are **lagged**, under demand that **inverts the best fixed policy over the lifetime**, **with a
  pre-registered distillation test.** Learned PARK with self-chosen resumption conditions is also unfound.
- **That residue is a methods control, not a new capability.** Most nearby results predict that the simple learner
  ties or wins:
  - language-driven bandits;
  - the harness-evolution null;
  - "Useful Memories Become Faulty";
  - MemEvolve's two shipped evolved designs, which retain items by per-item usage and success statistics (a pattern its
    generation prompt suggests).

  AEL is mixed: LLM reflection helped over a stateless baseline, and further additions hurt.

  §4 tests that prediction offline.
- **Reduction to ordinary memory management.** If the residue holds, the contribution reduces to ordinary memory
  management, i.e. online retention learning, which caching theory, MemRL, Memory Worth and MemCon already cover.

## 4. Strongest null

Two nulls compete for "strongest". They are stated separately because they kill different claims.
- **N1 (organization adds nothing):** store everything, retrieve well, and add deterministic triggers.
- **N2 (whatever is learned compresses):** any learned LLM organization policy compresses into a small controller.

### 4.1 N1: store everything, retrieve well, deterministic triggers

**Strongest form (N\*):**
1. An append-only raw log with timestamps and provenance.
2. Hybrid retrieval (BM25 plus dense), with query expansion, ±1 neighbour windows and chronological presentation.
3. Provider context editing and compaction for the working window.
4. Deterministic triggers: clock, channel polling, similarity-threshold cue matching.
5. Latest-wins validity.
6. Fixed typed side-indexes built by rules at write time: a pinned store of standing instructions, and a typed
   intention store.

**Why only three cases can beat it** [INFERENCE]. Any artefact that is a function of the immutable log can be
recomputed at read time once the query is known. So write-time organization can beat N\* only when:
- (i) no query exists at the moment of need (prospective memory, standing constraints);
- (ii) read-time computation exceeds the per-query budget (aggregation over more history than fits);
- (iii) latency binds.

A *learned* organization can beat a *fixed* one only if the right artefacts differ across deployments or drift over
a lifetime. This sharpens §2.3: cue failure is case (i), and integration cost is case (ii).

**What was computed** [COMPUTED in this session, no LLM; scripts and outputs in the session scratchpad, not
committed]
- *Methods:* our own BM25 with stemming; MiniLM-L6 dense embeddings from a non-Hugging-Face mirror; evidence recall
  only. No reader was run, so these are availability bounds, not accuracy.
- *Data:* LoCoMo (`locomo10.json`), BEAM (all 35 chats at 1M tokens and all 10 at 10M, from the BEAM GitHub
  repository), PM-Bench weeks for seeds 42 and 7, and MQuAKE-CF-3k-v2.
- *Not available:* LongMemEval, which is distributed only through blocked hosts.

**Results by benchmark:**
- **LoCoMo.** Histories are 13.6K-26.1K tokens. Every history fits a 32K window, so on LoCoMo the null is *full
  context*, with 100% of evidence available. LoCoMo cannot discriminate organization at all.
  - Under an artificial budget, BM25 all-evidence@10 is 0.67 for single-hop and 0.15 for multi-hop questions.
  - Multi-hop and open-domain questions need a median of 17% of the history to collect all their evidence.
- **BEAM-1M**, best single fixed configuration (BM25 plus ±1 window, ≤150 messages, about 80K tokens):
  - at least one evidence source is retrieved for 86.7% of probes;
  - choosing the best of 20 configurations per chat *with hindsight* gives 88.3%;
  - a per-probe oracle over all 20 gives 89.9%.
- **BEAM-10M:** 65.9% (the best fixed configuration there also adds a 0.1 recency weight), 67.0% and 67.6%
  respectively.
- **PM-Bench.** A non-LLM typed intention store reaches Set-F1 0.918 on the released week. It parses plan lines and
  "On ⟨Day⟩" notes, polls every channel, applies updates, and its threshold was tuned on the seed-7 week.
  - The same raw log *without* write-time typing reaches 0.56-0.58.
  - Released LLM runs reach 45.2-65.1% macro, with the best single run at 79.1%.
  - Caveat: the generator's templates make regex parsing easier than natural text would.
- **MQuAKE** (knowledge updates). BM25 top-10 contains the new fact for 99.9% of 6,121 edit questions. The dataset has
  no multi-valued keys, so supersession is never stressed.

**Where N\* fails, and whether something non-learned closes the gap:**

| Failure condition | Evidence | Closed without learning? |
|---|---|---|
| No query at the moment of need: standing instructions, due intentions | BEAM instruction-following: probe-as-query any@200 = 0.41 (1M), 0.05 (10M) | **Yes, by fixed write-time structure.** A regex pinned store holds about 1.4K tokens per 1M chat and covers 97% of instruction sources. The PM typed store scores 0.918 against 0.56 for the raw log. |
| Implicitly stated preferences | Pinned regex covers 70% of preference sources at 1M, 5% at 10M | **Partly.** A user-only dense index helps. Robust coverage needs a fixed LLM extractor, which is grounding, not learning. |
| Aggregation beyond the read budget: summaries, event order, multi-session | BEAM-10M all-evidence@200: summarization 0, event ordering 0, temporal 0.15, multi-session 0.25. Even the per-probe oracle misses 32% of 10M probes | **No.** This needs read-time LLM map-reduce (about 11.6M input tokens, about $11.6 per query at Haiku 4.5 list price) or *fixed* write-time aggregates such as a timeline or running scratchpad. **This is the only cell that neither fixed structure nor a fixed read-time procedure closes within budget.** |
| Stale-only retrieval | BEAM-1M: 12% of knowledge-update probes retrieve only the stale fact at k=50 | **Partly.** Chronological presentation fixes cases where both facts are retrieved. Key-based supersession works for single-valued facts and misfires on multi-valued ones. |
| Retrospective relevance (an item's significance is learned later) | Isolated LoCoMo examples | **No.** Needs iterative read-time retrieval or re-indexing; both are fixed procedures. |
| Non-stationary demand | **None of the datasets used in §4.1 has demand dynamics.** LoCoMo and BEAM ask their questions at the end, with a fixed type mix. The git streams added later (§6) do have drifting demand, but the best fixed rule rarely changes (mean regret 0.002) | **Untestable on available data.** |

**What N1 establishes:**
1. Raw-log-only N1 is false.
   - Where no query exists at the moment of need, write-time structure is worth 36 points of Set-F1 on PM-Bench and
     56-95 points of instruction-source coverage on BEAM.
   - A population pin classifier trained on other lifetimes also beat N\* on BEAM-1M (+0.028 to +0.047 at a 64K
     budget, 95% CIs above 0), so organization learned *across* lifetimes has value there.
   - Every gap that was closed, was closed by fixed structure (often regex-level) or by a population-level model.
     Nothing had to learn *within* a lifetime.
2. **Adaptive tuning of retrieval organization has almost no headroom.** Over 20 non-LLM configurations, the
   hindsight-best per-chat choice beats the single best fixed configuration by 1.6 points (BEAM-1M) and 1.1 points
   (10M). This is Gate 0's compressibility result reproduced on natural data.
3. The one genuine residual cell, aggregation beyond the read budget, is a contest between *fixed* write-time
   aggregates and read-time map-reduce. Learned against fixed is unidentifiable there, because BEAM's demand mix is
   stationary and known in advance.
4. **The property RQ needs, a best fixed policy that changes materially over the lifetime, exists in no dataset we
   could reach.** In git streams, the change exceeds 0.01 in only 8 of 37 lifetimes, with a maximum of 0.014. Testing it requires building demand dynamics. That is a designer choice, and §8 treats it as the main
   identifiability threat.

**Caveats:**
- Recall is not accuracy.
- Generator templates (BEAM's "Always X when I ask about Y", PM-Bench's plan lines) flatter regex structure.
- BEAM-10M has n = 16-20 probes per type.
- Mem0's results are vendor claims. Its BEAM-10M instruction-following score (90) is probably the model's default
  behaviour, since retrieval almost never surfaces the instruction.
- **Contamination disclosure.** LoCoMo, BEAM, PM-Bench seeds 42 and 7, and MQuAKE were all examined in this session.
  Any later pre-registered gate must not treat them as blind data (§8, §10).

### 4.2 N2: any learned LLM organization policy compresses into a small controller

**Theory: why this null is strong** [standard results; INFERENCE]
- **Worst case.** Deterministic LRU and FIFO are k-competitive, which is optimal among deterministic online policies.
  Randomized policies can do no better than Θ(log k): H_k is a lower bound, and Marker is 2H_k-competitive against an
  oblivious adversary. No
  online policy, LLM or not, escapes these worst-case bounds. Any claim of LLM advantage must therefore be
  average-case, on a declared demand distribution.
- **Decomposition.** For unit-size admit/evict decisions under demand the agent does not influence, learning-augmented
  caching (PredictiveMarker) has competitive ratio O(1 + min(√(η/OPT), log k)), where η is the error of the next-use
  predictions [SNIPPET]. So an LLM's value in this setting is *its prediction error*, and the policy that acts on
  predictions is textbook. The decomposition breaks when:
  - actions create content (summaries, merges);
  - item costs vary widely;
  - demand responds to the agent's actions.
- **Stationary recurrence.** When items recur, per-item counters converge to the best static set.
- **Rational memory.** ACT-R base-level activation is the Bayes-rational ranking when need tracks recency, frequency and
  association.
- **Generalized-linear bandits** approach the best predictor in their feature class with regret that does not depend
  on the number of items. LLM headroom is then only:
  - (a) the approximation error of the cheap features;
  - (b) prior-driven sample efficiency, which a *population prior* fitted on other lifetimes imitates cheaply.

**Where an LLM could have real headroom** [INFERENCE]:
- **Objectives changed in language.** This is provable, but it is instruction following, not learning; score it in a
  separate cell.
- **Generalizing a need predicate that is absent from the feature span after one failure.** Identifiable from
  failures-to-adapt on held-out streams where the predicate shifts.
- **Relational relevance:** multi-hop, aliases, supersession. Here an iterative-retrieval null is the stronger
  competitor.

**Where an LLM is structurally worse:**
- exact counting and recency;
- calibration;
- decision variance;
- deliberation cost;
- self-rewrite degradation. ACE's "context collapse" warning applies, and so does "Closing the Feedback Loop":
  ungoverned verbal experience falls below zero-shot.

**What was computed** [COMPUTED in this session, zero API; LoCoMo; 1,535 questions across 10 lifetimes; each question
asked at a seeded session end after its last evidence. Working set of K turns admitted/evicted at write time, plus
BM25 top-r over the log prefix. Outcome proxy: all gold evidence in context.]

| Policy (r=5, 4 seeds, 6,140 question instances) | K=16 | K=32 | K=64 |
|---|---|---|---|
| Null: retrieval spending the same slots at question time, RET(r+K) | **0.610** | **0.657** | **0.703** |
| Clairvoyant ILP oracle under the same admission constraint | 0.816 | 0.922 | 0.993 |
| Best implementable controller (salience, logistic + population prior) | 0.529 | 0.573 | 0.647 |
| FIFO | 0.503 | 0.536 | 0.592 |
| ACT-R | 0.482 | 0.497 | 0.524 |
| Memory-Worth counters, binary feedback | 0.486 | 0.503 | 0.531 |
| Online-only logistic | 0.513 | 0.543 | 0.593 |

**Findings:**
1. **No write-time keep/evict controller beats the matched-budget retrieval null.** On the pooled accuracies in the
   table, the best controller trails by −8.1, −8.4 and −5.6 pp. As per-conversation paired means, the gaps are −8.1,
   −8.5 and −5.3 pp, with 95% cluster-bootstrap CIs [−9.7, −6.8], [−10.2, −6.8] and [−7.7, −3.0]. At r = 10 the
   deficit is 0.7-3.4 pp, and LOGREG + prior at K = 64 ties. That includes 16 cheap or outcome-trained controllers and an
   outcome-blind LLM salience feature (gpt-3.5 dataset field).
2. **The oracle's 20-29 pp headroom is clairvoyance about *when* an item is needed, not *whether*.** A "whether"
   predictor never beats the null at K ≤ 32, even at AUC 0.999. A predictor that also knows when the need ends must
   reach AUC 0.93, 0.87 and 0.82 at K = 16, 32 and 64. The best write-time predictor reaches 0.785 with cheap features
   and 0.801 with LLM salience (leave-one-lifetime-out).
3. **Within-lifetime learning adds nothing on top of a population prior** (seed 0, 1,535 questions). The prior with no
   online learning equals
   prior plus online learning, within ±0.5 pp in all six cells.
   - Within-lifetime similarity to past evidence predicts future need of never-needed items at AUC 0.48-0.49, i.e.
     chance. The population prior reaches 0.775, and adding the within-lifetime signal *lowers* it to about 0.69.
4. **Under recency-biased demand** (seed 0 only, about ±2 pp noise), the small available gain (≤ 4 pp at K = 64) goes to FIFO or to "salient first, then
   recency". Outcome learning adds about 0.
5. **Post-hoc blame search fails without rich feedback.** With only a scalar failure signal, searching the log after
   the fact finds the missed evidence turn with precision 0.7-2%. Revealing the gold answer raises it to 27-35%.

**Delayed credit where credit is easy** [COMPUTED: PM-Bench v9 generator, logic unmodified, the deterministic
typed-store actor, 40-week lifetimes, failure reports at week end]
- A generic online logistic matcher learning resume-condition corrections from delayed failure reports rises from
  0.931 (frozen) to 0.980 lifetime F1.
- The same matcher trained on *other* lifetimes and then frozen reaches 0.986. Prior plus online learning reaches
  0.992.
- A clairvoyant trigger reaches 1.000. That leaves **≤ 0.008 F1 for any LLM learner**, overall, and 0.006-0.007 after
  a template shift at week 21.
- With access to the immutable log, delay matters little. In one stationary 40-week lifetime, reports delayed 1 day,
  1 week or 4 weeks give +0.021, +0.020 and +0.018 for a memorizer. For the logistic matcher, a 4-week delay costs
  0.008, which is the size of the entire remaining headroom.
- Without the log, learning disappears (−0.0035).

**What N2 establishes.** The immutable log turns delayed credit assignment into a lookup. Two cases follow:
- **When feedback names the item,** learning from delayed failures becomes ordinary supervised learning, and a
  generic learner with a population prior comes within 0.008 of a clairvoyant oracle.
- **When feedback does not name the item,** credit cannot be found and lessons do not generalize within a lifetime.

**Either way, the learner that must be beaten is cheap, and on every substrate we could reach it leaves too little
headroom to detect an LLM advantage.** Gate 0's compressibility failure reappears one level up. One-line rules do not
reach the oracle (0.943 against 1.000 on PM-Bench), but a generic learner with a population prior nearly does.

**Within-lifetime learnable headroom across every substrate reached** [COMPUTED]. This is what *learning within the
lifetime* adds over a population prior fitted on other lifetimes.

| Substrate (unit = one lifetime) | n | Best learner's gain within the lifetime, over the prior | Note |
|---|---|---|---|
| LoCoMo (natural) | 10 | −0.001 to +0.005 across the six budget cells (seed 0); +0.001 / +0.002 AUC from the lifetime's own first half | — |
| BEAM-1M (natural; probes constructed in-stream, gold provenance after each) | 31 | −0.040 [−0.067, −0.014] at 16K; −0.007 [−0.021, +0.007] at 64K | 4 of 35 chats excluded for shifted source annotations |
| BEAM-10M | 10 | −0.021 [−0.043, 0.000] | — |
| PM-Bench generator (synthetic, template-quarter shift) | 8 | +0.0054 (SD 0.0024); absolute room left by the clairvoyant trigger: **0.0079** | — |
| Git commit streams (natural, visible demand, no task text given) | 37 | Cross-fitted lifetime model − population model: +0.0026 [0.000, +0.0053] | Best fixed rule: ACT-R with d = 0.8 (hit rate 0.580 at K = 16). Every learned controller with a population prior or a warm start lands within ±0.006 of it; a cold-start online learner is 0.019 below it. With the task text, retrieval wins by +0.141 |

- No entry shows a within-lifetime gain above +0.008. Every point estimate is at most +0.0054, every reported upper
  bound is at most +0.008 (the largest is BEAM-1M at 64K, +0.007), and the BEAM entries are negative. LoCoMo reports
  pooled point differences only, and PM-Bench is bounded by its clairvoyant ceiling of 0.0079.
- Clairvoyant headroom over the null on these substrates:
  - LoCoMo +20-29 pp (exact ILP oracle);
  - BEAM +0.15 to +0.47 (a pin set chosen with knowledge of the lifetime's probes);
  - git 0.976 against 0.580 (an oracle that knows the next commits);
  - PM-Bench 1.000 against 0.992.

  No implementable learner reaches any of these.
- The smallest effect of interest any design in this session proposed was 0.01-0.03.
- These kills do not depend on where a threshold sits. They are absolute clairvoyant bounds, wrong-signed intervals, or
  upper bounds of at most +0.007. This matters because every threshold in this session was written after the data were
  examined.

### 4.3 Which null is strongest

1. **N1 refutes "organization adds nothing" only partly.** Fixed write-time structure is worth a great deal where no
   query exists at the moment of need, and a population model trained on other lifetimes adds more on BEAM-1M. But it
   refutes "organization learned *within* a lifetime adds something": every gap that was closed, was closed by fixed
   or population-level structure.
2. **N2 is the strongest null for RQ as revised.** On every substrate where it was measured, one of the following
   holds:
   - a population-prior learner using cheap features matches the oracle within detection limits (PM-Bench);
   - a fixed rule does (PrefEval routing, git ACT-R);
   - the oracle's headroom is clairvoyance that no implementable controller can obtain (LoCoMo);
   - the within-lifetime gain is negative (BEAM).
3. **The two nulls compose.** N1 says the competitor is fixed structure plus retrieval. N2 says that whatever is left
   to learn is learned by a counter, bandit or logistic model with a population prior.

**Can the alternative explanations be separated?** The brief for this review instructs: "If these explanations
cannot be separated experimentally, say so and stop". This is the reviewer's brief, not a repository document. §8 finds that three of them cannot be separated at affordable scale.

## 5. Candidate mechanism

This is stated so that it can be attacked. Nothing here is built.

### 5.1 Experiential organization policy (EOP)

**The fixed parts.**
- Everything listed in §2.2 is deterministic: the immutable hash-chained log, provenance, the clock and scheduler,
  indexes, budget metering, and `apply(op)`.
- The agent's task reader (the answerer) is a frozen model with a fixed prompt. It is shared by every arm.

**What is learned.** One object: an explicit, versioned organization policy P_t. It is a short table of rules in a
fixed edit grammar, capped in tokens, and each rule maps a situation to one operation:
- keep verbatim in A;
- keep as summary;
- archive with an extra index cue;
- register an intention with condition C;
- retire, i.e. set the end of a validity interval.

**At write and compose time.** A frozen executor (deterministic code, or an LLM with a fixed prompt) proposes
operations by applying P_t, and `apply` executes them.

**At feedback time.** Feedback may arrive many steps later. The learner receives three things:
- the feedback;
- the provenance trail from the log, i.e. which decisions touched the items relevant to the outcome;
- P_t.

It returns a small diff to P_t in the edit grammar. The diff is applied deterministically and logged. If a
pre-declared within-lifetime validation check degrades, the change is rolled back; AdaMem's rollback is the
precedent.

**What makes it "learning through experience".** P_t changes only as a function of the consequences of the agent's
own earlier operations, read through the log. A frozen twin (L0) receives the same calls and inputs with the outcome
labels removed.

**Decomposed variant, L1→PM.** The LLM emits only need predictions: the probability, and the time, that each item will
be needed. A textbook policy (PredictiveMarker, or a knapsack over token cost) acts on them. If L1→PM matches L1, the
LLM's contribution is prediction, and the "policy" is ordinary caching (§4.2).

### 5.2 Scope

| Decision | In scope? | Reason |
|---|---|---|
| D1 composition: FOCUS / PIN | Yes, **the only lever retained for E1** | The core of "what to keep active"; query-blind at write time, with delayed consequences |
| D1 composition: keep as summary (COMPRESS) | Deferred, not refuted | Not tested on a discriminating substrate. On LoCoMo, which cannot discriminate organization (§4.1), session summaries contain all answer stems for 0.275 of questions, against 0.718 for archive + retrieval at matched tokens (a stem proxy, not accuracy) |
| D2 write-time derivation (cue, supersession, aggregate) | Fixed, not learned | Every N1 gap was closed by *fixed* derivation. Aggregates beyond the read budget are an organization-vs-null question, which is a separate proposal |
| D3: learned matching of user-given resume conditions | Dropped after §4 | Timing is infrastructure; registration and matching are grounding. On the PM-Bench generator, learned condition edits have ≤ 0.008 F1 left |
| D3: agent-initiated PARK with self-chosen conditions | Untested | No reachable substrate supports it: in PM-Bench, parking is always imposed by the user's text, misses have no downstream consequence, and there is no capacity pressure (§3.2, §3.11) |
| D4 partitioning (BRANCH / FOLD) | No | Within-episode learning is published (§3.1). The lifetime-level part, keeping a partition, is SPECIALIZE (next row) |
| SPECIALIZE / MERGE / RETIRE whole contexts | No | Not distinct from a named store plus routing (§2.4). Confounded with extra windows. Hand-coded versions already exist (EvoChamber) |
| Item RETIRE | Only as a validity end | Deletion is forbidden by the immutable log; tombstones only |

**The evidence narrows this further** (§4). Two levers are set aside for E1:
- **COMPRESS is deferred.** Its only test was on a substrate that cannot discriminate organization, and it favoured
  archive plus retrieval: on LoCoMo, session summaries alone contain all answer stems for 0.275 of questions, against
  0.718 at matched tokens. Summaries helped only multi-hop aggregation, which is a fixed-aggregate effect.
- **Learned matching of given PARK conditions is dropped.** On the PM-Bench generator, a generic learner with a prior
  is within 0.008 of a clairvoyant trigger. PrefEval is solved by a fixed domain router.

The lever retained for E1 is **FOCUS/PIN**: which items stay in a small always-in-context store, chosen without
seeing the query, under consequences that arrive later. This is the one decision that is query-blind at write time
and has delayed effects.

**E1 therefore tests a narrowed RQ:**
- D1 FOCUS only, at matched active tokens;
- against C\*, C-T2\*, L0, YOKED, SHUF-cal and COMPUTE-MATCHED (equal total compute; this is the Q5 contrast);
- the hindsight-best fixed policy (B15) is reported as an offline bound, not used as a decision contrast. R0.6
  already requires the learnable ceiling to exceed B15 by δ before E1 can run. Without an R0.7 pass, no claim about
  tracking shift is made.

### 5.3 Why EOP is the right object to attack

- It is the most favourable reading of the hypothesis that still separates organization from content:
  - P_t is explicit, so it can be inspected, replayed frozen, and distilled;
  - its inputs are logged, so information parity with simple learners can be enforced by hash.
- It is also the reading closest to existing work:
  - AdaMem rewrites an explicit memory policy by LLM reflection;
  - ContextEvo "targets policy updates at information-management errors".

  So EOP is not novel as a mechanism. The only possible contribution is the *comparison*: EOP against simple learners
  given identical feedback, with distillation, under lagged consequences and regime shift.
- **The one route to an LLM advantage that does not come from priors** is naming a need predicate that lies outside the
  feature span of cheap learners after a few failures (§4.2) [INFERENCE]. E1 in §9 is built to test exactly that, and
  nothing else.

## 6. Candidate environments

**Requirements.** The decisive substrate needs all five of the following:
1. natural, or at least third-party, data;
2. questions or tasks arriving *during* the stream;
3. feedback during the stream;
4. demand or truth that shifts, so the hindsight-best fixed policy changes over the lifetime. This is needed only for
   the non-stationarity claim (R0.7);
5. an active budget that binds even against store-all plus retrieval.

**Inspection.** Each candidate was checked in code and data where accessible [CODE/COMPUTED unless marked].

| Substrate | Horizon / lifetimes | During-stream feedback | Demand or truth shift | Binding budget vs store-all+retrieval | Strong no-LLM baseline | Verdict |
|---|---|---|---|---|---|---|
| LoCoMo (CC BY-NC 4.0) | 10 lifetimes, 13.6K-26.1K tokens each | None native (questions at the end) | None | **No.** Fits a 32K window; full context is the null | Matched-budget retrieval beats the best write-time controller by 5-9 pp at r = 5 and by 1-3 pp at r = 10 (a tie at r = 10, K = 64). No controller beats it | Negative. Too few lifetimes; already examined |
| BEAM 1M / 10M (MIT) | 35 + 10 chats, ~1.1M / ~11.6M tokens | None (about 18 annotated probes per chat, all at the end) | None; fixed type mix | **Yes**, the only natural overflow | Best fixed retrieval config; regex pin store captures 97-100% of instruction sources | Residual cells are aggregation (fixed aggregates or map-reduce) and implicit preferences at 10M (n = 20). Nothing to *learn* |
| PM-Bench v9 generator (no LICENSE file) | Seeded weeks; multi-week lifetimes constructible | Constructible: weekly FN/FP reports | Constructible: template-quarter shift | Not native (week ≈ 17-18.5K tokens) | Non-LLM typed store 0.918; generic learner + prior 0.986-0.992; clairvoyant 1.000 | **Most favourable found.** Fails headroom: ≤ 0.008 F1 left |
| AgingBench (MIT) | 8-200 sessions; generator offline | None to the agent; controller hooks read ground-truth probes | Truth revisions, yes | No (S6 at 200 sessions ≈ 29K tokens) | BM25 + recency hit@10 0.917; latest-mention rule 0.84 on revised facts | Every past probe is re-asked every session, so need is uniform. Nothing to learn about retention |
| Memora (Apache-2.0) | 10 personas; ~150 / 600 / 2,000 sessions | None (questions on the last day) | Heavy truth change | Yes at the quarterly size (~870K tokens) | Write-time memory turns detectable with AUC 1.000; regex ledger | Templated; a fixed typed ledger is the oracle. Negative control only |
| PrefEval (CC BY-NC 4.0) | 1,000 preference/question pairs, 20 topics | None | None | Through reader degradation, not price | Fixed park-by-domain + router, top-2 at ~2K tokens: 0.91 (write-time classifier) to 0.95 (gold topic labels) | Solved by fixed routing |
| LifelongAgentBench (data vendored in MemRL, MIT) | 500 DB + 500 OS tasks | Correctness per task | Near-stationary (same top skill in every quintile for DB; in 4 of 5 for OS) | Storage budget unrealistic | Store-all dominates on a skill-cover proxy | Negative |
| Supersede (Apache-2.0) | One question per episode | Terminal reward | Knowledge updates | Artificial (300-char notes) | Full context 82-92% vs bounded notes 63-77% | Not a lifetime |
| MemoryAgentBench, LongMemEval, StreamBench | Data only on blocked hosts | None / none / correctness | None / none / i.i.d. shuffle | — | FactConsolidation states the newer-wins rule in its prompt | Unsuitable or unreachable |
| Evo-Memory; Ground Truth First; MemoryArena | No code or data found / no repo / no license | — | Evo-Memory uses a designed easy→hard order | — | ExpRAG already strong (Evo-Memory paper) | Not inspectable |
| Git commit streams (37 repositories; new in this session) | 37 lifetimes, 55,151 scored commits | Each commit reveals what was needed | Demand drifts, but the best rule rarely changes: mean regret of the global best rule against the per-third best is 0.002 (max 0.014); regret exceeds 0.01 in 8 of 37 lifetimes | Only if the task text is withheld; with it, retrieval wins by +0.141 | ACT-R d = 0.8; every learned controller within ±0.006 | Visible demand: experience carries only the agent's own errors (+0.0026 lifetime ceiling). Few post-cutoff windows |
| AdaMem-Bench | Abstract only | Weekly QA feedback | Unknown | Unknown | — | **The one unread candidate that might have demand dynamics** |

**Conclusion.**
- **No reachable substrate meets requirements 1-3 and 5, and none meets requirement 4 either.**
- Natural data has too few lifetimes. Except for git streams, it asks its questions at the end, with stationary
  demand. In git streams demand drifts, but the best fixed rule rarely changes.
- Generated data can supply lifetimes, feedback and shift. But there the designer picks the shift, and on the most
  favourable generator (PM-Bench) a generic learner with a population prior is already within 0.008 of the oracle.

**What a synthetic environment would need to qualify.**
1. The demand process comes from a third party, or is a published, unmodified generator, never ours.
2. The shift rule is hashed before any controller runs.
3. Hindsight-best one-line and two-line rules, a population-prior generic learner, and a clairvoyant oracle are all
   computed offline first.
4. It passes only if a pre-declared headroom, oracle minus (population prior + online simple learner) ≥ 2δ = 0.04
   (R0.4), survives on fresh seeds.

No environment found meets this.

## 7. Baseline ladder

Every arm uses the same frozen answerer, the same log and retriever, the same active budget B, and identical feedback
text, verified by hash. Every token is charged to the arm that spends it: answers, organization, reflection,
branches and retries.

| # | Arm | What it controls for | Status |
|---|---|---|---|
| B0 | Bounded monolithic agent with provider compaction / context editing | The default product behaviour | Required |
| B1 | Monolithic agent + immutable log + retrieval at matched tokens (RET(r+K)) | Context length and retrieval. **The primary null**: no write-time controller beat it on LoCoMo | Required |
| B2 | Strong deterministic memory manager: fixed typed side-indexes (pinned constraints, intention store, latest-wins validity, fixed aggregates) | Fixed structure, which closed every N1 gap | Required |
| B3 | Fixed current-state + historian + immutable ledger (content accumulates, policy frozen) | "The architecture did it", as opposed to learning | Required (it is the FROZEN arm's architecture) |
| B4 | Temporary branch/fold under a fixed fold rule | Extra windows and fold-time compression | Only if D4 is ever in scope |
| B5 | Fixed multi-agent (named persistent specialists, fixed router) | SPECIALIZE without learning | Only if SPECIALIZE is ever in scope |
| B6 | **Simple learners with identical feedback:** per-item and per-type counters, ACT-R, contextual bandit / logistic on cheap features, **each with a population prior fitted on training lifetimes**, discounted variants for shift, PredictiveMarker fed by their predictions | Whether *any* learning helps, and whether the LLM is needed for it. Online-only learners without a prior flatter the LLM by 0.006-0.012 on PM-Bench and by 0.016-0.054 on LoCoMo (§4.2) | Required. This is the bar |
| B7 | L0: the same LLM with learning frozen (same calls, outcome labels removed) | LLM priors and harness cues, as opposed to experience | Required |
| B8 | SHUF-cal: feedback permuted within the lifetime, **validated offline** so that a simple learner trained on it lands within ±δ/2 of its frozen prior | Specificity of credit. A naive shuffle *poisons* learners: on PM-Bench the shuffled logistic matcher fell to 0.813, below the frozen 0.931, so a naive SHUF arm would flatter L1 | Required |
| B9 | YOKED: receives the policy diffs another lifetime produced, at the same times | Own experience vs. generic updates | Required for any "own experience" claim |
| B10 | CUE-MATCHED: generic nudges of the same volume as L1's reflection calls | Demand effects of being prompted to reorganize | Required |
| B11 | COMPUTE-MATCHED: L1's reflection tokens spent on content-only reflection or best-of-n | More compute, not better organization | Required |
| B12 | L1: the adaptive mechanism (EOP), and L1→PM | The treatment, and its decomposition | Treatment |
| B13 | D: behaviour-cloned controller on L1's decisions, run on-policy; C-T0\* and C-T2\* outcome-trained controllers (C-T2\* = online GLM over cheap features plus L0's outcome-blind need scores, with identical feedback) | Compressibility; C-T2\* is the exactly matched competitor for LLM self-correction | Required |
| B13b | NOLOG (L1 without the provenance trail); DELAY×4 (feedback delayed fourfold) | Whether credit flows through the log; sensitivity to delay | Manipulation arms |
| B14 | Offline clairvoyant oracle under the same admission constraint | Headroom only, never a competitor | Required offline |
| B15 | Hindsight-best one- and two-line rules, hash-pinned before evaluation | Gate 0's compressibility trap | Required offline |

## 8. Identifiability threats

### 8.1 Separable, at the cost of one arm or one constraint each

| Alternative explanation | Separating control |
|---|---|
| Context length | B1 at measured equal tokens per call, plus a budget sweep |
| Retrieval | B1, with the same retriever and query budget for every arm |
| Summarization | A shared, frozen summarizer. Replay content swaps from the log and re-run only the answer calls. **Only partly separable**, because choosing what to summarize is itself a decision |
| Task queue; deterministic prospective-memory triggers | B2. A typed store already scores 0.918 on PM-Bench without an LLM, against 0.791 for the best LLM run |
| Temporary branch/fold | B4 |
| Fixed current/historian/archive architecture | B3, with difference-in-differences over lifetime position and a reversed-order replicate |
| Extra context windows or compute | B11, with all tokens metered, including branches and reflection |
| LLM self-assessment bias | Ground-truth outcomes only. Self-ratings are logged and calibrated in L0 |
| Feedback leaking answers | Score pre-registered "fresh" questions only (72.8% of LoCoMo questions have evidence not revealed by earlier questions). Run a scalar-feedback arm and a leak audit. No ground-truth fallbacks: PM-Bench has one at `pm_bench.py:1944-1958` |

### 8.2 Not separable at affordable scale [COMPUTED unless marked]

- **U1. "Learning the task distribution" vs "learning an organization policy."** This one is structural, not a matter
  of scale. Assume costs are metered and `apply` is deterministic. Then the optimal retention and composition policy
  is a function of the demand process, the reader's use of context, and the costs (Belady; rational memory)
  [INFERENCE]. For D1-D2, learning organization *is* learning demand plus a model of one's own reader, so the
  contrast is ill-posed and should be dropped. What remains well-posed are two claims:
  - Q4: LLM-mediated learning beats a plug-in learner with the same feedback;
  - autonomy: matching the controller without being given its specification (`GATE_0_SPEC.md:123-129`).
- **U2. Own-experience learning vs population prior vs harness cues.** Separable in principle, using B7, B9 and B10.
  The measurements:
  - On LoCoMo, learned-plus-prior against a salience rule that uses no outcomes differs by −0.004 to +0.015.
  - The lifetime SD is 0.031-0.055.
  - With LLM-level noise and N = 10, the minimum detectable effect is 0.04-0.06.
  - Detecting 0.01 would take about 128-285 lifetimes; detecting 0.005 about 505-1,133.

    No natural source examined here has more than 41 valid lifetimes. The open-ended one (git) has only 4-12
  repositories with enough commits after the model cutoff. Cue response also varies by model, in sign as well as size. For
  example, forced PM-Bench heartbeats changed F1 in opposite directions across models.
- **U3. Dependence on a regime the designer chose.** Generated lifetimes fix U2's sample-size problem only by letting
  the designer choose the non-stationarity. That choice is the manipulation, and Gate 0 shows it compresses into a
  contingent rule.

**These three combine into a dilemma.**
- Natural data has too few lifetimes and nothing to learn within one.
- Generated data has enough lifetimes, but the regime is the manipulation.
- Under the brief for this review (not a repository document), "If these explanations cannot be separated
  experimentally, say so and stop", **this alone justifies NO-GO on any LLM run.** It does not, by itself, forbid zero-API work.

### 8.3 How a follow-up would repeat Gate 0, and the guard against each

| Gate 0 failure mode | How it would recur here | Guard |
|---|---|---|
| The answer designed into the environment | Picking a shift type or a feedback format because it is the one where the LLM should win | Third-party generators only; shift rule hashed before any controller runs; environment never chosen by looking at which controllers fail |
| Optimal policy is a short contingent rule known in advance | "Maintain aggregates for the currently frequent probe types"; "ignore sentences with modal words" (0.943 on PM-Bench) | B15 hash-pinned; gate requires headroom over B6 *with population prior*, not over one-line rules alone |
| Compressibility one level up | A generic learner with a prior reaches the oracle (PM-Bench: 0.986-0.992 vs 1.000) | Gate criterion: oracle − (prior + online learner) ≥ 2δ = 0.04 on fresh seeds (R0.4) |
| Criteria drafted with or after the environment | **Already happened in this session.** LoCoMo; BEAM; PM-Bench seeds 42, 7, 101-140, 2001-2005, 3001-3008, 10001-10160, 20001-20160 and 30001-30160; PrefEval; MQuAKE; AgingBench; Memora; LifelongAgentBench; and the 37 git repositories were all examined before any criterion was hashed | Treat every dataset touched here as calibration only; any registered gate uses fresh seed blocks or untouched data, with thresholds hashed first |
| Simulator-derived power presented as empirical | LLM noise SD assumed (0.015-0.06) rather than measured | Label it as assumed; power the gate on controller SDs only; any LLM stage includes a pre-registered variance pilot |
| Deliberation cost ignored | Reflection calls are free in the accounting | Every token is charged to its arm; COMPUTE-MATCHED arm |
| Rescue knobs after failure | A second prompt wording, another model, a richer feedback format | One model, one prompt, one feedback format, pre-registered. Asymmetry rule: variants only to test generalization of a success |
| Demand effect | Prompting reorganization makes it happen whether or not it pays | CUE-MATCHED arm; pre-registered cells where an operation should be used *less*; net value per operation |

## 9. Smallest decisive experiment

**No experiment that spends money is proposed, and none is authorized.** §4 and §8 show why: on every substrate this
session could reach, the decisive contrast is either smaller than any affordable experiment can detect, or a positive
result is impossible by construction.

What follows specifies two things:
- **R0**, the zero-API gate that must come first on any substrate;
- **E1**, the LLM experiment that R0 would unlock.

They are specified so that the NO-GO can be audited and so that re-entry has a defined door. Neither is to be run now.

### 9.1 R0: zero-API substrate gate

Thresholds are hashed before anything is computed. Only fresh data may be used: nothing examined in this session.

**δ = 0.02** absolute on the substrate's primary score in [0, 1]. Any other value must be justified in the
registration. A PM-Bench-style F1 substrate fails at any δ ≥ 0.008.

| # | Criterion | Pass | Kill |
|---|---|---|---|
| R0.1 | **Eligibility.** All of: natural data, or an unmodified third-party generator whose regime and shift rule are hashed before any controller runs; ≥ 30 + n_test lifetimes (≥ 20 train, ≥ 10 validation, n_test from R0.9, so at least 84), plus ≥ 12 shift lifetimes from another domain; tasks arrive during the stream; licence permits publication | all hold | any fails |
| R0.2 | **Feedback reach.** Median feedback events per lifetime, and the share of evaluated *fresh* needs that share a pre-registered need cluster with an earlier feedback event | ≥ 50 and ≥ 30% | < 20 or < 10% |
| R0.3 | **Learnable room without an oracle.** A lifetime-specific model, cross-fitted on contiguous blocks over the widest zero-API feature set, minus the population-prior model | 95% lower bound ≥ δ/2 | 95% upper bound < δ/2. In between: no LLM run |
| R0.4 | **A positive is not ruled out by the ceiling.** Clairvoyant (or trigger) oracle minus (population prior + online simple learner) | ≥ 2δ | < δ |
| R0.5 | **Organization binds.** Best implementable organization minus N\* at matched *measured* active tokens | 95% lower bound > 0 | point estimate ≤ 0 |
| R0.6 | **Not a known rule.** R0.3's ceiling minus the larger of: the hindsight-best ≤ 2-line rule, and the best textbook rule (ACT-R, LRU, non-template regex pins, fixed router) | ≥ δ | < δ/2 |
| R0.7 | **Shift exists.** Needed only for non-stationarity claims: mean regret of the global best fixed rule against the per-third best rule | ≥ δ/2 | otherwise the non-stationarity claim is dropped, and E1 cannot claim the shift part of the §3.11 residue |
| R0.8 | **Gate sensitivity.** Plant a lifetime-specific regularity worth δ, and estimate P(R0.3 pass) and P(R0.3 kill) over ≥ 200 simulations | P(pass) ≥ 0.8 and P(kill) ≤ 0.05 | otherwise the gate is uninformative, which counts as a kill |
| R0.9 | **Power available.** Test lifetimes ≥ ⌈8.6σ²/δ²⌉, where σ² is the measured controller variance plus 0.05² of LLM variance, assumed until measured. At δ = 0.02 that is at least 54, even with zero controller variance | holds | fails |
| R0.10 | **Leak audit.** No ground-truth fallback; ≥ 70% of evaluated items fresh; feedback text a deterministic function of the log | holds | fails |

**Status on substrates touched in this session.** These are exploratory results, for calibration only. These
substrates can never be the registered data.

| | LoCoMo | BEAM 1M/10M | PM-Bench generator | Git, no task text |
|---|---|---|---|---|
| R0.1 | ✗ 10 lifetimes | ✗ 31 + 10 | ✗ synthetic; shift partition chosen after two others were rejected by the generator; no LICENSE | ✗ 37 < 84 (and it is the development set) |
| R0.2 | ✗ question timing constructed; 27% of questions already revealed by earlier evidence | ✗ 14 probes per lifetime; natural feedback overlaps probe sources 3% | grey: 40 weekly reports per 40-week lifetime (< 50); overlap share not measured | ✗ visible demand |
| R0.3 | — point estimates ≤ +0.005, no interval computed (killed by R0.1 and R0.5) | ✗ ≤ 0, upper bound +0.007 | ✗ +0.0054 | ✗ upper bound 0.0053 |
| R0.4 | ✓ but timing clairvoyance only | ✓ | ✗ 0.0079 | ✓ |
| R0.5 | ✗ null wins by 5-9 pp (r = 5) | population pins only | ✗ / not measured: no binding budget, and the typed store is part of N\* | ✓ only without task text |
| R0.6 | — | not measured: template regex pins reach 0.97-1.00 on instruction probes, but R0.6 counts only non-template pins | ✓ as written: hindsight one-line rule 0.943 vs a learner ceiling of about 0.99 (the 0.0079 gap to the oracle is R0.4's kill) | ✗ ACT-R within ±0.006 of every prior or warm-start learner |
| R0.8 | — | ✗ split-half test detects a planted optimum only at about +0.10 | — | — |
| R0.9 | ✗ minimum detectable effect 0.04-0.06 | ✗ minimum detectable effect 0.032-0.08 | ✓ about 54-57 lifetimes under R0.9's σ (generated lifetimes are unlimited) | ✗ 4-12 repositories with enough commits after the model cutoff |

### 9.2 E1: conditional LLM experiment

E1 runs only on a substrate that passes R0. No such substrate exists today.

**Hypothesis H1.** On held-out lifetimes, at matched measured active-context tokens, an LLM that revises an explicit
FOCUS policy table from delayed outcome feedback plus log provenance (L1) scores higher on *fresh* evaluated items
than each of:
- C\*, the strongest simple learner given identical feedback and features plus a population prior;
- C-T2\*, an online GLM over cheap features plus L0's outcome-blind need scores;
- L0, its frozen twin;
- YOKED, its yoked twin;
- SHUF-cal, its calibrated-shuffle twin;
- COMPUTE-MATCHED, the same total compute spent on content-only reflection (the Q5, net-value contrast).

L0 enters as a precondition (95% lower bound of L1 − L0 > 0). It is not one of the m = 5 Holm contrasts.

The required margin over C\* is δ = 0.02.

**Explicitly not claimed:** that it learns "organization rather than the task distribution" (U1, §8.2).

**Null H0.** Either:
- the upper limit of the two-sided 90% CI of L1 − max(C\*, C-T2\*) is below δ; or
- a precondition fails: the 95% lower bound of (L1 − L0) ≤ 0, or of (L1 − N\*) ≤ 0.

**Environment.** The R0-qualified substrate. Eligible classes, in order:
1. natural long-term assistant or agent deployment logs with consented implicit feedback (re-asks, corrections, task
   success), with at least 84 users (R0.1);
2. an unmodified third-party generator. The only named candidate is AdaMem-Bench, known from its abstract.

Not eligible: LoCoMo, BEAM, PM-Bench, PrefEval, git streams, AgingBench, Memora, LifelongAgentBench, or any generator
written by this program.

**Temporal structure.**
- A lifetime is one user or deployment, in native order. Its horizon is set by R0.2 (≥ 50 feedback events).
- A pin decision is made without the query. It pays off or fails when a later need arrives, so consequences are
  delayed by the decision-to-need lag, and that distribution is reported.
- Feedback delay is native, plus a DELAY×4 arm.
- Non-stationarity is native only, measured by R0.7. There are no designed cut points.

**Treatment L1 (EOP-FOCUS).**
- *State:*
  - the immutable log;
  - a pin store of ≤ P tokens (P = B/8, e.g. B = 16K, P = 2K). The fixed N\* retriever fills the remaining B − P at
    query time, so L1 differs from N\* only in what is pinned;
  - a policy table of ≤ 1K tokens and ≤ 30 rules in a fixed grammar. Each rule maps (a predicate over a pre-registered
    feature vocabulary, or a cue list) to a priority.
- *Execution:* deterministic code ranks items by summed priority, with recency as tie-break, and pins the top P tokens.
- *Updates:* every 10 feedback events, the LLM receives:
  - the table;
  - an outcome digest;
  - the provenance trail for each failure (what was pinned, unpinned or retrieved, and when);
  - ≤ 10 excerpts of missed items.

  It returns a diff. Invalid edits are no-ops. There is no rollback rule, because a rollback rule could do the work
  itself.
- *Shared start:* L1, L0, YOKED and SHUF-cal all start from the same outcome-blind table written by the LLM.
- *One model and one prompt.* L1 gets two samples on test, averaged per lifetime and never best-of-two. Every other
  LLM arm gets one.

**Baselines.** The §7 ladder: B0-B3, B6 (C\*, a hashed grid of ≤ 40 configurations, one chosen on validation),
C-T2\*, B7-B11, B13 (D-T2, behaviour clone run on-policy), NOLOG and DELAY×4 (manipulation arms, run on 8 train
lifetimes each and reported only), and B14-B15 offline only. B4 and B5
are not run, because D4 and SPECIALIZE are out of scope for E1 (§2.4, §5.2).

**Feedback.** Native outcomes only.
- The text is byte-identical across learning arms, verified by hash.
- No gold evidence ids unless the substrate natively provides provenance.
- No ground-truth fallback.
- Only fresh items are scored.

**Learned vs hard-coded.**
- *Learned:* the policy table only.
- *Deterministic, and why:*
  - log and hash chain: integrity, and memory loss must not be confounded with organization;
  - retriever: adaptive retrieval knobs showed ≤ 1.6 pp headroom;
  - table executor: keeps the learned object auditable and distillable;
  - metering: a known-correct implementation exists;
  - feedback extractor: parity across arms;
  - clock and scheduler: removing the clock alone cost the PM typed store 0.19 F1;
  - a frozen shared reader and a blind scorer, so arms differ only in context.

**Resource accounting** (per arm and per lifetime):
- measured active-context tokens per answer call; every arm must be within ±5% of B;
- organizer and reflection tokens (input, output and cached), reported separately;
- retrieval calls;
- storage: log bytes, pin-store tokens and table tokens;
- wall-clock time, with reflection off the critical path;
- cached and uncached cost;
- net value per million tokens.

**Primary outcomes.**
- O1: score on fresh items in test lifetimes.
- O2: Δ_inc = L1 − max(C\*, C-T2\*).
- O3: Δ_exp = L1 − L0; Δ_own = L1 − YOKED; Δ_credit = L1 − SHUF-cal.
- Secondary: an evidence-sufficiency proxy, total tokens, and the rate of invalid edits.

**Falsification** (paired over lifetimes, cluster bootstrap).
- *Preconditions,* checked first: the 95% lower bound must be > 0 for L1 − L0 and for L1 − N\*. If either fails, STOP.
- *Positive:* the point estimate of L1 − C\* ≥ δ, **and** the Holm-adjusted (m = 5) lower bounds are > 0 for each of
  L1 − C\*, L1 − C-T2\*, L1 − YOKED, L1 − SHUF-cal and L1 − COMPUTE-MATCHED. The last is the Q5 contrast: it
  compares against the same total compute spent on content-only reflection.
- Without an R0.7 pass, a positive supports Q3-Q5 under stationary demand only, not the shift part of the residue.
- *Negative:* the upper limit of the two-sided 90% CI (one-sided 95%) of L1 − max(C\*, C-T2\*) < δ.
- *Otherwise:* inconclusive, with no rescue.

With n_test = ⌈8.6σ²/δ²⌉ (SE ≈ 0.34δ) [COMPUTED]. The table models only the L1 − C\* contrast, so P(positive) is
an upper bound and P(negative) a lower bound:

| True effect | P(positive) | P(negative) |
|---|---|---|
| 0 | 0.00 | 0.90 |
| δ/4 | 0.01 | 0.71 |
| δ/2 | 0.07 | 0.43 |
| δ | 0.50 | 0.05 |
| 2δ | 1.00 | 0.00 |

This means n_test = 54, 89 and 138 for σ = 0.05 (the floor under R0.9's assumed LLM SD), 0.064 and 0.08.

**Validity and manipulation checks.**
- *The table actually changes:* ≥ 1 diff per 3 updates, and Jaccard similarity of L1's and L0's pin sets < 0.9.
- *Parsing:* ≥ 98% of outputs parse.
- *Time travel:* features recomputed from the prefix alone must match exactly.
- *Determinism:* FROZEN replays bit-identically.
- *Parity:* feedback hashes are identical across arms.
- *Contamination probe:* L0's score before vs after the model cutoff.
- *Scoring:* the judge is blind to arm, and the judge and the proxy must agree within N\*.
- *Calibration:* SHUF-cal is calibrated before any LLM run.
- *Credit channel:* NOLOG ≤ L1 − δ/2 on those 8 lifetimes. This is reported, not used in the decision.

**Held-out evaluation.**
- Split by hashed lifetime id:
  - train ≥ 20 lifetimes (priors, D);
  - validation ≥ 10 (one configuration per tier; L1 prompt frozen);
  - test n, used once.
- A shift set of ≥ 12 lifetimes from another domain, judged separately.
- Stage 1 pilot on 8 train lifetimes:
  1. Run 3 samples of L1 to measure σ_LLM, then recompute n. If n exceeds the available lifetimes, STOP.
  2. Compare need-AUC with experience in context (T3) against outcome-blind (T2). If the gain is < 0.02, STOP.

**Compressibility test** (pre-registered).
- (a) C-T0\* reproduces L1: the 90% upper bound of (L1 − C-T0\*) is < δ and, when L1 − N\* ≥ δ, the recovery lower
  bound is ≥ 0.8. Recovery is undefined when L1 ≈ N\*, and then only the gap clause applies. In that case LLM learning
  is unnecessary.
- (b) C-T2\* reproduces but C-T0\* does not: the LLM's value is perception, not organizational learning.
- (c) D-T2 reproduces: the learned policy is simple; the LLM is a sample-efficient learner.
- (d) L1's final table, replayed frozen on new lifetimes, reproduces L1: what was learned is a population prior, not
  something specific to the lifetime.
- *Calibration first.* On the substrate, positive controls (a cued teacher, an oracle teacher) must come out "not
  reproduced" and negative controls "reproduced". On git streams the gap clause discriminated correctly:
  - positive controls: teacher − distillate +0.134 and +0.305, recovery about 0;
  - negative controls: −0.0051 and +0.0023, upper 95% bounds ≤ +0.0044.

  The recovery clause did not discriminate there (0.00 and 0.46 for the negative controls), which is why it is
  restricted above.
- *Never use top-K decision agreement as the criterion.* It differed only modestly between controls (0.75-0.77 for
  negatives, 0.49-0.65 for positives), and nothing fixes a threshold for it in advance.

**API cost.** See §11. At the specified B = 16K, the reference case is about $4.8K (n = 54) to $7.8K (n = 89) at
Sonnet 5.5 list price, before contingency.

**What a positive would establish.** On one substrate and for one model, LLM-mediated revision of a FOCUS table beats
population-prior simple learners and its own controls at matched tokens. It would say nothing about PARK, COMPRESS,
SPECIALIZE or other models until replicated on a second R0 substrate.

**What a negative would establish.** For this model and prompt, LLM-mediated FOCUS learning does not beat simple
learners by δ on a substrate that passed R0, i.e. one with oracle headroom ≥ 2δ and lifetime-specific learnable room
whose lower bound is ≥ δ/2. That closes the line for this model generation. Mirroring postmortem rule 6, the registered E1 may be re-run
unchanged, once, when a new major model version is released. That re-run is report-only, and a positive permits only
a new decision memo. A negative does not establish the result for other models.

**What neither can establish:**
- "organization rather than task distribution" (U1);
- reader-attention effects beyond the proxies;
- generality across models. Cue response differed in sign across models on PM-Bench.

**How E1 could repeat Gate 0.**

| Risk | Guard |
|---|---|
| The designer picks the regime | R0.1 |
| The optimum is a known short rule | R0.6, with B15 hashed; the bar is C\* *with* a prior |
| Compressibility one level up | R0.4 ≥ 2δ |
| Thresholds written after the data | R0 hashed, fresh data only |
| Simulator-derived power presented as empirical | σ_LLM labelled as assumed; Stage 1 measures it |
| Deliberation cost ignored | Every token charged; COMPUTE-MATCHED arm |
| Rescue knobs | One model, one prompt, one feedback format |
| Demand effect of prompting | CUE-MATCHED arm |
| An uninformative gate kill | R0.8 |

### 9.3 Why E1 would survive the strongest baseline, or lose cleanly

The strongest baseline is the larger of N\* (store everything, retrieve, fixed side-indexes) and C\* (simple learner
with a population prior), both chosen on validation lifetimes at matched measured tokens. On every substrate where it was
measured (LoCoMo, BEAM-1M/10M, the PM-Bench generator, git streams), it already wins.

E1 could survive it only on a substrate where R0 has shown, before any spend, all three of:
- a ceiling above C\* of ≥ 2δ;
- learnable room over the prior with lower bound ≥ δ/2;
- that N\* does not dominate.

Even then, L1 must beat C\*, C-T2\* (the LLM's own outcome-blind perception handed to a simple learner), YOKED,
SHUF-cal and COMPUTE-MATCHED.

E1 loses cleanly because:
- the preconditions come first;
- the negative rule has 90% power at a true effect of 0;
- R0.3 and R0.4 make a positive plausible, though not guaranteed, so a negative is informative;
- one model and one prompt leave no forking paths.

## 10. Preregistration skeleton

For any future proposal under postmortem rule 7. This document registers nothing.

1. **Identity.** A new proposal, not a continuation. Date, owner, model identifier and sampling parameters.
2. **Hash manifest, committed before any computation on the registered data:**
   - R0 thresholds (JSON);
   - the substrate selection rule;
   - data snapshot hashes;
   - feature definitions;
   - the simple-learner grid (≤ 40 per tier);
   - L1 prompt and edit grammar;
   - the feedback extractor;
   - the scorer or judge rubric;
   - analysis code, seeds and split hashes.
3. **Hypotheses.** H1 and H0 (§9.2); δ; primary contrasts; what is explicitly not claimed (U1).
4. **R0** (§9.1). Includes the planted-effect simulation spec. Pass leads to Stage 1; kill or grey zone leads to stop.
5. **Stage 1.** Variance pilot and T3-vs-T2 elicitation; stop rules; the formula for recomputing n.
6. **Arms and information-parity contract.**
   - Identical observations, feedback text, retriever, budget and reader for every arm.
   - Forbidden information: gold evidence ids, generator metadata, future items, privileged probes.
7. **Accounting.** The fields in §9.2; cached and uncached cost.
8. **Analysis.** Estimands; paired lifetime cluster bootstrap; Holm with m = 5; one-sided 95% non-superiority test at δ.
   Parse failures and invalid edits are no-ops (the table is unchanged) and are counted.
9. **Decision rules.** Preconditions, then positive, negative or inconclusive.
10. **Compressibility test** (a)-(d), with positive and negative calibration controls.
11. **Validity checks**, and what each failure triggers.
12. **Deviation policy.** An append-only, hash-chained deviation log. No rescue knobs. The asymmetry rule applies:
    variants only to test whether a success generalizes.
13. **Reporting.** All runs, all arms, all seeds; cached and uncached cost.
14. **Kill criteria** K1-K10 (§12.3).

## 11. Engineering and API cost; the existing simulator

Prices are Anthropic list prices per million tokens, input/output, as cached on 2026-09-25: Opus 5.5 $4/$20, Sonnet
5.5 $2/$10, Haiku 4.5 $1/$5. The Batch API is 50% off, but it applies only to non-sequential calls.

| Item | API cost | Engineering |
|---|---|---|
| **This decision (NO-GO)** | **$0** | **0 further days** |
| R0-confirm, optional: a registered negative on fresh PM-Bench seed blocks and BEAM, with hashed thresholds and planted-effect checks | $0 | 2.5-4 days. Expected result: kill. The decision does not depend on it |
| *Avoided:* E-PARK-L (LLM learns PM-Bench resume conditions from delayed failure reports) | $205-410 at list price, about half with Batch. Per lifetime-arm: 312K in × $2 + 58.5K out × $10 = $1.21 (Sonnet) × 116 lifetime-arms = $140; Opus $281; +30% contingency; plus a read-time matcher arm, $23-46 | 5-7 days |
| *Avoided:* BEAM-L (LLM learns FOCUS on BEAM-1M) | $1,285 (Haiku) / $2,511 (Sonnet) once the missing compute-matched, map-reduce and salience arms are costed: +55% / +56% over the submitted $828 / $1,606. At 10M, $2,041-7,924 before the same correction | 8-10 days |
| *Avoided:* git-stream run | $487-1,948 including contingency | 8-11 days |
| **E1, only if a substrate ever passes R0** | Reference case: a LoCoMo-sized lifetime (154 feedback events), the specified B = 16K active context (about 17.5K input tokens per answer call), deterministic pin execution, and policy updates every 10 feedback events. Per test lifetime at Sonnet:
- 8 policy arms at about $5.5-5.9 each: L1, L0, YOKED, CUE-MATCHED, COMPUTE-MATCHED, SHUF-cal, the frozen-table replay for test (d), and N\*;
- the second L1 sample, at the same rate;
- answer calls for 6 controller arms at about $5.5 each: C\*, C-T2\*, D-T2, B0, B2, B3. N\* in the policy-arm list
  is the B1 arm.

That is about $84 in total. Pilot, outcome-blind T2 pass, and NOLOG and DELAY×4 on 8 lifetimes each come on top. **n = 54: about $4.8K. n = 89: about $7.8K. n = 121 (σ = 0.075): about $10.5K.** Haiku about half; Opus about double; add 25% contingency. Batching the non-learning arms saves up to about a third. Larger lifetimes add ingestion cost. [COMPUTED: arithmetic only. This corrects an earlier estimate that assumed a 2K active context.] | R0 on a new substrate: 3-5 days. E1 harness: 8-12 days |

**Money is not the binding constraint. The substrate is.**

**Should the existing simulator survive? Not for this question.** Sunk cost is not a reason to keep it.
- `devagents` runs single-task episodes, is centred on SPAWN, and has no context management at all: no eviction,
  summary, archive, retrieval, park or resume.
- Nothing persists across tasks. The window never binds below about $389 of simulated spend.
- Its runtime files are pinned by sha256 in the closed 0c pre-registration (`devagents/evals/exp0c.py`,
  `DECIDING_CODE` and `EXP0B_TREATMENT_FILES`). The Gate 0 audit also pins them, by path, against its genesis commit
  (`devagents/gate0/audit.py` lists `devagents/runtime/.*` in `PINNED`). Editing them would break the closed evidence
  trail and fail the 0c hash-identity tests in the 239-test suite.
- Gate 0 showed that a fully specified simulator of our own compresses to a contingent rule by construction.

So `devagents` stays frozen as the record of the closed experiments. Three domain-neutral patterns are worth reusing in
any new package:
- the `Ledger` (integer micro-dollars, conservation checked);
- the append-only, hash-chained, git-anchored audit core in `devagents/gate0/audit.py`;
- pre-registration by code hashing (`devagents/evals/exp0c.py`).

No new simulator should be written for this line. If the line reopens, the substrate must be external (R0.1).

## 12. GO / NO-GO / RESEARCH-FIRST

### 12.1 Decision: **NO-GO**

Stop the line "a persistent agent learns, through experience, to organize its own finite cognition", as posed. No API
spend and no harness build are authorized. No zero-API work is needed for the decision.

### 12.2 Reasons

1. **Almost nothing is learnable within a lifetime beyond a population prior** on any substrate where this was
   measured (LoCoMo, BEAM-1M/10M, the PM-Bench generator, git streams). The gain is at most +0.008 everywhere. It is
   small but positive on PM-Bench (+0.0054) and git (+0.0026), and negative on BEAM (§4.2 table).
   - The large oracle headroom that does exist (LoCoMo +20-29 pp, BEAM +0.15 to +0.47, git 0.976 against 0.580) is
     knowledge of future needs. On LoCoMo it is shown to be about *when*, not *whether*.
   - No feedback channel examined here reaches it. BEAM has 14 probes per lifetime, and its natural channel overlaps
     probe sources only 3%. In git, experience carries only the agent's own errors.
2. **Organization against the null.** No organization learned within a lifetime beat "store everything, retrieve
   well, add fixed typed side-indexes" wherever it could be computed.
   - Where anything beat it, it was fixed structure or a population-level model trained on other lifetimes (BEAM-1M:
     +0.028 to +0.047).
   - One genuine residual cell remains: aggregation beyond the read budget, which nothing tested here closed.
   - Implicit preferences and semantic cue matching are only partly closed.
   - In all three cells the natural competitors are *fixed* aggregates, extractors and matchers. They are therefore
     organization-vs-null questions, not learning questions.
3. **The alternative explanations cannot be separated at affordable scale** (§8.2):
   - U1 is structural;
   - U2 needs 128-1,133 lifetimes, against at most 41 valid natural ones examined (git: 4-12 after the model
     cutoff);
   - U3 means that synthetic regimes are the manipulation.

   The brief for this review applies: if these cannot be separated, say so and stop.
4. **The novelty that remains is small, and nearby work predicts a null.**
   - Generic online organization-policy learning is already reported: MemCon by bandit, AdaMem by LLM reflection.
     This rests on their abstracts.
   - Within-episode learned BRANCH, FOLD and ARCHIVE is published.
   - Most nearby results favour the simple learner:
     - language-driven bandits, the harness-evolution null and "Useful Memories Become Faulty" (abstracts only);
     - MemEvolve's shipped designs, which keep usage and success counters [CODE].

     AEL is mixed [CODE; ABSTRACT].
5. **Value of information.** Every conditional LLM run designed in this session for a reachable substrate is one of
   three kinds:
   - *can only fail:* E-PARK-L, where the headroom of 0.0079 is below δ;
   - *mostly inconclusive:* BEAM-L, where P(no claim | true effect 0) = 0.56-0.99 at 16 test lifetimes;
   - *decisive only toward a predicted negative,* in a regime its own designer calls practically irrelevant: git
     without the task text.

**Why not RESEARCH-FIRST.** The research-first steps were run in this session, at zero API cost, and each one killed:
- the LoCoMo Stage 0;
- a reduced form of the "learn from own outcomes vs frozen prior ≥ 0.04" exit test, on 8 PM-Bench lifetimes with no
  yoked arm (measured +0.0054; the clairvoyant ceiling of 0.0079 is already below 0.04);
- the BEAM gate;
- the PM-Bench gate;
- the git gate.

Reading the full texts of ContextEvo, MemCon and AdaMem could move the novelty assessment either way. It cannot
create headroom on a substrate, and the NO-GO rests on headroom. "Don't Lose the Thread" turned out to be CORAL, a within-episode method withdrawn from ICLR 2026. The
reading is still recommended, as half a day of work, before anyone cites this decision externally.

### 12.3 What would reopen the line, and what would kill it again

- **Re-entry:** only as a new proposal under postmortem rule 7, and only with a substrate that passes R0 (§9.1) on
  fresh data with thresholds hashed first.
- **The one regime not tested** is real long-term deployment logs with all three of:
  - hidden demand that recurs by theme and changes over time;
  - dense implicit feedback;
  - at least 84 lifetimes (R0.1).

  No such data was reachable, and building it synthetically repeats Gate 0.

**Kill criteria** (pre-registrable):
- **K0, in force now:** any LLM spend requires an R0 pass on fresh data.
- **K1:** R0.3 upper bound < δ/2.
- **K2:** R0.4 < δ.
- **K3:** R0.2 < 20 events per lifetime, or < 10% fresh-need overlap.
- **K4:** fewer than 30 + n_test lifetimes (R0.1), or fewer test lifetimes than R0.9 requires.
- **K5:** best implementable organization ≤ N\*.
- **K6:** a known ≤ 2-line or textbook rule within δ/2 of the ceiling.
- **K7:** the gate is insensitive (R0.8).
- **K8:** Stage 1 T3 − T2 need-AUC < 0.02, or the recomputed n exceeds the available lifetimes.
- **K9, after E1:**
  - a failed precondition or a negative result closes the line for the current model generation. The only exception
    is the single unchanged, report-only re-run on a new major model version (§9.2);
  - a positive that (a) or (d) reproduces is downgraded to "not experiential organization learning";
  - a positive that (b) or (c) reproduces is downgraded to "perception" or "sample-efficient learner";
  - any surviving positive needs a second R0 substrate.
- **K10, novelty:** if ContextEvo, MemCon or AdaMem already compares LLM-mediated organization learning against simple
  learners given the same feedback, the comparison is no longer a contribution either.

### 12.4 What this decision does not say

- **It does not say that organization is worthless.** Where no query exists at the moment of need, fixed write-time
  structure was worth 36 points of Set-F1 on PM-Bench and 56-95 points of instruction-source coverage on BEAM
  (§4.1).
- **It does not say that LLMs cannot organize context.** Learned within-episode folding works (§3.1).
- **It does not say that adaptive organization is impossible** (§1.2 h). The claim is narrower: on every substrate
  where it was measured, *learning through experience* adds at most +0.008 over what a population prior, a counter
  or a fixed rule already captures, and the contrasts that would show more are below detection. Organization learned
  *across* lifetimes, i.e. a population model, did add value on BEAM-1M.
- **What was measured, and what was only scoped out.**
  - The evidence covers D1 keep/evict/pin and learned matching of user-given PARK conditions.
  - SPECIALIZE, MERGE, whole-context RETIRE, persistent BRANCH, agent-chosen PARK, and COMPRESS on a substrate that
    can discriminate were *not measured*. They were scoped out on novelty and confound grounds (§2.4, §5.2), or no
    reachable substrate supports them.
  - The NO-GO for those levers rests on that scoping, on prior art, and on the identifiability dilemma (§8.2), not on
    a measured null.
- **Out of scope:** the one surviving question that is *not* about learning, fixed write-time aggregates vs read-time
  map-reduce beyond 1M tokens. On BEAM-1M at a 64K budget, a population pin set raised aggregate coverage from 0.27 to
  0.415 [COMPUTED]. That would be a separate proposal.

## Appendix A: Provenance of computed numbers

These analyses ran in this session without any model API. They are not committed, because this decision commits
only this document. They can be reproduced from the descriptions below and from the public data. Each was run by an
analysis agent and spot-checked against its output file before being cited here.

| Analysis | Data | What it computed | Cited in |
|---|---|---|---|
| Retrieval null | LoCoMo (`locomo10.json`), BEAM 1M/10M (`mohammadtavakoli78/BEAM`), PM-Bench seeds 42/7, MQuAKE-CF-3k-v2 | BM25 (own implementation) and MiniLM evidence recall by category; 20-configuration retrieval knob sweep with per-chat hindsight and per-probe oracle; regex pin store; non-LLM typed intention store with ablations | §4.1 |
| Simple-learner audit | LoCoMo, with seeded question timing after the last evidence | Write-time keep/evict controllers (FIFO, ACT-R, counters, logistic, bandit, population prior) vs matched-budget retrieval vs an exact ILP clairvoyant oracle; predictor-quality sweep; recency-biased demand | §4.2 |
| Alternative explanations | PM-Bench released runs; Context-Folding Table 1; LoCoMo | Heartbeat cue response by model; learning × architecture interaction; feedback leakage; within-lifetime vs population AUC; power and cost per lifetime | §8 |
| Benchmark survey | AgingBench (generated S2/S3/S6), Memora, LifelongAgentBench (vendored in MemRL), and the above | Demand uniformity, horizon in tokens, write-time predictability, store-all vs proxies | §6 |
| Delayed credit | LoCoMo; PrefEval; PM-Bench v9 generator: one 40-week stationary lifetime (seeds 101-140), 8 shift lifetimes (seeds 10001-10160 in regime A, 20001-20160 and 30001-30160 in regime B), and two rejected partitions (seeds 2001-2005, 3001-3008) | Post-hoc blame search; generalization AUC; park-by-domain routing; LoCoMo session summaries vs archive + retrieval (answer-stem proxy); delayed-report learners (memorizer, logistic, population prior), clairvoyant trigger, hindsight one-line rules | §4.2, §5, §9 |
| BEAM gate | BEAM 1M (31 valid chats) / 10M | Clairvoyant pin headroom over cross-fitted N\*; population pins; lifetime-specific optimum; in-stream learning value; feedback reach; annotation audit (4 of 35 chats have shifted source ids) | §4.2, §9.1 |
| Git streams | 37 public repositories, 55,151 scored commits | Resident-file paging with K = 16; ACT-R and learned controllers; cross-fitted lifetime ceiling; calibrated distillation test with positive and negative controls | §4.2, §6, §9.2 |
| Judges, synthesis and fact-check | Outputs of the above | Planted-effect sensitivity of the BEAM split-half test; fair recomputation against cross-fitted N\*; operating characteristics of the E1 rule; cost recomputation, including the E1 reference cost at B = 16K | §9, §11 |

**Contamination.** Every dataset and seed block in this table has been examined. None can serve as blind data for a
registered gate.

**Fact-check.** Before commit, six adversarial checkers reviewed this document: repository citations, literature,
computed numbers, logic and coverage, arithmetic, and completeness. No issue they found reversed the decision. The
fixes they required are incorporated.

## Appendix B: Sources and access limits

**Read in full or in code:**
- Context-Folding v1 PDF (via a GitHub mirror) and `sunnweiwei/FoldAgent` at 58a2d69;
- PM-Bench code, data and released logs;
- ACE (`ace-agent/ace`, `ace-appworld`) and its released playbooks;
- MemGPT paper v2 (PDF from a Letta release tag); MemGPT 0.1.6 / Letta V1 (archive branch), `letta-code`,
  `sleep-time-compute` (code only);
- MemRL, MemexRL, MemEvolve, ALMA, MemSkill, Mem-α, AgingBench, Supersede, MemoryAgentBench, CLM, the Complexity
  Trap, DGM, HGM, ADAS, Gödel Agent, SICA, AEL, EvoChamber;
- Kimi K2.5 report PDF; Evo-Memory and MemAct PDFs;
- `dynamic-cheatsheet`, `reasoning-bank` and `agent-workflow-memory` (code).

**Abstract, snippet or list level only:**
- ContextEvo, MemCon, AdaMem, AdaCoM, CORAL ("Don't Lose the Thread"), Auto-Dreamer, Memory Worth, TraceRetain,
  "Closing the Feedback Loop", Ground Truth First, PIS, BudgetPM, Memory-R1/R2, Mem-T, MemBuilder, MEM1, AgeMem,
  AgentFold, MemPO, MMPO;
- the paper bodies of PM-Bench, ACE and Memory-R1. Memory-R1 has released no official code; a third-party
  re-implementation was read.

**Recalled from memory, with no source read:** the sleep-time compute numbers.

**Blocked:** arXiv, openreview, Hugging Face, Semantic Scholar, most publisher hosts. The web-search quota was used up
partway through.

**Search coverage for the novelty check:**
- a GitHub-hosted mirror of arXiv listings (92,059 abstracts, 2025-03-18 to 2026-09-07);
- the ICLR and ICML 2026 paper lists;
- curated "awesome" lists up to 2026-09-30.

Papers from 2026-09-08 to 2026-10-03 not on those lists are not covered.

**Corrections to earlier passes in this session** (recorded so that they are not repeated):
- MemRL has no memory-eviction policy. Its FIFO evicts from a database cache.
- AEL does not show LLM components hurting relative to simple learners. LLM reflection beat the stateless baseline;
  mechanisms added on top hurt.
- "Don't Lose the Thread" is CORAL: within-episode, withdrawn from ICLR 2026.
- The PM-Bench menu gives exact one-step feedback on selected tasks. It does not give "no feedback".
- The PM-Bench TODO ledger is an aid capped at 5 items, added to the full history. It is not a capacity-limited
  store.
- PM-Bench's hierarchical "specialist" result (45.2%) is confounded (day plans omitted, step time leaked). It cannot
  support any claim about SPECIALIZE.
