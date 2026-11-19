"""Experiment 1 (solve): ask a model each problem k times, grade every reply."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from . import extract
from .grade import grade
from .models import ModelClient
from .prompts import solve_prompt, solve_system
from .schema import Problem


def solve_one(client: ModelClient, p: Problem, sample: int, temperature: float) -> dict:
    reply = client.complete(solve_system(p.subject), solve_prompt(p), temperature=temperature)
    ans = extract.final_answer(reply)
    g = grade(ans, p.answer)
    return {
        "experiment": "solve",
        "model": client.name,
        "problem_id": p.id,
        "topic": p.topic,
        "difficulty": p.difficulty,
        "tags": p.tags,
        "input": "image" if p.images else "text",
        "sample": sample,
        "answer_text": ans,
        "parsed": g.parsed,
        "correct": g.correct,
        "grade_note": g.note,
        "format_ok": extract.has_final_marker(reply),
        "confidence": extract.confidence(reply),
        "reference": (f"{float(p.answer.value):.4g} {p.answer.unit}".strip()
                      if p.answer.type == "numeric" else str(p.answer.value)),
        "reply": reply,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def run_solve(client: ModelClient, problems: list[Problem], out: Path,
              samples: int = 3, temperature: float = 1.0, workers: int = 4) -> list[dict]:
    """Run every problem `samples` times and append results to `out` (JSONL).
    Already-finished (problem, sample) pairs in `out` are skipped, so a run can be resumed."""
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("experiment") == "solve" and r["model"] == client.name:
                done.add((r["problem_id"], r["sample"]))
    jobs = [(p, s) for p in problems for s in range(samples) if (p.id, s) not in done]

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool, out.open("a", encoding="utf-8") as f:
        # Save each result as soon as it arrives, so one slow request holds nothing back.
        futures = [pool.submit(solve_one, client, p, s, temperature) for p, s in jobs]
        for fut in as_completed(futures):
            r = fut.result()
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            results.append(r)
            mark = "ok " if r["correct"] else "BAD"
            print(f"  {mark} {r['problem_id']:<28} sample {r['sample']}  answer={r['answer_text']!r}")
    return results


def regrade(problems: list[Problem], solve_file: Path, verify_file: Path) -> list[tuple]:
    """Re-extract and re-grade stored replies with the current grader (no model
    calls), and keep the verify results that judged them consistent. Returns
    (model, problem_id, sample, was_correct, now_correct) for every change."""
    by_id = {p.id: p for p in problems}
    rows = [json.loads(l) for l in solve_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    changes, correct = [], {}
    for r in rows:
        p = by_id.get(r["problem_id"])
        if p is None or r.get("experiment") != "solve":
            continue
        ans = extract.final_answer(r["reply"])
        g = grade(ans, p.answer)
        if g.correct != r["correct"]:
            changes.append((r["model"], r["problem_id"], r["sample"], r["correct"], g.correct))
        r.update(answer_text=ans, parsed=g.parsed, correct=g.correct, grade_note=g.note,
                 format_ok=extract.has_final_marker(r["reply"]))
        correct[(r["model"], r["problem_id"], r["sample"])] = g.correct
    solve_file.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    if verify_file.exists():
        vrows = [json.loads(l) for l in verify_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        for v in vrows:
            key = (v["solver"], v["problem_id"], v["sample"])
            if key in correct:
                v["solution_correct"] = correct[key]
                v["verifier_right"] = None if v["verdict"] is None else (v["verdict"] == "CORRECT") == correct[key]
        verify_file.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in vrows), encoding="utf-8")
    return changes
