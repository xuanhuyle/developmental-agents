"""Append-only, hash-chained Gate-0 calibration audit (GATE_0_SPEC.md §6).

Every line of data/gate0/audit.jsonl is one entry: {"seq", "prev", "kind", "time", "payload", "hash"}, where `hash`
is the SHA-256 of the canonical JSON of the other fields and `prev` is the previous entry's hash.

The chain detects edits, not truncation or deletion. That is why the official audit is anchored to git: genesis needs
a clean, pushed tree, and every evaluation needs the audit file exactly as committed and pushed at HEAD. Genesis pins:
- the hashes of acceptance.json, GATE_0_SPEC.md and candidates_round1.json;
- the git tree hashes of every guarded path (the code that defines the classes and criteria, the tests, the specs,
  the frozen 0b constants and the 0b world).

Round rules (`begin_evaluation`):
- the acceptance and spec hashes must equal genesis; the guarded trees must equal genesis, or the trees of the latest
  verified `defect` entry for the round being re-evaluated, or (for a new round > 1) the trees recorded when that
  round is registered;
- round 1 must use the candidate file pinned at genesis; round n > 1 may be registered only after round n - 1 ended
  with a FAIL decision;
- a round is evaluated once, and re-evaluated only after a verified `defect` entry (an existing commit that descends
  from the previous evaluation and is in HEAD, plus a regression test that exists), on the same candidate file and the
  same world digests, at most `rounds.max_reevaluations` times;
- `decide` must repeat the last completed evaluation's mechanical decision.

What this cannot enforce: Python can always call the runtime directly. The limitation is disclosed in the report.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from devagents.config import ROOT

GATE0_DIR = ROOT / "data" / "gate0"
AUDIT_PATH = GATE0_DIR / "audit.jsonl"
ACCEPTANCE_PATH = GATE0_DIR / "acceptance.json"
SPEC_PATH = ROOT / "GATE_0_SPEC.md"
CANDIDATES_1 = GATE0_DIR / "candidates_round1.json"
GUARDED = ["devagents", "tests", "data/world", "data/exp0b/frozen.json", "data/gate0/acceptance.json",
           "data/gate0/candidates_round1.json", "GATE_0_SPEC.md", "pyproject.toml"]


def sha256_lf(path: Path) -> str:
    """SHA-256 of a text file with CRLF normalized to LF, so a Windows checkout hashes identically."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


class AuditError(RuntimeError):
    pass


