"""Command-line interface.

    mathscanbench list     problems/
    mathscanbench run      problems/ --model claude-opus-5-5 --samples 3
    mathscanbench verify   problems/ --verifier claude-sonnet-5-5
    mathscanbench report

One-off problems from images (scans, photos, screenshots), outside the benchmark:

    mathscanbench ask    --model claude-opus-5-5 problem.jpg
    mathscanbench check  --model claude-opus-5-5 --problem problem.jpg --solution page1.jpg --solution page2.jpg
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import extract
from .images import check_image
from .models import get_client
from .prompts import free_solve_prompt, free_verify_prompt, solve_system, verify_system
from .report import write_report
from .run import regrade, run_solve
from .schema import load_problems
from .verify import load_jsonl, run_verify, submission_jobs


def _select(problems, args):
    if getattr(args, "topic", None):
        problems = [p for p in problems if p.topic == args.topic]
    if getattr(args, "ids", None):
        wanted = set(args.ids.split(","))
        problems = [p for p in problems if p.id in wanted]
    return problems


def _check_images(ap, paths):
    for p in paths:
        try:
            check_image(p)
        except (ValueError, FileNotFoundError) as e:
            ap.error(str(e))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="mathscanbench", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default="results", help="results folder (default: results)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="list problems")
    s.add_argument("problems")

    s = sub.add_parser("run", help="solve experiment")
    s.add_argument("problems")
    s.add_argument("--model", required=True, action="append", help="repeat for several models")
    s.add_argument("--samples", type=int, default=3)
    s.add_argument("--temperature", type=float, default=1.0)
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--topic")
    s.add_argument("--ids", help="comma-separated problem ids")

    s = sub.add_parser("verify", help="verification experiment on stored solutions")
    s.add_argument("problems")
    s.add_argument("--verifier", required=True)
    s.add_argument("--solver", help="only judge solutions from this model (or submission author)")
    s.add_argument("--workers", type=int, default=4)

    s = sub.add_parser("ask", help="solve a one-off problem given as images and/or text")
    s.add_argument("images", nargs="*", type=Path, help="problem images (png, jpg, gif, webp)")
    s.add_argument("--model", required=True)
    s.add_argument("--text", default="", help="problem text, or extra context for the images")
    s.add_argument("--subject", default="solid mechanics", help="named in the system prompt")
    s.add_argument("--temperature", type=float, default=1.0)

    s = sub.add_parser("check", help="check a one-off solution given as images and/or text")
    s.add_argument("--model", required=True)
    s.add_argument("--problem", action="append", default=[], type=Path, help="problem image (repeatable)")
    s.add_argument("--problem-text", default="")
    s.add_argument("--solution", action="append", default=[], type=Path, help="solution image (repeatable)")
    s.add_argument("--solution-text", default="")
    s.add_argument("--subject", default="solid mechanics", help="named in the system prompt")

    sub.add_parser("report", help="write results/report.md and figures")

    s = sub.add_parser("regrade", help="re-grade stored replies with the current grader (no model calls)")
    s.add_argument("problems", nargs="+", help="problem files or folders the results came from")

    args = ap.parse_args(argv)
    results = Path(args.results)
    solve_file, verify_file = results / "solve.jsonl", results / "verify.jsonl"

    if args.cmd == "list":
        for p in load_problems(args.problems):
            print(f"{p.id:<30} {p.topic:<22} d{p.difficulty}  {p.answer.type}")
    elif args.cmd == "run":
        problems = _select(load_problems(args.problems), args)
        for name in args.model:
            print(f"{name}: {len(problems)} problems x {args.samples} samples")
            run_solve(get_client(name), problems, solve_file, args.samples, args.temperature, args.workers)
    elif args.cmd == "verify":
        problems = load_problems(args.problems)
        solved = load_jsonl(solve_file) if solve_file.exists() else []
        solved = [r for r in solved + submission_jobs(problems) if not args.solver or r["model"] == args.solver]
        res = run_verify(get_client(args.verifier), problems, solved, verify_file, args.workers)
        print(f"judged {len(res)} solutions")
    elif args.cmd == "regrade":
        problems = [p for path in args.problems for p in load_problems(path)]
        changes = regrade(problems, solve_file, verify_file)
        for model, pid, sample, was, now in changes:
            print(f"  {model}  {pid}  sample {sample}: {'right' if was else 'wrong'} -> {'right' if now else 'wrong'}")
        print(f"regraded {solve_file}: {len(changes)} changed")
    elif args.cmd == "ask":
        if not args.images and not args.text.strip():
            ap.error("ask needs problem images or --text")
        _check_images(ap, args.images)
        reply = get_client(args.model).complete(
            solve_system(args.subject), free_solve_prompt(args.text, args.images), temperature=args.temperature)
        print(reply)
        print(f"\n--- answer: {extract.final_answer(reply)}  confidence: {extract.confidence(reply)}")
    elif args.cmd == "check":
        if not args.problem and not args.problem_text.strip():
            ap.error("check needs --problem images or --problem-text")
        if not args.solution and not args.solution_text.strip():
            ap.error("check needs --solution images or --solution-text")
        _check_images(ap, args.problem + args.solution)
        prompt = free_verify_prompt(args.problem_text, args.problem, args.solution_text, args.solution)
        reply = get_client(args.model).complete(verify_system(args.subject), prompt, temperature=0.0)
        print(reply)
        print(f"\n--- verdict: {extract.verdict(reply)}  confidence: {extract.confidence(reply)}")
    elif args.cmd == "report":
        solve = load_jsonl(solve_file) if solve_file.exists() else []
        verify = load_jsonl(verify_file) if verify_file.exists() else []
        print(f"wrote {write_report(solve, verify, results)}")


if __name__ == "__main__":
    main()
