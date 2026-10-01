"""Gate-0 commands (GATE_0_SPEC.md §6): `verify` (offline integrity; evaluates nothing), `genesis`, `calibrate --round
N` (the only command that evaluates candidates; every evaluation is logged before it starts), `defect` and `decide`.

    python -m devagents.gate0 verify
    python -m devagents.gate0 calibrate --round 1
"""

from __future__ import annotations

import hashlib
import json
import traceback
from pathlib import Path

from devagents.config import ROOT, Constants, load_frozen
from devagents.gate0.audit import (ACCEPTANCE_PATH, AUDIT_PATH, CANDIDATES_1, GATE0_DIR, SPEC_PATH, Audit, AuditError,
                                   canonical, sha256_lf)
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
    """JSON-safe copy: infinities and NaN (infeasible plans) become null."""
    if isinstance(obj, float):
        return obj if obj == obj and abs(obj) != float("inf") else None
    if isinstance(obj, dict):
        return {str(k): _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


def run_analysis(instances, acc: dict, constants: Constants, progress=print) -> tuple[dict, dict]:
    """Measure, analyze and assess follow-up feasibility. Returns (results without metadata, records)."""
    k_max = constants.compute.max_concurrency - 1
    conds, base_cond = conditions(acc, constants)
    recs = measure(instances, conds, k_max, progress)
    analysis = analyze(recs, instances, conds, base_cond, acc, k_max)
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
        progress(f"power: {len(cells)} qualifying cells, {len(valid)} control worlds")
    feas = feasibility(cells, len(valid), acc["power"], constants, grid_min)
    feas["control_worlds_valid"], feas["control_worlds_rejected"] = valid, rejected
    analysis["criteria"]["G9_power"] = {
        "pass": bool(feas.get("pass")), "power_presentation": feas.get("primary_presentation", {}).get("all"),
        "power_deliberation": feas.get("deliberation", {}).get("all"), "allocation": feas.get("allocation"),
        "runs": feas.get("runs"), "reason": feas.get("reason")}
    return {"decision": decide(analysis["criteria"]), **analysis, "followup": feas}, compact_records(recs)


def evaluate_round(round_no: int, candidates_path: Path, *, acc_path: Path = ACCEPTANCE_PATH,
                   audit: Audit | None = None, out_dir: Path | None = None, spec_path: Path | None = SPEC_PATH,
                   require_clean: bool = True, progress=print) -> dict:
    """Evaluate one candidate set. Cheap validation first; the audit entry is appended before anything is simulated;
    a crash is recorded as an INDETERMINATE completion before it propagates."""
    audit = audit or Audit()
    acc = load_json(acc_path)
    cand = load_json(candidates_path)
    if cand.get("round") != round_no:
        raise AuditError(f"{candidates_path} declares round {cand.get('round')}, not {round_no}")
    constants = base_constants(acc)
    conditions(acc, constants)
    instances = build_instances(cand)
    digests = {i.id: i.digest() for i in instances}
    cand_sha = sha256_lf(candidates_path)
    started = audit.begin_evaluation(round_no, cand_sha, acc_path, acc, digests, spec_path=spec_path,
                                     require_clean=require_clean)
    k = started["payload"]["evaluation"]
    out_dir = Path(out_dir or GATE0_DIR / f"round{round_no}" / f"eval{k}")
    try:
        results, records = run_analysis(instances, acc, constants, progress)
        out_dir.mkdir(parents=True, exist_ok=True)
        rec_path = out_dir / "records.json"
        rec_path.write_text(canonical(_finite(records)) + "\n", encoding="utf-8", newline="\n")
        results = {"round": round_no, "evaluation": k, "audit_seq": started["seq"],
                   "acceptance_sha": sha256_lf(acc_path), "candidates_sha": cand_sha, "instances": digests,
                   "git": started["payload"]["git"], "records_sha": sha256_lf(rec_path), **results}
        res_path = out_dir / "results.json"
        res_path.write_text(json.dumps(_finite(results), indent=1, sort_keys=True, default=str) + "\n",
                            encoding="utf-8", newline="\n")
    except BaseException as exc:
        audit.complete_evaluation(round_no, "", {"decision": "INDETERMINATE", "evaluation": k,
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
    """Offline integrity of the Gate-0 trail. Evaluates no candidate."""
    audit = audit or Audit()
    problems = list(audit.verify())
    g = audit.genesis()
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
    rounds = {}
    try:
        rounds = audit.rounds()
    except AuditError as exc:
        problems.append(str(exc))
    for n, r in rounds.items():
        path = GATE0_DIR / f"candidates_round{n}.json"
        if not path.exists() or sha256_lf(path) != r["candidates_sha"]:
            problems.append(f"round {n}: the candidate file does not match its registration")
        for c in r["completed"]:
            if not c.get("results_sha"):
                continue  # an aborted evaluation (INDETERMINATE, no results)
            res = GATE0_DIR / f"round{n}" / f"eval{c['evaluation']}" / "results.json"
            if not res.exists() or sha256_lf(res) != c["results_sha"]:
                problems.append(f"round {n} evaluation {c['evaluation']}: results.json does not match the audit")
    return {"ok": not problems, "problems": problems, "acceptance_sha": acc_sha, "entries": len(audit.entries()),
            "rounds": {n: {"evaluations": len(r["evaluations"]), "decision": r["decision"]} for n, r in rounds.items()}}


def cli(a) -> int:
    path = Path(a.audit) if getattr(a, "audit", None) else AUDIT_PATH
    if a.action != "verify" and path.resolve() != AUDIT_PATH.resolve():
        raise AuditError("only `verify` may use an audit file other than data/gate0/audit.jsonl")
    audit = Audit(path)
    if a.action == "verify":
        res = verify(audit)
    elif a.action == "genesis":
        res = audit.write_genesis(ACCEPTANCE_PATH, SPEC_PATH, CANDIDATES_1, a.note or "")
    elif a.action == "calibrate":
        res = evaluate_round(a.round, GATE0_DIR / f"candidates_round{a.round}.json", audit=audit)
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
