"""python -m devagents.gate0 ACTION — Gate 0 (GATE_0_SPEC.md), LLM-free.

A separate entry point, so that devagents/__main__.py (pinned by Experiment 0c's pre-registration) stays unchanged.

    verify                 offline integrity of the audit trail; evaluates nothing
    genesis --note TEXT    pin the acceptance and specification hashes (once, before any evaluation)
    calibrate --round N    the only command that evaluates candidates; logged in data/gate0/audit.jsonl first
    defect --round N --note TEXT --fix-commit SHA --regression-test NAME
    decide --round N --decision PASS|FAIL|INDETERMINATE --note TEXT
"""

from __future__ import annotations

import argparse
import sys

from devagents.gate0.run import cli


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m devagents.gate0", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["verify", "genesis", "calibrate", "defect", "decide"])
    p.add_argument("--round", type=int)
    p.add_argument("--note")
    p.add_argument("--fix-commit")
    p.add_argument("--regression-test")
    p.add_argument("--decision", choices=["PASS", "FAIL", "INDETERMINATE"])
    p.add_argument("--audit", help="an audit file other than data/gate0/audit.jsonl (tests)")
    a = p.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    return cli(a)


if __name__ == "__main__":
    sys.exit(main())
