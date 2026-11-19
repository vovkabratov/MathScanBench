from mathscanbench.extract import confidence, final_answer, parse_number, verdict


def test_final_answer_takes_last_marker_and_strips_markdown():
    reply = "FINAL ANSWER: 3\nwait, recheck\n**FINAL ANSWER:** $1.67 \\times 10^{-3}$ m\nCONFIDENCE: 85"
    assert final_answer(reply) == "1.67 \\times 10^{-3}$ m"
    assert final_answer("FINAL ANSWER: sqrt(k/(m*(a+b)))") == "sqrt(k/(m*(a+b)))"
    assert final_answer("FINAL ANSWER: \\boxed{2.5} m.") == "\\boxed{2.5} m"
    assert final_answer("FINAL ANSWER: $\\boxed{2.5}$") == "2.5"


def test_confidence_percent_and_fraction():
    assert confidence("CONFIDENCE: 85") == 0.85
    assert confidence("Confidence: 90%") == 0.9
    assert confidence("CONFIDENCE: 0.7") == 0.7
    assert confidence("no marker") is None


def test_verdict():
    assert verdict("...\nVERDICT: INCORRECT\nCONFIDENCE: 80") == "INCORRECT"
    assert verdict("VERDICT: **correct**") == "CORRECT"


def test_parse_number_formats():
    assert parse_number("1.6e-3 m") == (1.6e-3, "m")
    v, u = parse_number("1.6 × 10^-3 m")
    assert abs(v - 1.6e-3) < 1e-15 and u == "m"
    v, u = parse_number("1.6 \\times 10^{-3} m")
    assert abs(v - 1.6e-3) < 1e-15
    assert parse_number("22,500 N*m") == (22500.0, "N*m")
    v, _ = parse_number("σ = 2.4·10⁸ Pa")
    assert abs(v - 2.4e8) < 1
    assert parse_number("no number") is None


def test_parse_number_repeating_decimals():
    for text in ("0.(3)", "0.33..", "0.333...", "0,(3)", "0.3…"):
        v, _ = parse_number(text)
        assert abs(v - 1 / 3) < 1e-12, text
    v, _ = parse_number("0.1(6)")
    assert abs(v - 1 / 6) < 1e-12
    v, _ = parse_number("-2.(27)")
    assert abs(v + 2.272727) < 1e-6


def test_answer_without_marker_or_with_commentary_is_still_scored():
    assert final_answer("Working...\n\n-6*b\nCONFIDENCE: 96") == "-6*b"
    assert final_answer("Long working\nB") == "B"
    assert final_answer("A long paragraph of reasoning that never states a final answer, " * 2) is None
    assert final_answer("FINAL ANSWER: FiniteSet(0) — reading the equation as x+1=sqrt(1-x).") == "FiniteSet(0)"
    assert final_answer("FINAL ANSWER: 12.5 kN; the beam is safe") == "12.5 kN"
    assert final_answer("FINAL ANSWER: -3") == "-3"


def test_regrade_updates_solve_and_verify(tmp_path):
    import json
    from pathlib import Path

    from mathscanbench.run import regrade
    from mathscanbench.schema import load_problems

    problems = load_problems(Path(__file__).parent.parent / "problems")
    p = next(p for p in problems if p.id == "beam-simply-supported-udl")
    solve, verify = tmp_path / "solve.jsonl", tmp_path / "verify.jsonl"
    solve.write_text(json.dumps({"experiment": "solve", "model": "m", "problem_id": p.id, "sample": 0,
                                 "correct": False, "reply": "M = wL^2/8\n22.5 kN*m\nCONFIDENCE: 90"}) + "\n")
    verify.write_text(json.dumps({"verifier": "v", "solver": "m", "problem_id": p.id, "sample": 0,
                                  "solution_correct": False, "verdict": "CORRECT", "verifier_right": False}) + "\n")
    assert regrade(problems, solve, verify) == [("m", p.id, 0, False, True)]
    s, v = json.loads(solve.read_text()), json.loads(verify.read_text())
    assert s["correct"] and s["format_ok"] is False
    assert v["solution_correct"] and v["verifier_right"]
