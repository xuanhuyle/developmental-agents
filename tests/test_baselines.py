"""The modes differ only where the design says they may (SPEC §6)."""

from devagents.config import default_constants
from devagents.environment.tasks import REGIMES, TASKS
from devagents.evals.experiment import plan
from devagents.runtime.runtime import MODES, Run, RunConfig
from tests.helpers import info

MODE_RULES_PREFIX = "MODE RULES:"


def prompts_for(task, regime, mode):
    run = Run(RunConfig(task, regime, mode), policy=None, info=info())
    return run.system_prompt_for(True), run.system_prompt_for(False), run


def strip_rules(prompt: str) -> str:
    lines = prompt.splitlines()
    rules = [l for l in lines if l.startswith(MODE_RULES_PREFIX)]
    assert len(rules) == 1, "exactly one MODE RULES line"
    return "\n".join(l for l in lines if not l.startswith(MODE_RULES_PREFIX))


def test_equal_resources_across_modes():
    for task in TASKS:
        for regime in REGIMES.values():
            audits = {m: Run(RunConfig(task, regime, m), None, info()).cfg.resource_audit(info()) for m in MODES}
            assert all(a == audits["single"] for a in audits.values()), (task.id, regime.name)


def test_system_prompts_differ_only_in_the_mode_rules_line():
    task = TASKS[0]
    for regime in REGIMES.values():
        bodies = set()
        fingerprints = set()
        for mode in MODES:
            root, child, run = prompts_for(task, regime, mode)
            bodies.add(strip_rules(root))
            bodies.add(strip_rules(child))
            fingerprints.add(run.prompt_fingerprint())
        assert len(bodies) == 1 and len(fingerprints) == 1


def test_prompts_never_reveal_regime_or_task_class_and_use_neutral_roles():
    for task in TASKS:
        for regime in REGIMES.values():
            for mode in MODES:
                root, child, run = prompts_for(task, regime, mode)
                text = (root + child).lower()
                for word in ("urgent", "relaxed", "parallel-friendly", "solo-friendly", "cross-source", "coordinator",
                             "worker"):
                    assert word not in text, (word, mode)


def test_every_block_runs_every_mode_in_a_seeded_order():
    c = default_constants()
    configs = plan(TASKS, c, list(MODES), repeats=2, seed=0)
    blocks = {}
    for cfg in configs:
        blocks.setdefault((cfg.task.id, cfg.regime.name, cfg.repeat), []).append(cfg.mode)
    assert len(blocks) == len(TASKS) * 2 * 2
    assert all(sorted(m) == sorted(MODES) for m in blocks.values())
    assert len({tuple(m) for m in blocks.values()}) > 1  # the order is shuffled
    assert [c.run_id for c in plan(TASKS, c, list(MODES), repeats=2, seed=0)] == [x.run_id for x in configs]
