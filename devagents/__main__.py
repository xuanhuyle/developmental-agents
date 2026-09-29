"""Command line: python -m devagents <command>.

    calibrate        LLM-free oracle calibration and the validity gate (SPEC §7.1-7.2)
    criteria-check   LLM-free power and specificity check of the §8 evaluator (§7.3)
    pilot            single and central on held-out pilot tasks; measures tokens (§7.4 step 1; needs an API key)
    freeze           calibrate from the pilot, repair the gate, pick R, write data/frozen.json (§7.4 step 2)
    run              the frozen main experiment (§4); --smoke runs all modes on the pilot tasks (needs an API key)
    report DIR       recompute everything from the event logs and evaluate §8
    build-world      regenerate data/world/ from the fact tables
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from devagents.config import default_constants, load_frozen, sha256_file, FROZEN_PATH


def _llm_policy(constants, no_structured: bool):
    from devagents.agents.policies import LLMPolicy
    try:
        return LLMPolicy(constants.compute, structured=not no_structured)
    except ImportError:
        sys.exit("The real experiment needs the Anthropic SDK: pip install anthropic (see README).")


def cmd_calibrate(a):
    from devagents.evals.calibrate import Assumptions, calibrate, format_calibration
    cal = calibrate(default_constants(a.compute), Assumptions(a.input_scale, a.reasoning_tokens), with_grid=not a.no_grid)
    print(format_calibration(cal))
    if a.json:
        Path(a.json).write_text(json.dumps(cal, indent=1))
    return 0 if cal["gate"]["passed"] else 1


def cmd_criteria_check(a):
    from devagents.environment.tasks import TASKS
    from devagents.evals.analysis import criteria_check
    from devagents.evals.calibrate import calibrate
    cal = calibrate(default_constants(a.compute))
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
    res = freeze(Path(a.pilot) if a.pilot else None, a.compute, n_sims=a.sims)
    print(json.dumps(res, indent=1))
    if res["ok"]:
        print(f"Commit {res['path']} and record sha256 {res['sha']} in EXPERIMENT_STATUS.md and SPEC.md §11.")
    return 0 if res["ok"] else 1


def cmd_run(a):
    from devagents.environment.tasks import PILOT_TASKS, TASKS, TASKS_BY_ID
    from devagents.evals.experiment import frozen_constants, make_manifest, plan, run_suite, verify_frozen
    from devagents.runtime.runtime import MODES
    if a.exploratory and not FROZEN_PATH.exists():
        frozen, constants, sha = None, default_constants(a.compute), ""
    else:
        frozen, constants, sha = frozen_constants()
        problems = verify_frozen(frozen)
        if problems and not a.exploratory:
            sys.exit("Frozen configuration does not verify (SPEC §7.4):\n  " + "\n  ".join(problems))
        if frozen.get("provisional") and not (a.exploratory or a.smoke):
            sys.exit("data/frozen.json is provisional (made without a pilot). Run `pilot`, then `freeze --pilot DIR` "
                     "(SPEC §7.4), or pass --exploratory.")
    tasks = [TASKS_BY_ID[t] for t in a.tasks.split(",")] if a.tasks else (PILOT_TASKS if a.smoke else TASKS)
    modes = a.modes.split(",") if a.modes else list(MODES)
    repeats = a.repeats or (1 if a.smoke else (frozen or {}).get("R") or 3)
    regimes = ["urgent"] if a.smoke else None
    configs = plan(tasks, constants, modes, repeats, regimes=regimes, frozen_sha=sha)
    exploratory = a.exploratory or a.smoke or bool(a.tasks) or bool(a.modes) or bool(a.repeats and frozen and a.repeats != frozen["R"])
    out = Path(a.out or ("results/smoke" if a.smoke else "results/main"))
    summary = run_suite(configs, _llm_policy(constants, a.no_structured_output), constants, out,
                        make_manifest("smoke" if a.smoke else "main", configs, constants, exploratory, sha), a.workers)
    print(json.dumps(summary))
    print(f"Next: python -m devagents report {out}")
    return 0


def cmd_report(a):
    from devagents.evals.experiment import verify_frozen
    from devagents.evals.report import build_report, format_markdown
    frozen = load_frozen()
    if frozen is None:
        sys.exit("data/frozen.json not found; reports need the frozen labels (run `freeze`).")
    manifest = json.loads((Path(a.results) / "manifest.json").read_text())
    frozen_ok = manifest.get("frozen_sha") == sha256_file(FROZEN_PATH) and not verify_frozen(frozen)
    overrides = {}
    if a.value_of_time:
        overrides["value_of_time"] = {k: float(v) for k, v in (p.split("=") for p in a.value_of_time.split(","))}
    if a.w_coord is not None:
        overrides["w_coord"] = a.w_coord
    rep = build_report(Path(a.results), frozen, frozen_ok, overrides or None, n_boot=a.n_boot)
    md = format_markdown(rep)
    suffix = "-exploratory" if rep["exploratory"] else ""
    (Path(a.results) / f"report{suffix}.md").write_text(md)
    (Path(a.results) / f"summary{suffix}.json").write_text(json.dumps(rep, indent=1, default=str))
    print(md)
    return 0


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
    s.set_defaults(fn=cmd_calibrate)
    s = sub.add_parser("criteria-check")
    s.add_argument("--compute", default="opus")
    s.add_argument("--accuracy", type=float, default=0.9)
    s.add_argument("--cost-cv", type=float, default=0.25)
    s.add_argument("--sims", type=int, default=200)
    s.set_defaults(fn=cmd_criteria_check)
    for name, fn in (("pilot", cmd_pilot), ("run", cmd_run)):
        s = sub.add_parser(name)
        s.add_argument("--out", default="results/pilot" if name == "pilot" else None)
        s.add_argument("--workers", type=int, default=4)
        s.add_argument("--compute", default="opus")
        s.add_argument("--no-structured-output", action="store_true",
                       help="do not send output_config.format (use only if the API rejects the schema)")
        s.set_defaults(fn=fn)
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
    s.add_argument("--compute", default="opus")
    s.add_argument("--sims", type=int, default=200)
    s.set_defaults(fn=cmd_freeze)
    s = sub.add_parser("report")
    s.add_argument("results")
    s.add_argument("--value-of-time", help="exploratory rescoring, e.g. relaxed=0.0001,urgent=0.002")
    s.add_argument("--w-coord", type=float)
    s.add_argument("--n-boot", type=int, default=10_000)
    s.set_defaults(fn=cmd_report)
    s = sub.add_parser("build-world")
    s.set_defaults(fn=cmd_build_world)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
