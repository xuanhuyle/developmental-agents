"""Append-only, hash-chained Gate-0 calibration audit (GATE_0_SPEC.md §6).

Every line of data/gate0/audit.jsonl is one entry: {"seq", "prev", "kind", "time", "payload", "hash"}, where `hash`
is the SHA-256 of the canonical JSON of the other fields and `prev` is the previous entry's hash. The first entry
(`genesis`) pins the acceptance specification's hash before any candidate evaluation.

Round rules, enforced by `begin_evaluation` (and therefore by every evaluation the harness performs):
- the acceptance file's current hash must equal the hash pinned in genesis;
- a round is registered once, with one candidate-set hash; at most `rounds.max` rounds exist;
- round n > 1 may be registered only after round n - 1 ended with a FAIL decision;
- a registered round may be evaluated once, and re-evaluated (same candidate set) only after a logged `defect` entry,
  at most `rounds.max_reevaluations` times; a round with a `decision` entry is closed;
- the code must be committed: evaluation refuses a dirty working tree for code, specs and acceptance files.

What this cannot enforce: Python can always call the runtime directly. The limitation is disclosed in the report.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

from devagents.config import ROOT

GATE0_DIR = ROOT / "data" / "gate0"
AUDIT_PATH = GATE0_DIR / "audit.jsonl"
ACCEPTANCE_PATH = GATE0_DIR / "acceptance.json"
SPEC_PATH = ROOT / "GATE_0_SPEC.md"
GUARDED = ["devagents", "tests", "data/gate0/acceptance.json", "data/gate0/candidates_round1.json",
           "data/gate0/candidates_round2.json", "GATE_0_SPEC.md", "pyproject.toml"]


def sha256_lf(path: Path) -> str:
    """SHA-256 of a text file with CRLF normalized to LF, so a Windows checkout hashes identically."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


class AuditError(RuntimeError):
    pass


def git_state(root: Path = ROOT) -> dict:
    def run(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False).stdout.strip()
    head = run("rev-parse", "HEAD")
    dirty = [line[3:] for line in run("status", "--porcelain", "--", *GUARDED).splitlines() if line.strip()]
    return {"head": head, "dirty": dirty}


