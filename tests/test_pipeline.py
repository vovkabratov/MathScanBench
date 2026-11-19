"""End-to-end run with the offline mock model: solve, verify, report."""

import json
from pathlib import Path

from mathscanbench.cli import main
from mathscanbench.schema import load_problems

ROOT = Path(__file__).parent.parent
REPLIES = ROOT / "examples" / "mock_replies.json"
N_PROBLEMS = len(load_problems(ROOT / "problems"))


def test_full_pipeline(tmp_path):
    results = tmp_path / "results"
    model = f"mock:{REPLIES}"
    main(["--results", str(results), "run", str(ROOT / "problems"), "--model", model, "--samples", "1"])
    main(["--results", str(results), "verify", str(ROOT / "problems"), "--verifier", "mock"])
    main(["--results", str(results), "report"])

    solve = [json.loads(l) for l in (results / "solve.jsonl").read_text().splitlines()]
    assert len(solve) == N_PROBLEMS
    # Problems without a stored reply get the mock's fixed wrong answer.
    replied = set(json.loads(REPLIES.read_text()))
    wrong = {r["problem_id"] for r in solve if not r["correct"]} & replied
    # The mock replies contain three deliberate, confident errors.
    assert wrong == {"axial-composite-bar-series", "axial-suddenly-applied-load",
                     "fracture-centre-crack-critical-stress"}

    report = (results / "report.md").read_text()
    assert "Confidently wrong answers" in report
    assert "Verification" in report
    assert (results / "calibration.png").exists()


def test_run_resumes_without_duplicates(tmp_path):
    results = tmp_path / "results"
    args = ["--results", str(results), "run", str(ROOT / "problems"), "--model", f"mock:{REPLIES}", "--samples", "1"]
    main(args)
    main(args)
    assert len((results / "solve.jsonl").read_text().splitlines()) == N_PROBLEMS


def test_verify_resumes_without_duplicates(tmp_path):
    results = tmp_path / "results"
    main(["--results", str(results), "run", str(ROOT / "problems"), "--model", f"mock:{REPLIES}", "--samples", "1"])
    args = ["--results", str(results), "verify", str(ROOT / "problems"), "--verifier", "mock"]
    main(args)
    main(args)
    assert len((results / "verify.jsonl").read_text().splitlines()) == N_PROBLEMS
