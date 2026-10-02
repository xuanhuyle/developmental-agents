"""Append-only, hash-chained Gate-0 calibration audit (GATE_0_SPEC.md §6).

Every line of data/gate0/audit.jsonl is one entry: {"seq", "prev", "kind", "time", "payload", "hash"}, where `hash`
is the SHA-256 of the canonical JSON of the other fields and `prev` is the previous entry's hash.

The chain detects edits, not truncation or deletion, so the official audit is anchored to git and to the pinned remote
branch (both recorded at genesis):
- every write that matters (genesis, the start of an evaluation, a defect, a decision) requires a clean checkout whose
  HEAD is on the remote branch, and the audit file byte-equal to its committed copy at HEAD and on the remote;
- an evaluation runs in two phases: `begin_evaluation` appends `evaluation_started`, then nothing may be simulated
  until that entry is committed and pushed (`confirm_start` checks it, and that nothing but the audit changed since);
- every committed version of the audit must extend the previous one (`history_problems`), and genesis is refused if the
  audit ever had a git history;
- the code that runs is pinned as a whole: after genesis, `git diff <genesis head> HEAD` may touch only the trail and
  the write-ups, plus, for round n > 1, that round's candidate file, worlds.py and the tests, plus the files changed by
  logged defects. Untracked, ignored or hidden (skip-worktree, assume-unchanged) files are refused, except caches.

Round rules:
- round 1 uses the candidate file and world digests pinned at genesis; round n > 1 may be registered only after round
  n - 1 ended with a FAIL decision;
- a completed PASS or FAIL stands. A round is re-evaluated only after an INDETERMINATE completion (a G1 failure or an
  aborted run) and a `defect` entry: the fix is in HEAD, descends from the evaluated code, changes no pinned file, and
  (if it changes code) adds a new regression test; a re-run without a code change is allowed only after an abort.
  Same candidate file and world digests, at most `rounds.max_reevaluations` times;
- `decide` must repeat the last completed evaluation's mechanical decision.

What this cannot enforce: Python can always call the runtime directly, and git can be configured to lie (for example
`url.<x>.insteadOf`). Unanchored audits (tests) skip every git check and record {"unverified": true}.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from devagents.config import ROOT

GATE0_DIR = ROOT / "data" / "gate0"
AUDIT_PATH = GATE0_DIR / "audit.jsonl"
ACCEPTANCE_PATH = GATE0_DIR / "acceptance.json"
SPEC_PATH = ROOT / "GATE_0_SPEC.md"
CANDIDATES_1 = GATE0_DIR / "candidates_round1.json"
REMOTE, BRANCH = "origin", "main"

# May change after genesis without a new round or a defect: the trail and the write-ups.
ALWAYS_ALLOWED = [r"data/gate0/audit\.jsonl", r"data/gate0/round\d+/eval\d+/(results|records)\.json",
                  r"GATE_0_REPORT\.md", r"EXPERIMENT_STATUS\.md"]
# Never changed after genesis, by a defect or a new round: the criteria, the spec, the frozen 0b constants, world and
# execution semantics.
PINNED = [r"data/gate0/acceptance\.json", r"data/gate0/candidates_round1\.json", r"GATE_0_SPEC\.md",
          r"pyproject\.toml", r"data/exp0b/frozen\.json", r"data/world/.*", r"devagents/config\.py",
          r"devagents/runtime/.*", r"devagents/evals/calibrate\.py"]
# Untracked or ignored paths tolerated in the checkout: caches and old ignored result data, nothing importable.
TOLERATED = [r"(.*/)?__pycache__/.*", r"\.pytest_cache/.*", r"results/.*(?<!\.py)(?<!\.pth)", r"data/gate0/audit\.lock"]


def round_allowed(n: int) -> list[str]:
    return [rf"data/gate0/candidates_round{n}\.json", r"devagents/gate0/worlds\.py", r"tests/test_gate0\.py"]


def sha256_lf(path: Path) -> str:
    """SHA-256 of a text file with CRLF normalized to LF, so a Windows checkout hashes identically."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def interpreter() -> dict:
    return {"implementation": platform.python_implementation(), "version": "%d.%d" % sys.version_info[:2]}


