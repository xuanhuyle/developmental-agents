"""Infrastructure-only fix (SPEC_0C.md §4): user-facing report files are written as UTF-8. On Windows the default
encoding was cp1252, and `Path.write_text()` failed on the report's U+2212 minus sign. No number changes."""

import json
from pathlib import Path

import pytest

ORIGINAL_WRITE_TEXT = Path.write_text


@pytest.fixture
def windows_default_encoding(monkeypatch):
    """Simulate a cp1252 locale: a write without an explicit encoding uses cp1252, as on Windows."""
    def write_text(self, data, encoding=None, errors=None, newline=None):
        return ORIGINAL_WRITE_TEXT(self, data, encoding=encoding or "cp1252", errors=errors, newline=newline)
    monkeypatch.setattr(Path, "write_text", write_text)


def test_the_simulation_reproduces_the_original_failure(tmp_path, windows_default_encoding):
    with pytest.raises(UnicodeEncodeError):
        (tmp_path / "x.md").write_text("developmental − router")


def test_report_files_are_written_as_utf8(tmp_path, windows_default_encoding):
    from devagents.__main__ import main
    from devagents.agents.policies import LLMPolicy
    from devagents.config import EXPERIMENTS, load_frozen, sha256_file
    from devagents.environment.tasks import TASKS_BY_ID
    from devagents.evals.experiment import make_manifest, plan, run_suite
    from tests.test_llm_pipeline import FakeClient, FakeModel
    frozen_path = EXPERIMENTS["0b"].frozen
    from devagents.config import Constants
    c = Constants.from_json(load_frozen(frozen_path)["constants"])
    configs = plan([TASKS_BY_ID["T01"]], c, ["single", "router", "developmental", "central"], 1, regimes=["urgent"],
                   frozen_sha=sha256_file(frozen_path))
    run_suite(configs, LLMPolicy(c.compute, client=FakeClient(FakeModel())), c, tmp_path,
              make_manifest("test", configs, c, True, sha256_file(frozen_path), experiment="0b"))
    assert main(["report", str(tmp_path), "--n-boot", "50"]) == 0
    md = (tmp_path / "report-exploratory.md").read_bytes().decode("utf-8")
    assert "−" in md  # "developmental − router", the text that crashed on Windows
    json.loads((tmp_path / "summary-exploratory.json").read_bytes().decode("utf-8"))


def test_experiment_0c_reports_are_written_as_utf8(tmp_path, windows_default_encoding):
    from devagents.evals import exp0c as X
    from tests.test_exp0c import ModeAwareModel, factory
    pre = tmp_path / "prereg.json"
    pre.write_bytes(X.PREREG_PATH.read_bytes())
    res = X.run_stage("pilot", factory(ModeAwareModel()), out=tmp_path / "pilot", prereg_path=pre, verify=False,
                      workers=1)
    assert "§" in (tmp_path / "pilot" / "pilot_report.md").read_bytes().decode("utf-8")
    assert res["decision"]["verdict"] == "PASS"
    pre2 = tmp_path / "failing" / "prereg.json"  # a FAIL decision cites "SPEC_0C.md §6-§7"
    pre2.parent.mkdir()
    pre2.write_bytes(X.PREREG_PATH.read_bytes())
    res = X.run_stage("pilot", factory(ModeAwareModel(central_answer="nobody")), out=tmp_path / "failing" / "pilot",
                      prereg_path=pre2, verify=False, workers=1)
    assert res["decision"]["verdict"] == "FAIL"
    assert "§" in (tmp_path / "failing" / "pilot" / "pilot_decision.json").read_bytes().decode("utf-8")


def test_a_cp1252_console_does_not_crash_on_report_text(tmp_path, monkeypatch):
    """Printing U+2212 to a cp1252 stdout (a Windows console or pipe) is replaced, not fatal."""
    import io
    import sys
    from devagents.__main__ import main
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")  # strict, as Windows would be
    monkeypatch.setattr(sys, "stdout", out)
    with pytest.raises(SystemExit):  # any command: main() reconfigures stdout before it runs
        main(["exp0c", "report"])
    print("developmental \u2212 router")
    out.flush()
    assert out.buffer.getvalue().endswith(b"developmental ? router\n")