class Audit:
    def __init__(self, path: Path = AUDIT_PATH):
        self.path = Path(path)

    # ------------------------------------------------------------------ reading
    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def verify(self) -> list[str]:
        """Problems with the chain (empty if intact)."""
        problems, prev = [], ""
        for i, e in enumerate(self.entries()):
            body = {k: v for k, v in e.items() if k != "hash"}
            if e.get("seq") != i:
                problems.append(f"entry {i}: seq {e.get('seq')} != {i}")
            if e.get("prev") != prev:
                problems.append(f"entry {i}: prev does not match the previous hash")
            if hashlib.sha256(canonical(body).encode()).hexdigest() != e.get("hash"):
                problems.append(f"entry {i}: hash mismatch (edited entry)")
            prev = e.get("hash", "")
        return problems

    def genesis(self) -> dict | None:
        es = self.entries()
        return es[0] if es and es[0]["kind"] == "genesis" else None

    def rounds(self) -> dict[int, dict]:
        """Per round: candidate-set hash, evaluations, defects and the decision, in log order."""
        out: dict[int, dict] = {}
        for e in self.entries():
            p = e["payload"]
            if e["kind"] == "round_registered":
                out[p["round"]] = {"candidates_sha": p["candidates_sha"], "evaluations": [], "defects": [],
                                   "completed": [], "decision": None}
            elif e["kind"] in ("evaluation_started", "evaluation_completed", "defect", "decision") and p.get("round") in out:
                r = out[p["round"]]
                if e["kind"] == "evaluation_started":
                    r["evaluations"].append(e["seq"])
                elif e["kind"] == "evaluation_completed":
                    r["completed"].append(p)
                elif e["kind"] == "defect":
                    r["defects"].append(e["seq"])
                else:
                    r["decision"] = p["decision"]
        return out

    # ------------------------------------------------------------------ writing
    def append(self, kind: str, payload: dict) -> dict:
        problems = self.verify()
        if problems:
            raise AuditError("audit chain is broken: " + "; ".join(problems))
        es = self.entries()
        entry = {"seq": len(es), "prev": es[-1]["hash"] if es else "", "kind": kind,
                 "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "payload": payload}
        entry["hash"] = hashlib.sha256(canonical(entry).encode()).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical(entry) + "\n")
        return entry

    def write_genesis(self, acceptance_path: Path, spec_path: Path, note: str) -> dict:
        if self.entries():
            raise AuditError("genesis exists already")
        return self.append("genesis", {"acceptance_sha": sha256_lf(acceptance_path), "spec_sha": sha256_lf(spec_path),
                                       "note": note, "git": git_state()})

    # ------------------------------------------------------------------ the round guard
    def begin_evaluation(self, round_no: int, candidates_sha: str, acceptance_path: Path, acceptance: dict,
                         instance_digests: dict, defect_ok: bool = True, require_clean: bool = True) -> dict:
        problems = self.verify()
        if problems:
            raise AuditError("audit chain is broken: " + "; ".join(problems))
        g = self.genesis()
        if g is None:
            raise AuditError("no genesis entry: the acceptance specification was not pinned before evaluation")
        acc_sha = sha256_lf(acceptance_path)
        if acc_sha != g["payload"]["acceptance_sha"]:
            raise AuditError(f"acceptance file changed after genesis ({acc_sha} != {g['payload']['acceptance_sha']})")
        max_rounds = acceptance["rounds"]["max"]
        if not 1 <= round_no <= max_rounds:
            raise AuditError(f"round {round_no} is outside 1..{max_rounds}")
        state = self.rounds()
        git = git_state()
        if require_clean and git["dirty"]:
            raise AuditError("uncommitted changes in guarded paths: " + ", ".join(git["dirty"]))
        if round_no not in state:
            for earlier in range(1, round_no):
                if earlier not in state or state[earlier]["decision"] != "FAIL":
                    raise AuditError(f"round {round_no} needs round {earlier} to end with a FAIL decision")
            if any(r > round_no for r in state):
                raise AuditError("a later round exists")
            self.append("round_registered", {"round": round_no, "candidates_sha": candidates_sha,
                                             "instances": instance_digests, "git": git})
            state = self.rounds()
        r = state[round_no]
        if r["candidates_sha"] != candidates_sha:
            raise AuditError(f"round {round_no} is registered with another candidate set")
        if r["decision"] is not None:
            raise AuditError(f"round {round_no} is closed ({r['decision']})")
        n_eval = len(r["evaluations"])
        if n_eval >= 1:
            if not defect_ok:
                raise AuditError(f"round {round_no} was evaluated already")
            if n_eval > acceptance["rounds"]["max_reevaluations"]:
                raise AuditError(f"round {round_no}: re-evaluation limit reached")
            if not r["defects"] or r["defects"][-1] < r["evaluations"][-1]:
                raise AuditError(f"round {round_no}: a re-evaluation needs a logged defect after the last evaluation")
        return self.append("evaluation_started", {"round": round_no, "candidates_sha": candidates_sha,
                                                  "acceptance_sha": acc_sha, "instances": instance_digests,
                                                  "git": git, "evaluation": n_eval + 1})

    def complete_evaluation(self, round_no: int, results_sha: str, summary: dict) -> dict:
        return self.append("evaluation_completed", {"round": round_no, "results_sha": results_sha, **summary})

    def log_defect(self, round_no: int, description: str, fix_commit: str, regression_test: str) -> dict:
        if round_no not in self.rounds():
            raise AuditError(f"round {round_no} is not registered")
        return self.append("defect", {"round": round_no, "description": description, "fix_commit": fix_commit,
                                      "regression_test": regression_test})

    def decide(self, round_no: int, decision: str, rationale: str) -> dict:
        if decision not in ("PASS", "FAIL", "INDETERMINATE"):
            raise AuditError(f"unknown decision {decision!r}")
        r = self.rounds().get(round_no)
        if r is None or not r["completed"]:
            raise AuditError(f"round {round_no} has no completed evaluation")
        if r["decision"] is not None:
            raise AuditError(f"round {round_no} is closed already")
        return self.append("decision", {"round": round_no, "decision": decision, "rationale": rationale})