class AuditError(RuntimeError):
    pass


def _match(path: str, patterns: list[str]) -> bool:
    return any(re.fullmatch(p, path) for p in patterns)


def _run(args: list[str], root: Path, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, check=False, timeout=timeout)


def _git(*args, root: Path = ROOT, timeout: float = 120) -> str:
    r = _run(list(args), root, timeout)
    if r.returncode != 0:
        raise AuditError(f"git {' '.join(args)} failed ({r.returncode}): {r.stderr.decode(errors='replace')[:200]}")
    return r.stdout.decode("utf-8")


def _show(rev: str, rel: str, root: Path) -> bytes | None:
    r = _run(["show", f"{rev}:{rel}"], root)
    return r.stdout if r.returncode == 0 else None


def is_ancestor(a: str, b: str, root: Path = ROOT) -> bool:
    return _run(["merge-base", "--is-ancestor", a, b], root).returncode == 0


def head(root: Path = ROOT) -> str:
    h = _git("rev-parse", "HEAD", root=root).strip()
    if len(h) != 40:
        raise AuditError(f"unexpected HEAD {h!r}")
    return h


def checkout_problems(root: Path = ROOT) -> list[str]:
    """Modified, staged, untracked, ignored or hidden paths that could change what runs (caches excepted)."""
    out, fields = [], _git("status", "--porcelain=v1", "-z", "--ignored", "--untracked-files=all", root=root).split("\0")
    i = 0
    while i < len(fields):
        rec = fields[i]
        i += 1
        if not rec:
            continue
        code, path = rec[:2], rec[3:]
        if code[0] in "RC":
            i += 1  # the rename source follows
        if code in ("??", "!!") and _match(path, TOLERATED):
            continue
        out.append(f"{code} {path}")
    for line in _git("ls-files", "-v", root=root).splitlines():
        if line[:1].islower() or line[:1] == "S":
            out.append(f"hidden (skip-worktree or assume-unchanged) {line[2:]}")
    return out


def changed_since(base: str, root: Path = ROOT, until: str = "HEAD") -> list[str]:
    return [p for p in _git("diff", "--name-only", "-z", base, until, root=root).split("\0") if p]


def fetch_remote(url: str, branch: str, root: Path = ROOT) -> str:
    """Fetch the pinned branch from the pinned remote and return its commit."""
    got = _git("remote", "get-url", REMOTE, root=root).strip()
    if got != url:
        raise AuditError(f"remote {REMOTE!r} is {got!r}, not the pinned {url!r}")
    for delay in (2, 4, 8, 16, 0):
        r = _run(["fetch", "-q", REMOTE, branch], root, timeout=180)
        if r.returncode == 0:
            return _git("rev-parse", "FETCH_HEAD", root=root).strip()
        if delay:
            time.sleep(delay)
    raise AuditError(f"cannot fetch {url} {branch}: {r.stderr.decode(errors='replace')[:200]}")


def loaded_module_problems(root: Path = ROOT) -> list[str]:
    """Every module loaded from the repository is a tracked file, and no standard-library name is shadowed."""
    tracked = set(_git("ls-files", "-z", root=root).split("\0"))
    out = []
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        try:
            rel = Path(f).resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            continue
        if rel not in tracked:
            out.append(f"module {name} was loaded from an untracked file {rel}")
        if name.split(".")[0] in getattr(sys, "stdlib_module_names", ()):
            out.append(f"standard-library module {name} was loaded from the repository ({rel})")
    return out


