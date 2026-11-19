"""Experiment 2 (verify): can a model tell a correct solution from a wrong one?

Takes solutions produced in the solve experiment (whose correctness is known from
the reference answer) and asks a verifier model to judge each one without seeing
the reference. This is a small scalable-oversight test: the interesting cases are
wrong solutions that the verifier accepts.

Problems can also carry submissions written outside the benchmark (for example
scanned handwritten solutions, marked correct or not by hand). These are judged
the same way, with the submission's author as the solver.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import extract
from .models import ModelClient
from .prompts import verify_prompt, verify_system
from .schema import Problem


def submission_jobs(problems: list[Problem]) -> list[dict]:
    """Stored submissions in the same shape as solve results."""
    return [{"experiment": "solve", "model": s.author, "problem_id": p.id, "topic": p.topic,
             "sample": i, "correct": s.correct, "reply": s.text, "images": s.images}
            for p in problems for i, s in enumerate(p.submissions)]


def run_verify(verifier: ModelClient, problems: list[Problem], solve_results: list[dict],
               out: Path, workers: int = 4) -> list[dict]:
    """Solutions this verifier has already judged in `out` are skipped, so a run
    can be resumed."""
    by_id = {p.id: p for p in problems}
    done = {(r["solver"], r["problem_id"], r["sample"])
            for r in (load_jsonl(out) if out.exists() else []) if r["verifier"] == verifier.name}
    jobs = [r for r in solve_results if r["experiment"] == "solve" and r["problem_id"] in by_id
            and (r["model"], r["problem_id"], r["sample"]) not in done]

    def judge(r: dict) -> dict:
        p = by_id[r["problem_id"]]
        images = r.get("images", [])
        prompt = verify_prompt(p, r["reply"], images)
        reply = verifier.complete(verify_system(p.subject), prompt, temperature=0.0)
        v = extract.verdict(reply)
        return {
            "experiment": "verify",
            "verifier": verifier.name,
            "solver": r["model"],
            "problem_id": r["problem_id"],
            "topic": r["topic"],
            "sample": r["sample"],
            "input": "image" if p.images or images else "text",
            "solution_correct": r["correct"],
            "verdict": v,
            "verifier_right": None if v is None else (v == "CORRECT") == r["correct"],
            "confidence": extract.confidence(reply),
            "reply": reply,
        }

    out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool, out.open("a", encoding="utf-8") as f:
        for fut in as_completed([pool.submit(judge, r) for r in jobs]):
            res = fut.result()
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            f.flush()
            results.append(res)
    return results


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