def _git(*args, root: Path = ROOT, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if check and r.returncode != 0:
        raise AuditError(f"git {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def git_state(root: Path = ROOT) -> dict:
    """HEAD, dirty guarded paths (fails closed outside a git checkout), and whether HEAD is on a remote branch."""
    head = _git("rev-parse", "HEAD", root=root)
    if len(head) != 40:
        raise AuditError(f"unexpected HEAD {head!r}")
    paths = [p for p in GUARDED + ["data/gate0/candidates_round2.json"] if (root / p).exists()]
    dirty = [line[3:] for line in _git("status", "--porcelain", "--untracked-files=all", "--", *paths,
                                       root=root).splitlines() if line.strip()]
    pushed = bool(_git("branch", "-r", "--contains", head, root=root, check=False))
    return {"head": head, "dirty": dirty, "pushed": pushed}


def guarded_trees(root: Path = ROOT) -> dict:
    return {p: _git("rev-parse", f"HEAD:{p}", root=root) for p in GUARDED if (root / p).exists()}


class Audit:
    def __init__(self, path: Path = AUDIT_PATH, anchored: bool | None = None):
        self.path = Path(path)
        self.anchored = (self.path.resolve() == AUDIT_PATH.resolve()) if anchored is None else anchored

    # ------------------------------------------------------------------ reading
    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def verify(self) -> list[str]:
        """Problems with the chain or the round state machine (empty if intact)."""
        problems, prev = [], ""
        for i, e in enumerate(self.entries()):
            body = {k: v for k, v in e.items() if k != "hash"}
            if e.get("seq") != i:
                problems.append(f"entry {i}: seq {e.get('seq')} != {i}")
            if e.get("prev") != prev:
                problems.append(f"entry {i}: prev does not match the previous hash")
            if hashlib.sha256(canonical(body).encode()).hexdigest() != e.get("hash"):
                problems.append(f"entry {i}: hash mismatch (edited entry)")
            if i == 0 and e.get("kind") != "genesis":
                problems.append("the first entry is not genesis")
            prev = e.get("hash", "")
        try:
            self.rounds()
        except AuditError as exc:
            problems.append(str(exc))
        return problems

    def genesis(self) -> dict | None:
        es = self.entries()
        return es[0] if es and es[0]["kind"] == "genesis" else None

    def rounds(self) -> dict[int, dict]:
        """Per round: candidate-set hash, world digests, trees, evaluations, defects, completions and the decision."""
        out: dict[int, dict] = {}
        for e in self.entries():
            p, k = e["payload"], e["kind"]
            if k == "round_registered":
                if p["round"] in out:
                    raise AuditError(f"round {p['round']} is registered twice")
                out[p["round"]] = {"candidates_sha": p["candidates_sha"], "instances": p["instances"],
                                   "trees": p.get("trees"), "evaluations": [], "defects": [], "completed": [],
                                   "decision": None}
            elif k in ("evaluation_started", "evaluation_completed", "defect", "decision"):
                r = out.get(p.get("round"))
                if r is None:
                    raise AuditError(f"entry {e['seq']} refers to an unregistered round")
                if r["decision"] is not None:
                    raise AuditError(f"entry {e['seq']} follows the decision of round {p['round']}")
                {"evaluation_started": r["evaluations"], "evaluation_completed": r["completed"],
                 "defect": r["defects"]}.get(k, []).append(e["seq"] if k != "evaluation_completed" else p)
                if k == "decision":
                    r["decision"] = p["decision"]
            elif k not in ("genesis", "note"):
                raise AuditError(f"entry {e['seq']} has an unknown kind {k!r}")
        return out

    # ------------------------------------------------------------------ writing
    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path.with_suffix(".lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _append(self, kind: str, payload: dict) -> dict:
        problems = self.verify()
        if problems:
            raise AuditError("audit chain is broken: " + "; ".join(problems))
        es = self.entries()
        entry = {"seq": len(es), "prev": es[-1]["hash"] if es else "", "kind": kind,
                 "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "payload": payload}
        entry["hash"] = hashlib.sha256(canonical(entry).encode()).hexdigest()
        with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical(entry) + "\n")
            fh.flush()
        return entry

    def append(self, kind: str, payload: dict) -> dict:
        with self._locked():
            return self._append(kind, payload)

    def _require_anchored(self, git: dict, what: str) -> None:
        if git["dirty"]:
            raise AuditError(f"{what}: uncommitted changes in guarded paths: " + ", ".join(git["dirty"][:10]))
        if not git["pushed"]:
            raise AuditError(f"{what}: HEAD is not on a remote branch (push first)")
        if self.path.exists():
            committed = _git("show", f"HEAD:{self.path.relative_to(ROOT).as_posix()}", check=False)
            if committed.strip() != self.path.read_text(encoding="utf-8").strip():
                raise AuditError(f"{what}: the audit file differs from the committed one (commit and push it first)")

    def write_genesis(self, acceptance_path: Path, spec_path: Path, candidates_path: Path, note: str) -> dict:
        with self._locked():
            if self.entries():
                raise AuditError("genesis exists already")
            git = git_state() if self.anchored else {"head": "", "dirty": [], "pushed": True}
            if self.anchored:
                self._require_anchored(git, "genesis")
            return self._append("genesis", {
                "acceptance_sha": sha256_lf(acceptance_path), "spec_sha": sha256_lf(spec_path),
                "candidates_round1_sha": sha256_lf(candidates_path), "note": note, "git": git,
                "trees": guarded_trees() if self.anchored else {}})

    def begin_evaluation(self, round_no: int, candidates_sha: str, acceptance_path: Path, acceptance: dict,
                         instance_digests: dict, spec_path: Path | None = SPEC_PATH,
                         require_clean: bool = True) -> dict:
        with self._locked():
            problems = self.verify()
            if problems:
                raise AuditError("audit chain is broken: " + "; ".join(problems))
            g = self.genesis()
            if g is None:
                raise AuditError("no genesis entry: the acceptance specification was not pinned before evaluation")
            gp = g["payload"]
            acc_sha = sha256_lf(acceptance_path)
            if acc_sha != gp["acceptance_sha"]:
                raise AuditError(f"acceptance file changed after genesis ({acc_sha} != {gp['acceptance_sha']})")
            if spec_path is not None and sha256_lf(spec_path) != gp["spec_sha"]:
                raise AuditError("GATE_0_SPEC.md changed after genesis")
            max_rounds = acceptance["rounds"]["max"]
            if not 1 <= round_no <= max_rounds:
                raise AuditError(f"round {round_no} is outside 1..{max_rounds}")
            state = self.rounds()
            git = git_state() if require_clean else {"head": "", "dirty": [], "pushed": True}
            trees = guarded_trees() if require_clean else {}
            if require_clean:
                self._require_anchored(git, f"round {round_no}")
            if round_no not in state:
                for earlier in range(1, round_no):
                    if earlier not in state or state[earlier]["decision"] != "FAIL":
                        raise AuditError(f"round {round_no} needs round {earlier} to end with a FAIL decision")
                if any(r > round_no for r in state):
                    raise AuditError("a later round exists")
                if round_no == 1:
                    if candidates_sha != gp["candidates_round1_sha"]:
                        raise AuditError("round 1 must use the candidate file pinned at genesis")
                    if require_clean and trees != gp["trees"]:
                        raise AuditError("the guarded code differs from genesis; changes need a later round or a "
                                         "verified defect")
                self._append("round_registered", {"round": round_no, "candidates_sha": candidates_sha,
                                                  "instances": instance_digests, "git": git, "trees": trees})
                state = self.rounds()
            r = state[round_no]
            if r["candidates_sha"] != candidates_sha:
                raise AuditError(f"round {round_no} is registered with another candidate set")
            if r["decision"] is not None:
                raise AuditError(f"round {round_no} is closed ({r['decision']})")
            n_eval = len(r["evaluations"])
            if n_eval >= 1:
                if n_eval > acceptance["rounds"]["max_reevaluations"]:
                    raise AuditError(f"round {round_no}: re-evaluation limit reached")
                if not r["defects"] or r["defects"][-1] < r["evaluations"][-1]:
                    raise AuditError(f"round {round_no}: a re-evaluation needs a verified defect after the last "
                                     "evaluation")
                if instance_digests != r["instances"]:
                    raise AuditError(f"round {round_no}: a re-evaluation must use the registered worlds; a change to "
                                     "the worlds is a new round")
                if require_clean:
                    last_defect = next(e for e in self.entries() if e["seq"] == r["defects"][-1])
                    if trees != last_defect["payload"]["trees"]:
                        raise AuditError(f"round {round_no}: the code differs from the defect fix's pinned trees")
            elif round_no > 1 and require_clean and trees != r["trees"]:
                raise AuditError(f"round {round_no}: the code differs from the trees recorded at registration")
            return self._append("evaluation_started", {"round": round_no, "candidates_sha": candidates_sha,
                                                       "acceptance_sha": acc_sha, "instances": instance_digests,
                                                       "git": git, "evaluation": n_eval + 1})

    def complete_evaluation(self, round_no: int, results_sha: str, summary: dict) -> dict:
        return self.append("evaluation_completed", {"round": round_no, "results_sha": results_sha, **summary})

    def log_defect(self, round_no: int, description: str, fix_commit: str, regression_test: str,
                   verify_git: bool = True) -> dict:
        with self._locked():
            state = self.rounds()
            if round_no not in state:
                raise AuditError(f"round {round_no} is not registered")
            payload = {"round": round_no, "description": description, "regression_test": regression_test}
            if verify_git:
                git = git_state()
                self._require_anchored(git, "defect")
                full = _git("rev-parse", "--verify", f"{fix_commit}^{{commit}}")
                if subprocess.run(["git", "merge-base", "--is-ancestor", full, "HEAD"], cwd=ROOT).returncode != 0:
                    raise AuditError("the fix commit is not in HEAD")
                last = next(e for e in reversed(self.entries()) if e["kind"] == "evaluation_started"
                            and e["payload"]["round"] == round_no)
                if subprocess.run(["git", "merge-base", "--is-ancestor", last["payload"]["git"]["head"], full],
                                  cwd=ROOT).returncode != 0:
                    raise AuditError("the fix commit does not descend from the evaluated code")
                test_file = regression_test.split("::")[0]
                if not (ROOT / test_file).exists() or regression_test.split("::")[-1] not in (ROOT / test_file).read_text():
                    raise AuditError(f"regression test {regression_test} does not exist")
                payload.update(fix_commit=full, git=git, trees=guarded_trees())
            else:
                payload.update(fix_commit=fix_commit, trees={})
            return self._append("defect", payload)

    def decide(self, round_no: int, decision: str, rationale: str) -> dict:
        with self._locked():
            problems = self.verify()
            if problems:
                raise AuditError("audit chain is broken: " + "; ".join(problems))
            if decision not in ("PASS", "FAIL", "INDETERMINATE"):
                raise AuditError(f"unknown decision {decision!r}")
            r = self.rounds().get(round_no)
            if r is None or not r["completed"]:
                raise AuditError(f"round {round_no} has no completed evaluation")
            if r["decision"] is not None:
                raise AuditError(f"round {round_no} is closed already")
            if len(r["completed"]) != len(r["evaluations"]):
                raise AuditError(f"round {round_no}: an evaluation started but did not complete")
            if r["completed"][-1]["decision"] != decision:
                raise AuditError(f"the decision must repeat the last evaluation's ({r['completed'][-1]['decision']})")
            return self._append("decision", {"round": round_no, "decision": decision, "rationale": rationale})