class Audit:
    def __init__(self, path: Path = AUDIT_PATH, anchored: bool | None = None, root: Path = ROOT):
        self.path = Path(path)
        self.root = Path(root)
        self.anchored = (self.path.resolve() == AUDIT_PATH.resolve()) if anchored is None else anchored

    @property
    def rel(self) -> str:
        return self.path.resolve().relative_to(self.root.resolve()).as_posix()

    # ------------------------------------------------------------------ reading
    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        text = self.path.read_text(encoding="utf-8")
        if text and not text.endswith("\n"):
            raise AuditError("the audit's last line is incomplete (an interrupted write): restore it from git")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def verify(self) -> list[str]:
        """Problems with the chain or the round state machine (empty if intact)."""
        try:
            es = self.entries()
        except (AuditError, ValueError) as exc:
            return [f"unreadable audit: {exc}"]
        problems, prev = [], ""
        for i, e in enumerate(es):
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

    def history_problems(self) -> list[str]:
        """Every committed version of the audit (HEAD's history) extends the previous one, and the file extends HEAD's."""
        out, prev = [], b""
        for c in _git("log", "--reverse", "--format=%H", "--", self.rel, root=self.root).split():
            cur = _show(c, self.rel, self.root)
            if cur is None:
                out.append(f"commit {c[:12]} deletes the audit")
                continue
            if not cur.startswith(prev):
                out.append(f"commit {c[:12]} rewrites or truncates earlier audit entries")
            prev = cur
        local = self.path.read_bytes() if self.path.exists() else b""
        if not local.startswith(prev):
            out.append("the audit file does not extend its committed version")
        return out

    def genesis(self) -> dict | None:
        es = self.entries()
        return es[0] if es and es[0]["kind"] == "genesis" else None

    def rounds(self) -> dict[int, dict]:
        """Per round: candidate-set hash, world digests, evaluations, progress, defects, completions and the decision."""
        out: dict[int, dict] = {}
        for e in self.entries():
            p, k = e["payload"], e["kind"]
            if k == "round_registered":
                if p["round"] in out:
                    raise AuditError(f"round {p['round']} is registered twice")
                out[p["round"]] = {"candidates_sha": p["candidates_sha"], "instances": p["instances"],
                                   "evaluations": [], "progress": [], "defects": [], "completed": [],
                                   "decision": None}
            elif k in ("evaluation_started", "evaluation_progress", "evaluation_completed", "defect", "decision"):
                r = out.get(p.get("round"))
                if r is None:
                    raise AuditError(f"entry {e['seq']} refers to an unregistered round")
                if r["decision"] is not None:
                    raise AuditError(f"entry {e['seq']} follows the decision of round {p['round']}")
                pending = len(r["evaluations"]) > len(r["completed"])
                if k == "evaluation_started":
                    if pending:
                        raise AuditError(f"entry {e['seq']} starts an evaluation while another is pending")
                    r["evaluations"].append(e["seq"])
                elif k in ("evaluation_progress", "evaluation_completed"):
                    if not pending or p.get("evaluation") != len(r["evaluations"]):
                        raise AuditError(f"entry {e['seq']} does not belong to the pending evaluation")
                    (r["progress"] if k == "evaluation_progress" else r["completed"]).append(p)
                elif k == "defect":
                    if pending:
                        raise AuditError(f"entry {e['seq']} logs a defect while an evaluation is pending")
                    r["defects"].append(e["seq"])
                else:
                    if pending:
                        raise AuditError(f"entry {e['seq']} decides while an evaluation is pending")
                    r["decision"] = p["decision"]
            elif k != "genesis":
                raise AuditError(f"entry {e['seq']} has an unknown kind {k!r}")
        return out

    def pending_start(self, round_no: int) -> dict | None:
        """The round's `evaluation_started` entry that has no completion yet, if any."""
        r = self.rounds().get(round_no)
        if r is None or len(r["evaluations"]) == len(r["completed"]):
            return None
        return self.entries()[r["evaluations"][-1]]

    def defect_files(self) -> list[str]:
        return [re.escape(f) for e in self.entries() if e["kind"] == "defect" for f in e["payload"].get("changed", [])]

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

    def _anchor(self, what: str, url: str, branch: str) -> str:
        """A clean checkout at a commit of the pinned remote branch, with the audit byte-equal to its committed copy
        there and on the remote, and an append-only history. Returns HEAD."""
        local = self.path.read_bytes() if self.path.exists() else b""
        if (_show("HEAD", self.rel, self.root) or b"") != local:
            raise AuditError(f"{what}: the audit file differs from its committed copy (commit and push it first)")
        problems = checkout_problems(self.root)
        if problems:
            raise AuditError(f"{what}: the checkout is not clean: " + ", ".join(problems[:10]))
        h = head(self.root)
        remote = fetch_remote(url, branch, self.root)
        if not is_ancestor(h, remote, self.root):
            raise AuditError(f"{what}: HEAD {h[:12]} is not on {url} {branch} (push first)")
        if (_show(remote, self.rel, self.root) or b"") != local:
            raise AuditError(f"{what}: the audit file differs from the remote's copy (pull or push first)")
        problems = self.history_problems()
        if problems:
            raise AuditError(f"{what}: " + "; ".join(problems))
        return h

    def _code_check(self, what: str, gp: dict, allowed: list[str]) -> None:
        bad = [p for p in changed_since(gp["git"]["head"], self.root) if not _match(p, allowed)]
        if bad:
            raise AuditError(f"{what}: files changed since genesis beyond what this round may change: "
                             + ", ".join(bad[:10]))

    def write_genesis(self, acceptance_path: Path, spec_path: Path, candidates_path: Path, note: str,
                      instances: dict | None = None) -> dict:
        with self._locked():
            if self.entries():
                raise AuditError("genesis exists already")
            payload = {"acceptance_sha": sha256_lf(acceptance_path), "spec_sha": sha256_lf(spec_path),
                       "candidates_round1_sha": sha256_lf(candidates_path), "instances_round1": instances or {},
                       "interpreter": interpreter(), "note": note}
            if self.anchored:
                if not instances:
                    raise AuditError("genesis must pin the round-1 world digests")
                url = _git("remote", "get-url", REMOTE, root=self.root).strip()
                h = self._anchor("genesis", url, BRANCH)
                if _git("log", "--all", "--format=%H", "--", self.rel, root=self.root).strip():
                    raise AuditError("the audit has a git history: genesis is written once, ever")
                payload["git"] = {"head": h, "remote": url, "branch": BRANCH}
            else:
                payload["git"] = {"unverified": True}
            return self._append("genesis", payload)

    def _genesis_checked(self, acceptance_path: Path, spec_path: Path | None) -> dict:
        problems = self.verify()
        if problems:
            raise AuditError("audit chain is broken: " + "; ".join(problems))
        g = self.genesis()
        if g is None:
            raise AuditError("no genesis entry: the acceptance specification was not pinned before evaluation")
        gp = g["payload"]
        if sha256_lf(acceptance_path) != gp["acceptance_sha"]:
            raise AuditError("acceptance file changed after genesis")
        if spec_path is not None and sha256_lf(spec_path) != gp["spec_sha"]:
            raise AuditError("GATE_0_SPEC.md changed after genesis")
        if self.anchored and interpreter() != gp["interpreter"]:
            raise AuditError(f"interpreter {interpreter()} differs from genesis {gp['interpreter']}")
        return gp

    def begin_evaluation(self, round_no: int, candidates_sha: str, acceptance_path: Path, acceptance: dict,
                         instance_digests: dict, spec_path: Path | None = SPEC_PATH) -> dict:
        """Phase 1: check the round rules and append `evaluation_started`. Nothing is simulated here."""
        with self._locked():
            gp = self._genesis_checked(acceptance_path, spec_path)
            max_rounds = acceptance["rounds"]["max"]
            if not 1 <= round_no <= max_rounds:
                raise AuditError(f"round {round_no} is outside 1..{max_rounds}")
            git = {"unverified": True}
            if self.anchored:
                git = {"head": self._anchor(f"round {round_no}", gp["git"]["remote"], gp["git"]["branch"])}
                self._code_check(f"round {round_no}", gp, ALWAYS_ALLOWED + self.defect_files()
                                 + [p for n in range(2, round_no + 1) for p in round_allowed(n)])
            state = self.rounds()
            if round_no not in state:
                for earlier in range(1, round_no):
                    if earlier not in state or state[earlier]["decision"] != "FAIL":
                        raise AuditError(f"round {round_no} needs round {earlier} to end with a FAIL decision")
                if any(r > round_no for r in state):
                    raise AuditError("a later round exists")
                if round_no == 1:
                    if candidates_sha != gp["candidates_round1_sha"]:
                        raise AuditError("round 1 must use the candidate file pinned at genesis")
                    if gp["instances_round1"] and instance_digests != gp["instances_round1"]:
                        raise AuditError("round 1's worlds differ from the digests pinned at genesis")
                self._append("round_registered", {"round": round_no, "candidates_sha": candidates_sha,
                                                  "instances": instance_digests, "git": git})
                state = self.rounds()
            r = state[round_no]
            if r["candidates_sha"] != candidates_sha:
                raise AuditError(f"round {round_no} is registered with another candidate set")
            if r["decision"] is not None:
                raise AuditError(f"round {round_no} is closed ({r['decision']})")
            n_eval = len(r["evaluations"])
            if n_eval > len(r["completed"]):
                raise AuditError(f"round {round_no}: evaluation {n_eval} is pending; run it (calibrate) first")
            if n_eval >= 1:
                if r["completed"][-1]["decision"] != "INDETERMINATE":
                    raise AuditError(f"round {round_no}: a completed {r['completed'][-1]['decision']} stands; a "
                                     "defect found now goes to the next round")
                if n_eval > acceptance["rounds"]["max_reevaluations"]:
                    raise AuditError(f"round {round_no}: re-evaluation limit reached")
                if not r["defects"] or r["defects"][-1] < r["evaluations"][-1]:
                    raise AuditError(f"round {round_no}: a re-evaluation needs a defect entry after the last "
                                     "evaluation")
                if instance_digests != r["instances"]:
                    raise AuditError(f"round {round_no}: a re-evaluation must use the registered worlds; a change to "
                                     "the worlds is a new round")
            return self._append("evaluation_started", {
                "round": round_no, "evaluation": n_eval + 1, "candidates_sha": candidates_sha,
                "acceptance_sha": gp["acceptance_sha"], "instances": instance_digests, "git": git,
                "interpreter": interpreter()})

    def confirm_start(self, round_no: int, candidates_sha: str, instance_digests: dict, out_dir: Path,
                      acceptance_path: Path = ACCEPTANCE_PATH, spec_path: Path | None = SPEC_PATH) -> dict:
        """Phase 2: the pending start is the audit's last entry (bar its own progress entries), committed and pushed,
        and nothing but the audit changed since it was written. Returns the start entry."""
        with self._locked():
            gp = self._genesis_checked(acceptance_path, spec_path)
            start = self.pending_start(round_no)
            if start is None:
                raise AuditError(f"round {round_no} has no pending evaluation")
            sp = start["payload"]
            if any(e["kind"] != "evaluation_progress" for e in self.entries()[start["seq"] + 1:]):
                raise AuditError("other entries follow the pending start")
            if sp["candidates_sha"] != candidates_sha or sp["instances"] != instance_digests:
                raise AuditError("the candidate file or the worlds differ from the pending start")
            if Path(out_dir).exists():
                raise AuditError(f"{out_dir} exists already")
            if self.anchored:
                self._anchor(f"round {round_no} evaluation {sp['evaluation']}", gp["git"]["remote"],
                             gp["git"]["branch"])
                bad = [p for p in changed_since(sp["git"]["head"], self.root) if p != self.rel]
                if bad:
                    raise AuditError("files other than the audit changed since the evaluation was started: "
                                     + ", ".join(bad[:10]))
                if interpreter() != sp["interpreter"]:
                    raise AuditError("the interpreter differs from the one recorded at the start")
                problems = loaded_module_problems(self.root)
                if problems:
                    raise AuditError("; ".join(problems[:10]))
            return start

    def progress(self, round_no: int, evaluation: int, payload: dict) -> dict:
        return self.append("evaluation_progress", {"round": round_no, "evaluation": evaluation, **payload})

    def complete_evaluation(self, round_no: int, results_sha: str, summary: dict) -> dict:
        return self.append("evaluation_completed", {"round": round_no, "results_sha": results_sha, **summary})

    def log_defect(self, round_no: int, description: str, fix_commit: str, regression_test: str) -> dict:
        with self._locked():
            problems = self.verify()
            if problems:
                raise AuditError("audit chain is broken: " + "; ".join(problems))
            r = self.rounds().get(round_no)
            if r is None:
                raise AuditError(f"round {round_no} is not registered")
            if r["decision"] is not None:
                raise AuditError(f"round {round_no} is closed")
            if not r["completed"] or len(r["completed"]) != len(r["evaluations"]):
                raise AuditError(f"round {round_no} has no completed evaluation, or one is pending")
            last = r["completed"][-1]
            if last["decision"] != "INDETERMINATE":
                raise AuditError(f"a completed {last['decision']} stands; a defect found now goes to the next round")
            payload = {"round": round_no, "description": description, "regression_test": regression_test,
                       "after_evaluation": len(r["evaluations"])}
            if not self.anchored:
                payload.update(fix_commit=fix_commit, changed=[], git={"unverified": True})
                return self._append("defect", payload)
            gp = self.genesis()["payload"]
            h = self._anchor("defect", gp["git"]["remote"], gp["git"]["branch"])
            fix = _git("rev-parse", "--verify", f"{fix_commit}^{{commit}}", root=self.root).strip()
            started = self.entries()[r["evaluations"][-1]]["payload"]["git"]["head"]
            if not is_ancestor(started, fix, self.root) or not is_ancestor(fix, h, self.root):
                raise AuditError("the fix commit must descend from the evaluated code and be in HEAD")
            later = [p for p in changed_since(fix, self.root) if not _match(p, ALWAYS_ALLOWED)]
            if later:
                raise AuditError("HEAD carries changes after the fix commit: " + ", ".join(later[:10]))
            changed = [p for p in changed_since(started, self.root, fix) if not _match(p, ALWAYS_ALLOWED)]
            pinned = [p for p in changed if _match(p, PINNED)]
            if pinned:
                raise AuditError("a defect cannot change pinned files: " + ", ".join(pinned))
            if changed:
                test_file, _, name = regression_test.partition("::")
                if not re.fullmatch(r"test_\w+", name):
                    raise AuditError("the regression test must be named exactly, as tests/<file>.py::test_<name>")
                pattern = re.compile(rf"^def {name}\(", re.M)
                now = _show(fix, test_file, self.root)
                before = _show(started, test_file, self.root) or b""
                if now is None or not pattern.search(now.decode("utf-8")):
                    raise AuditError(f"regression test {regression_test} does not exist at the fix commit")
                if pattern.search(before.decode("utf-8")):
                    raise AuditError(f"regression test {regression_test} existed at the evaluated commit")
            elif not last.get("aborted"):
                raise AuditError("a re-run without a code change is allowed only after an aborted evaluation")
            payload.update(fix_commit=fix, changed=changed, git={"head": h})
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
            git = {"unverified": True}
            if self.anchored:
                gp = self.genesis()["payload"]
                git = {"head": self._anchor("decide", gp["git"]["remote"], gp["git"]["branch"])}
            return self._append("decision", {"round": round_no, "decision": decision, "rationale": rationale,
                                             "git": git})
