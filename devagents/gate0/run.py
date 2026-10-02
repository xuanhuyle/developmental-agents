"""Gate-0 commands (GATE_0_SPEC.md §6): `verify` (offline integrity; evaluates nothing), `genesis`, `calibrate --round
N` (the only command that evaluates candidates), `defect` and `decide`.

`calibrate` runs in two phases on the official audit: the first call appends `evaluation_started` and stops; after
that entry is committed and pushed, the second call simulates. Nothing outcome-bearing is printed before the
evaluation's completion is logged.

    python -m devagents.gate0 verify
    python -m devagents.gate0 calibrate --round 1     # registers evaluation k; commit and push the audit
    python -m devagents.gate0 calibrate --round 1     # runs evaluation k
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import traceback
from pathlib import Path

from devagents.config import ROOT, Constants, load_frozen
from devagents.gate0.audit import (ACCEPTANCE_PATH, AUDIT_PATH, CANDIDATES_1, GATE0_DIR, SPEC_PATH, Audit, AuditError,
                                   canonical, is_ancestor, sha256_lf)
from devagents.gate0.evaluate import View, analyze, conditions, features, measure
from devagents.gate0.power import control_worlds, feasibility, followup_inputs
from devagents.gate0.worlds import build_instances


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def base_constants(acc: dict) -> Constants:
    src = acc["constants"]
    raw = load_frozen(ROOT / src["source"])[src["key"]]
    got = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if got != src["sha256_canonical"]:
        raise AuditError(f"the constants changed: {got} != {src['sha256_canonical']}")
    return Constants.from_json(raw)


def validate_candidates(round_no: int, candidates_path: Path, acc: dict):
    """Cheap checks that need no simulation: the declared round, the constants, the conditions, the worlds."""
    cand = load_json(candidates_path)
    if cand.get("round") != round_no:
        raise AuditError(f"{candidates_path} declares round {cand.get('round')}, not {round_no}")
    constants = base_constants(acc)
    conditions(acc, constants)
    instances = build_instances(cand)
    return constants, instances, {i.id: i.digest() for i in instances}


def decide(criteria: dict) -> str:
    if not criteria["G1_integrity"]["pass"]:
        return "INDETERMINATE"
    return "PASS" if all(v["pass"] for v in criteria.values()) else "FAIL"


def compact_records(recs: dict) -> dict:
    cols = ["instance", "regime", "member", "plan", "cond", "outcome", "quality", "info_complete", "elapsed_s",
            "money_usd", "llm_calls", "in_tokens", "out_tokens", "agents", "root_calls", "max_child_calls",
            "invalid_actions", "cap_hits", "termination_reasons", "signature", "t_reveal", "pre_reveal", "t0_state"]
    rows = [[*k, *(rec[c] for c in cols[5:])] for k, rec in sorted(recs.items())]
    return {"columns": cols, "rows": rows}


def _finite(obj):
    """JSON-safe copy: non-finite numbers become the strings "inf", "-inf" and "nan" (an infeasible plan is "-inf")."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return "nan" if obj != obj else ("inf" if obj > 0 else "-inf")
    if isinstance(obj, dict):
        return {str(k): _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


def run_analysis(instances, acc: dict, constants: Constants, progress=print, checkpoint=None) -> tuple[dict, dict]:
    """Measure, analyze and assess follow-up feasibility. Returns (results without metadata, records).
    `checkpoint` receives the decision on G1-G8 before the (long) power step; it is logged, so an abort after a FAIL
    is already determined still records a FAIL."""
    k_max = constants.compute.max_concurrency - 1
    conds, base_cond = conditions(acc, constants)
    recs = measure(instances, conds, k_max, progress)
    analysis = analyze(recs, instances, conds, base_cond, acc, k_max)
    pre = decide(analysis["criteria"])
    if checkpoint:
        checkpoint({"pre_power_decision": "PENDING_G9" if pre == "PASS" else pre,
                    "criteria": {k: v["pass"] for k, v in analysis["criteria"].items()}})
    qualifying = analysis["criteria"]["G3_G4_qualifying"]["qualifying"]
    feats = {(inst.id, r, m.key): features(inst, m, constants.sources)
             for inst in instances for r in constants.regimes for m in inst.members}
    views = {c: View(recs, instances, c, k, k_max, acc["delta"], feats) for c, _, k in conds if c.startswith("g")}
    base = views[base_cond]
    cost = acc["power"]["cost"]
    cells = followup_inputs(recs, base, qualifying, constants, cost)
    per_grid = {g: {c.key: c for c in followup_inputs(recs, v, qualifying, constants, cost)} for g, v in views.items()}
    grid_min = [min((per_grid[g][c.key] for g in per_grid), key=lambda x: sum(x.a[m] - x.b[m] for m in x.a))
                for c in cells]
    valid, rejected = control_worlds(base, qualifying, acc["delta"])
    if progress:
        progress("power analysis (several minutes)")
    feas = feasibility(cells, len(valid), acc["power"], constants, grid_min)
    feas["control_worlds_valid"], feas["control_worlds_rejected"] = valid, rejected
    analysis["criteria"]["G9_power"] = {
        "pass": bool(feas.get("pass")),
        "power_presentation": feas.get("presentation", {}).get("primary", {}).get("all"),
        "power_deliberation": feas.get("deliberation", {}).get("primary", {}).get("all"),
        "allocation_presentation": feas.get("presentation", {}).get("allocation"),
        "allocation_deliberation": feas.get("deliberation", {}).get("allocation"),
        "reason": feas.get("reason")}
    return {"decision": decide(analysis["criteria"]), **analysis, "followup": feas}, compact_records(recs)


def evaluate_round(round_no: int, candidates_path: Path, *, acc_path: Path = ACCEPTANCE_PATH,
                   audit: Audit | None = None, out_dir: Path | None = None, spec_path: Path | None = SPEC_PATH,
                   progress=print) -> dict:
    """Evaluate one candidate set. Phase 1 appends `evaluation_started` (on the official audit it then stops, until the
    entry is committed and pushed); phase 2 checks the published start and simulates. An abort is recorded as a
    completion: FAIL if G1-G8 had already failed, INDETERMINATE otherwise."""
    audit = audit or Audit()
    acc = load_json(acc_path)
    constants, instances, digests = validate_candidates(round_no, candidates_path, acc)
    cand_sha = sha256_lf(candidates_path)
    started = audit.pending_start(round_no)
    if started is None:
        started = audit.begin_evaluation(round_no, cand_sha, acc_path, acc, digests, spec_path=spec_path)
        if audit.anchored:
            return {"registered": True, "round": round_no, "evaluation": started["payload"]["evaluation"],
                    "audit_seq": started["seq"],
                    "next": f"commit and push {audit.rel}, then run `calibrate --round {round_no}` again to execute it"}
    k = started["payload"]["evaluation"]
    out_dir = Path(out_dir or GATE0_DIR / f"round{round_no}" / f"eval{k}")
    audit.confirm_start(round_no, cand_sha, digests, out_dir, acceptance_path=acc_path, spec_path=spec_path)
    pre: dict = {}

    def checkpoint(payload):
        pre.update(payload)
        audit.progress(round_no, k, payload)
    try:
        results, records = run_analysis(instances, acc, constants, progress, checkpoint)
        out_dir.mkdir(parents=True)
        rec_path = out_dir / "records.json"
        rec_path.write_text(canonical(_finite(records)) + "\n", encoding="utf-8", newline="\n")
        results = {"round": round_no, "evaluation": k, "audit_seq": started["seq"],
                   "acceptance_sha": sha256_lf(acc_path), "candidates_sha": cand_sha, "instances": digests,
                   "git": started["payload"]["git"], "interpreter": started["payload"]["interpreter"],
                   "records_sha": sha256_lf(rec_path), **results}
        res_path = out_dir / "results.json"
        res_path.write_text(json.dumps(_finite(results), indent=1, sort_keys=True, default=str) + "\n",
                            encoding="utf-8", newline="\n")
    except BaseException as exc:
        decision = "FAIL" if pre.get("pre_power_decision") == "FAIL" else "INDETERMINATE"
        audit.complete_evaluation(round_no, "", {"decision": decision, "evaluation": k, "aborted": True,
                                                 "started_seq": started["seq"],
                                                 "error": f"{type(exc).__name__}: {exc}",
                                                 "traceback_sha": hashlib.sha256(
                                                     traceback.format_exc().encode()).hexdigest()})
        raise
    audit.complete_evaluation(round_no, sha256_lf(res_path), {
        "decision": results["decision"], "evaluation": k, "started_seq": started["seq"],
        "records_sha": results["records_sha"], "criteria": {c: v["pass"] for c, v in results["criteria"].items()},
        "qualifying": results["criteria"]["G3_G4_qualifying"]["qualifying"]})
    return results


def verify(audit: Audit | None = None) -> dict:
    """Offline integrity of the Gate-0 trail (local git only). Evaluates no candidate."""
    audit = audit or Audit()
    problems = list(audit.verify())
    try:
        g, n_entries = audit.genesis(), len(audit.entries())
    except (AuditError, ValueError):
        g, n_entries = None, None
    acc_sha = sha256_lf(ACCEPTANCE_PATH)
    if g is None:
        problems.append("no genesis entry")
    else:
        gp = g["payload"]
        if gp["acceptance_sha"] != acc_sha:
            problems.append("acceptance.json differs from the hash pinned in genesis")
        if gp["spec_sha"] != sha256_lf(SPEC_PATH):
            problems.append("GATE_0_SPEC.md differs from the hash pinned in genesis")
        if gp["candidates_round1_sha"] != sha256_lf(CANDIDATES_1):
            problems.append("candidates_round1.json differs from the hash pinned in genesis")
    if audit.anchored and n_entries is not None:
        problems += audit.history_problems()
        for e in audit.entries():
            h = e["payload"].get("git", {}).get("head", "")
            if e["kind"] in ("genesis", "round_registered", "evaluation_started", "defect", "decision") and (
                    not re.fullmatch(r"[0-9a-f]{40}", h) or not is_ancestor(h, "HEAD", audit.root)):
                problems.append(f"entry {e['seq']} ({e['kind']}) has no verified commit in HEAD's history")
    rounds = {}
    try:
        rounds = audit.rounds()
    except AuditError as exc:
        problems.append(str(exc))
    expected = set()
    for n, r in rounds.items():
        path = GATE0_DIR / f"candidates_round{n}.json"
        if not path.exists() or sha256_lf(path) != r["candidates_sha"]:
            problems.append(f"round {n}: the candidate file does not match its registration")
        for c in r["completed"]:
            if not c.get("results_sha"):
                continue  # an aborted evaluation (no results)
            d = GATE0_DIR / f"round{n}" / f"eval{c['evaluation']}"
            expected.add(d)
            res = d / "results.json"
            if not res.exists() or sha256_lf(res) != c["results_sha"]:
                problems.append(f"round {n} evaluation {c['evaluation']}: results.json does not match the audit")
            rec = d / "records.json"
            if not rec.exists() or sha256_lf(rec) != c.get("records_sha"):
                problems.append(f"round {n} evaluation {c['evaluation']}: records.json does not match the audit")
    for d in sorted(GATE0_DIR.glob("round*/eval*")):
        if d not in expected and audit.anchored:
            problems.append(f"{d.relative_to(ROOT).as_posix()} has no completed evaluation in the audit")
    return {"ok": not problems, "problems": problems, "acceptance_sha": acc_sha, "entries": n_entries,
            "rounds": {n: {"evaluations": len(r["evaluations"]), "decision": r["decision"]} for n, r in rounds.items()}}


def cli(a) -> int:
    path = Path(a.audit) if getattr(a, "audit", None) else AUDIT_PATH
    if a.action != "verify" and path.resolve() != AUDIT_PATH.resolve():
        raise AuditError("only `verify` may use an audit file other than data/gate0/audit.jsonl")
    audit = Audit(path)
    if a.action == "verify":
        res = verify(audit)
    elif a.action == "genesis":
        acc = load_json(ACCEPTANCE_PATH)
        _, _, digests = validate_candidates(1, CANDIDATES_1, acc)
        res = audit.write_genesis(ACCEPTANCE_PATH, SPEC_PATH, CANDIDATES_1, a.note or "", instances=digests)
    elif a.action == "calibrate":
        res = evaluate_round(a.round, GATE0_DIR / f"candidates_round{a.round}.json", audit=audit)
        if not res.get("registered"):
            res = {"decision": res["decision"], "criteria": {k: v["pass"] for k, v in res["criteria"].items()},
                   "qualifying": res["criteria"]["G3_G4_qualifying"]["qualifying"]}
    elif a.action == "defect":
        res = audit.log_defect(a.round, a.note, a.fix_commit, a.regression_test)
    elif a.action == "decide":
        res = audit.decide(a.round, a.decision, a.note or "")
    else:
        raise ValueError(a.action)
    print(json.dumps(res, indent=1, default=str))
    return 0 if not (a.action == "verify" and not res["ok"]) else 1
