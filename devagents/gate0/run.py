"""Gate-0 commands (GATE_0_SPEC.md §6): `verify` (offline integrity; evaluates nothing), `genesis`, `calibrate --round
N` (the only command that evaluates candidates; every evaluation is logged before it starts), `defect` and `decide`.

    python -m devagents.gate0 verify
    python -m devagents.gate0 calibrate --round 1
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from devagents.config import ROOT, Constants, load_frozen
from devagents.gate0.audit import (ACCEPTANCE_PATH, AUDIT_PATH, GATE0_DIR, SPEC_PATH, Audit, AuditError, canonical,
                                   sha256_lf)
from devagents.gate0.evaluate import View, analyze, conditions, measure
from devagents.gate0.power import feasibility, followup_inputs
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


def evaluate_round(round_no: int, candidates_path: Path, *, acc_path: Path = ACCEPTANCE_PATH,
                   audit: Audit | None = None, out_dir: Path | None = None, require_clean: bool = True,
                   progress=print) -> dict:
    """Evaluate one candidate set. The audit entry is appended before anything is simulated."""
    audit = audit or Audit()
    acc = load_json(acc_path)
    cand = load_json(candidates_path)
    if cand.get("round") != round_no:
        raise AuditError(f"{candidates_path} declares round {cand.get('round')}, not {round_no}")
    instances = build_instances(cand)
    digests = {i.id: i.digest() for i in instances}
    cand_sha = sha256_lf(candidates_path)
    started = audit.begin_evaluation(round_no, cand_sha, acc_path, acc, digests, require_clean=require_clean)
    constants = base_constants(acc)
    k_max = constants.compute.max_concurrency - 1
    conds, base_cond = conditions(acc, constants)
    recs = measure(instances, conds, k_max, progress)
    analysis = analyze(recs, instances, conds, base_cond, acc, k_max)
    qualifying = analysis["criteria"]["G3_G4_qualifying"]["qualifying"]
    view = View(recs, instances, base_cond, constants, k_max, acc["delta"])
    cells = followup_inputs(recs, view, qualifying, constants)
    if progress:
        progress(f"power: {len(cells)} qualifying cells")
    feas = feasibility(cells, acc["power"], constants)
    analysis["criteria"]["G9_power"] = {"pass": bool(feas.get("pass")), "power": feas.get("primary", {}).get("all"),
                                        "allocation": feas.get("allocation"), "runs": feas.get("runs"),
                                        "reason": feas.get("reason")}
    decision = decide(analysis["criteria"])
    out_dir = Path(out_dir or GATE0_DIR / f"round{round_no}")
    out_dir.mkdir(parents=True, exist_ok=True)
    records = compact_records(recs)
    rec_path = out_dir / "records.json"
    rec_path.write_text(canonical(records) + "\n", encoding="utf-8", newline="\n")
    results = {"round": round_no, "evaluation": started["payload"]["evaluation"], "audit_seq": started["seq"],
               "acceptance_sha": sha256_lf(acc_path), "candidates_sha": cand_sha, "instances": digests,
               "git": started["payload"]["git"], "records_sha": sha256_lf(rec_path), "conditions":
               [{"name": c, "assumptions": vars(a), "perturbed": c.startswith("p:")} for c, a, _ in conds],
               "decision": decision, **analysis, "followup": feas}
    res_path = out_dir / "results.json"
    res_path.write_text(json.dumps(results, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8",
                        newline="\n")
    audit.complete_evaluation(round_no, sha256_lf(res_path), {
        "decision": decision, "records_sha": results["records_sha"],
        "criteria": {k: v["pass"] for k, v in analysis["criteria"].items()},
        "qualifying": qualifying})
    return results


def verify(audit: Audit | None = None) -> dict:
    """Offline integrity of the Gate-0 trail. Evaluates no candidate."""
    audit = audit or Audit()
    problems = list(audit.verify())
    g = audit.genesis()
    acc_sha = sha256_lf(ACCEPTANCE_PATH)
    if g is None:
        problems.append("no genesis entry")
    elif g["payload"]["acceptance_sha"] != acc_sha:
        problems.append("acceptance.json differs from the hash pinned in genesis")
    for n, r in audit.rounds().items():
        path = GATE0_DIR / f"candidates_round{n}.json"
        if not path.exists() or sha256_lf(path) != r["candidates_sha"]:
            problems.append(f"round {n}: the candidate file does not match its registration")
        if r["completed"]:
            res = GATE0_DIR / f"round{n}" / "results.json"
            if not res.exists() or sha256_lf(res) != r["completed"][-1]["results_sha"]:
                problems.append(f"round {n}: results.json does not match the last completed evaluation")
    return {"ok": not problems, "problems": problems, "acceptance_sha": acc_sha, "entries": len(audit.entries()),
            "rounds": {n: {"evaluations": len(r["evaluations"]), "decision": r["decision"]}
                       for n, r in audit.rounds().items()}}


def cli(a) -> int:
    audit = Audit(Path(a.audit) if getattr(a, "audit", None) else AUDIT_PATH)
    if a.action == "verify":
        res = verify(audit)
    elif a.action == "genesis":
        res = audit.write_genesis(ACCEPTANCE_PATH, SPEC_PATH, a.note or "")
    elif a.action == "calibrate":
        res = evaluate_round(a.round, GATE0_DIR / f"candidates_round{a.round}.json", audit=audit)
        res = {"decision": res["decision"], "criteria": {k: v["pass"] for k, v in res["criteria"].items()},
               "qualifying": res["criteria"]["G3_G4_qualifying"]["qualifying"]}
    elif a.action == "defect":
        res = audit.log_defect(a.round, a.note, a.fix_commit, a.regression_test)
    elif a.action == "decide":
        last = audit.rounds()[a.round]["completed"][-1]["decision"]
        if a.decision != last:
            raise AuditError(f"the decision must be the last evaluation's mechanical decision ({last})")
        res = audit.decide(a.round, a.decision, a.note or "")
    else:
        raise ValueError(a.action)
    print(json.dumps(res, indent=1, default=str))
    return 0 if not (a.action == "verify" and not res["ok"]) else 1
