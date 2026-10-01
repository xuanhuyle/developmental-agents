"""Command line: python -m devagents <command>.

    calibrate        LLM-free oracle calibration and the validity gate (SPEC §7.1-7.2)
    criteria-check   LLM-free power and specificity check of the §8 evaluator (§7.3)
    pilot            single and central on held-out pilot tasks; measures tokens (§7.4 step 1; needs an API key)
    freeze           calibrate from the pilot, repair the gate, pick R, write data/frozen.json (§7.4 step 2)
    run              the frozen main experiment (§4); --smoke runs all modes on the pilot tasks (needs an API key)
    report DIR       recompute everything from the event logs and evaluate §8
    build-world      regenerate data/world/ from the fact tables
    exp0c ACTION     Experiment 0c (SPEC_0C.md): verify (offline Stage 0 checks), pilot (the 4-run X2 instrument
                     pilot), stage1 (the 36-run Stage 1, only after the pilot PASSED), report DIR, and prereg
                     (writes data/exp0c/prereg.json; refuses if it exists)

freeze, run and report take --experiment 0b to use Experiment 0b (SPEC_0B.md): its constants,
data/exp0b/frozen.json and results/exp0b/. Without it they use Experiment 0, as before.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from devagents.config import EXPERIMENTS, ROOT, default_constants, load_frozen, sha256_file


def _llm_policy(constants, no_structured: bool):
    from devagents.agents.policies import LLMPolicy
    try:
        return LLMPolicy(constants.compute, structured=not no_structured)
    except ImportError:
        sys.exit("The real experiment needs the Anthropic SDK: pip install anthropic (see README).")


def _constants_and_assumptions(a):
    """The frozen configuration if there is one (what the experiment uses), else the provisional code defaults."""
    from devagents.config import Constants
    from devagents.evals.calibrate import Assumptions
    frozen = None if a.defaults else load_frozen()
    if frozen:
        print(f"Using the frozen configuration in data/frozen.json (provisional: {frozen.get('provisional')}). "
              "Pass --defaults for the pre-repair code defaults.")
        return Constants.from_json(frozen["constants"]), Assumptions(**frozen["assumptions"])
    return default_constants(a.compute), Assumptions(a.input_scale, a.reasoning_tokens)


def cmd_calibrate(a):
    from devagents.evals.calibrate import calibrate, format_calibration
    constants, assumptions = _constants_and_assumptions(a)
    cal = calibrate(constants, assumptions, with_grid=not a.no_grid)
    print(format_calibration(cal))
    if a.json:
        Path(a.json).write_text(json.dumps(cal, indent=1), encoding="utf-8")
    return 0 if cal["gate"]["passed"] else 1


def cmd_criteria_check(a):
    from devagents.environment.tasks import TASKS
    from devagents.evals.analysis import criteria_check
    from devagents.evals.calibrate import calibrate
    constants, assumptions = _constants_and_assumptions(a)
    cal = calibrate(constants, assumptions)
    acc = {c: a.accuracy for c in ("solo", "parallel", "cross")}
    res = criteria_check(cal["cells"], cal["gate"]["sets"], {t.id: t.max_doc_route for t in TASKS}, accuracy=acc,
                         cost_cv=a.cost_cv, n_sims=a.sims)
    for R, row in res["table"].items():
        print(f"R={R}: " + ", ".join(f"{k} supported {v:.0%}" for k, v in row["supported_rate"].items()) +
              ("  <- chosen" if row["ok"] else ""))
    print(f"Chosen R: {res['R']}")
    return 0 if res["R"] else 1


def cmd_pilot(a):
    from devagents.evals.experiment import make_manifest, pilot_configs, run_suite
    constants = default_constants(a.compute)
    configs = pilot_configs(constants, a.repeats)
    summary = run_suite(configs, _llm_policy(constants, a.no_structured_output), constants, Path(a.out),
                        make_manifest("pilot", configs, constants, exploratory=True, frozen_sha=""), a.workers)
    print(json.dumps(summary))
    print(f"Next: python -m devagents freeze --pilot {a.out}")
    return 0


def cmd_freeze(a):
    from devagents.evals.experiment import freeze
    if a.pilot and a.pilot_stats:
        sys.exit("Pass either --pilot DIR or --pilot-stats FILE, not both.")
    if a.experiment != "0" and not (a.pilot or a.pilot_stats):
        sys.exit(f"Experiment {a.experiment} reuses the Experiment 0 pilot: pass --pilot DIR or --pilot-stats FILE.")
    stats = json.loads(Path(a.pilot_stats).read_text()) if a.pilot_stats else None
    res = freeze(Path(a.pilot) if a.pilot else None, a.compute, out=Path(a.out) if a.out else None, n_sims=a.sims,
                 experiment=a.experiment, stats=stats, stats_source=a.pilot_stats or "")
    print(json.dumps(res, indent=1))
    if res["ok"]:
        where = "EXPERIMENT_STATUS.md and SPEC.md §11" if a.experiment == "0" else "EXPERIMENT_STATUS.md"
        print(f"Commit {res['path']} and record sha256 {res['sha']} in {where}.")
    return 0 if res["ok"] else 1


def cmd_run(a):
    from devagents.environment.tasks import PILOT_TASKS, TASKS, TASKS_BY_ID
    from devagents.evals.experiment import frozen_constants, make_manifest, plan, run_suite, verify_frozen
    from devagents.runtime.runtime import MODES
    exp = EXPERIMENTS[a.experiment]
    if a.exploratory and not exp.frozen.exists():
        frozen, constants, sha = None, exp.constants(a.compute), ""
    else:
        frozen, constants, sha = frozen_constants(a.experiment)
        problems = verify_frozen(frozen)
        if problems and not a.exploratory:
            sys.exit("Frozen configuration does not verify (SPEC §7.4):\n  " + "\n  ".join(problems))
        if frozen.get("provisional") and not (a.exploratory or a.smoke):
            sys.exit(f"{exp.frozen.relative_to(ROOT).as_posix()} is provisional (made without a pilot). "
                     "Run `pilot`, then `freeze --pilot DIR` "
                     "(SPEC §7.4), or pass --exploratory.")
    tasks = [TASKS_BY_ID[t] for t in a.tasks.split(",")] if a.tasks else (PILOT_TASKS if a.smoke else TASKS)
    modes = a.modes.split(",") if a.modes else list(MODES)
    repeats = a.repeats or (1 if a.smoke else (frozen or {}).get("R") or 3)
    regimes = ["urgent"] if a.smoke else None
    configs = plan(tasks, constants, modes, repeats, regimes=regimes, frozen_sha=sha)
    exploratory = a.exploratory or a.smoke or bool(a.tasks) or bool(a.modes) or bool(a.repeats and frozen and a.repeats != frozen["R"])
    default_out = exp.results / ("smoke" if a.smoke else ("exploratory" if exploratory else "main"))
    out = Path(a.out or default_out)
    summary = run_suite(configs, _llm_policy(constants, a.no_structured_output), constants, out,
                        make_manifest("smoke" if a.smoke else "main", configs, constants, exploratory, sha, a.experiment),
                        a.workers)
    print(json.dumps(summary))
    print(f"Next: python -m devagents report {out}" + (f" --experiment {a.experiment}" if a.experiment != "0" else ""))
    return 0


def cmd_report(a):
    from devagents.evals.experiment import verify_frozen
    from devagents.evals.report import build_report, format_markdown
    manifest = json.loads((Path(a.results) / "manifest.json").read_text())
    suite = manifest.get("experiment", "0")
    experiment = a.experiment or suite
    if experiment != suite:
        sys.exit(f"{a.results} is an Experiment {suite} suite; report it with --experiment {suite}.")
    path = EXPERIMENTS[experiment].frozen
    frozen = load_frozen(path)
    if frozen is None:
        sys.exit(f"{path} not found; reports need the frozen labels (run `freeze`).")
    frozen_ok = manifest.get("frozen_sha") == sha256_file(path) and not verify_frozen(frozen)
    overrides = {}
    if a.value_of_time:
        overrides["value_of_time"] = {k: float(v) for k, v in (p.split("=") for p in a.value_of_time.split(","))}
    if a.w_coord is not None:
        overrides["w_coord"] = a.w_coord
    rep = build_report(Path(a.results), frozen, frozen_ok, overrides or None, n_boot=a.n_boot)
    md = format_markdown(rep)
    suffix = "-exploratory" if rep["exploratory"] else ""
    (Path(a.results) / f"report{suffix}.md").write_text(md, encoding="utf-8")
    (Path(a.results) / f"summary{suffix}.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    print(md)
    return 0


def cmd_exp0c(a):
    """Experiment 0c (SPEC_0C.md). `pilot` and `stage1` need an API key; the others are offline."""
    from devagents.evals import exp0c
    if a.action == "verify":
        prereg, sha = exp0c.load_prereg()
        checks = exp0c.stage0_checks(prereg)
        for name, problems in checks.items():
            print(f"{'ok    ' if not problems else 'FAILED'} {name}" + "".join(f"\n         - {p}" for p in problems))
        failed = [n for n, p in checks.items() if p]
        print(f"data/exp0c/prereg.json sha256 {sha}: " + ("all Stage 0 checks pass" if not failed else
                                                         f"{len(failed)} check(s) FAILED: STOP (SPEC_0C.md §5)"))
        return 1 if failed else 0
    if a.action == "prereg":
        if exp0c.PREREG_PATH.exists():
            sys.exit(f"{exp0c.PREREG_PATH} exists; it is the pre-registration and is never rewritten.")
        print(f"wrote {exp0c.PREREG_PATH} sha256 {exp0c.write_prereg()}")
        return 0
    if a.action in ("pilot", "stage1"):
        if a.results:
            sys.exit(f"exp0c {a.action} takes no directory: it always uses results/exp0c/{a.action} (SPEC_0C.md §11).")

        def make_policy(constants):
            policy = _llm_policy(constants, no_structured=False)
            client = getattr(policy, "client", None)
            if not (getattr(client, "api_key", None) or getattr(client, "auth_token", None)):
                sys.exit("No Anthropic API credentials are configured (ANTHROPIC_API_KEY); nothing was run or written.")
            return policy
        res = exp0c.run_stage(a.action, make_policy, workers=a.workers)
        if a.action == "pilot":
            print(f"Commit {exp0c.pilot_record_path().relative_to(ROOT).as_posix()} (the pilot record) before Stage 1.")
    else:
        if not a.results:
            sys.exit("usage: python -m devagents exp0c report results/exp0c/<pilot|stage1>")
        res = exp0c.report_stage(Path(a.results))
    print(res["markdown"])
    return 0 if res["decision"]["verdict"] in ("PASS", "GO", "NO-GO") else 1


def cmd_build_world(a):
    from devagents.environment.world import WORLD_DIR, write_world
    write_world()
    print(f"wrote {WORLD_DIR}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m devagents", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("calibrate")
    s.add_argument("--compute", default="opus")
    s.add_argument("--input-scale", type=float, default=1.0)
    s.add_argument("--reasoning-tokens", type=int, default=150)
    s.add_argument("--no-grid", action="store_true")
    s.add_argument("--json")
    s.add_argument("--defaults", action="store_true", help="ignore data/frozen.json; use the provisional code defaults")
    s.set_defaults(fn=cmd_calibrate)
    s = sub.add_parser("criteria-check")
    s.add_argument("--compute", default="opus")
    s.add_argument("--accuracy", type=float, default=0.9)
    s.add_argument("--cost-cv", type=float, default=0.25)
    s.add_argument("--sims", type=int, default=200)
    s.add_argument("--input-scale", type=float, default=1.0)
    s.add_argument("--reasoning-tokens", type=int, default=150)
    s.add_argument("--defaults", action="store_true", help="ignore data/frozen.json; use the provisional code defaults")
    s.set_defaults(fn=cmd_criteria_check)
    for name, fn in (("pilot", cmd_pilot), ("run", cmd_run)):
        s = sub.add_parser(name)
        s.add_argument("--out", default="results/pilot" if name == "pilot" else None)
        s.add_argument("--workers", type=int, default=4)
        s.add_argument("--compute", default="opus")
        s.add_argument("--no-structured-output", action="store_true",
                       help="do not send output_config.format (use only if the API rejects the schema)")
        s.set_defaults(fn=fn)
        if name == "run":
            s.add_argument("--experiment", choices=sorted(EXPERIMENTS), default="0")
        if name == "pilot":
            s.add_argument("--repeats", type=int, default=2)
        else:
            s.add_argument("--repeats", type=int)
            s.add_argument("--smoke", action="store_true", help="all modes, pilot tasks, urgent, 1 repeat (exploratory)")
            s.add_argument("--exploratory", action="store_true", help="allow running without a verified freeze")
            s.add_argument("--tasks")
            s.add_argument("--modes")
    s = sub.add_parser("freeze")
    s.add_argument("--pilot")
    s.add_argument("--pilot-stats", help="a JSON file of pilot_stats() output, when the pilot logs are elsewhere")
    s.add_argument("--experiment", choices=sorted(EXPERIMENTS), default="0")
    s.add_argument("--out", help="write the frozen file here instead of the experiment's frozen path")
    s.add_argument("--compute", default="opus")
    s.add_argument("--sims", type=int, default=200)
    s.set_defaults(fn=cmd_freeze)
    s = sub.add_parser("report")
    s.add_argument("results")
    s.add_argument("--experiment", choices=sorted(EXPERIMENTS), help="default: the suite's own (from its manifest)")
    s.add_argument("--value-of-time", help="exploratory rescoring, e.g. relaxed=0.0001,urgent=0.002")
    s.add_argument("--w-coord", type=float)
    s.add_argument("--n-boot", type=int, default=10_000)
    s.set_defaults(fn=cmd_report)
    s = sub.add_parser("exp0c", help="Experiment 0c (SPEC_0C.md): verify | prereg | pilot | stage1 | report DIR")
    s.add_argument("action", choices=["verify", "prereg", "pilot", "stage1", "report"])
    s.add_argument("results", nargs="?", help="report only: a results/exp0c/<stage> directory")
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(fn=cmd_exp0c)
    s = sub.add_parser("build-world")
    s.set_defaults(fn=cmd_build_world)
    a = p.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # a cp1252 console or pipe must not crash on report text (U+2212 etc.)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
