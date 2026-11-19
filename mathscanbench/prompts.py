"""Prompt templates for the solve and verify experiments.

Prompts are plain text when a problem has no images. Otherwise they are a list
of text and image parts (see images.py), with each image placed under the
heading it belongs to.
"""

from __future__ import annotations

from pathlib import Path

from .images import Content, Part
from .schema import Answer, Problem

SOLVE_SYSTEM = (
    "You are solving a problem in {subject}. Reason step by step. "
    "End your reply with exactly two lines:\n"
    "FINAL ANSWER: <answer>\n"
    "CONFIDENCE: <integer 0-100, your probability that the final answer is correct>"
)

IMAGE_NOTE = ("The {what} is given in the attached image{s} (a scan, photo or screenshot, "
              "possibly handwritten). Read it carefully; if any part is illegible or "
              "ambiguous, say what you read it as.")


def answer_format(a: Answer | None) -> str:
    if a is None:
        return "Give the final answer with its unit, if it has one (for example: FINAL ANSWER: 12.5 mm)."
    if a.type == "numeric":
        unit = a.unit or "dimensionless"
        return f"Give the final answer as a number in {unit} (for example: FINAL ANSWER: 12.5 {a.unit})."
    if a.type == "symbolic":
        if a.form:
            return f"Give the final answer as {a.form}, written in Python/SymPy syntax."
        syms = ", ".join(a.symbols)
        return f"Give the final answer as a single expression in {syms}, written in Python/SymPy syntax (for example sqrt(k/m))."
    return "Give the final answer as the letter of one option."


def _join(parts: list[Part]) -> Content:
    """Merge neighbouring text parts; plain text if there are no images."""
    out: list[Part] = []
    for p in parts:
        if isinstance(p, str) and out and isinstance(out[-1], str):
            out[-1] = out[-1] + p
        else:
            out.append(p)
    return out[0] if len(out) == 1 and isinstance(out[0], str) else out


def _with_images(what: str, text: str, images: list[Path]) -> list[Part]:
    """Text of a problem or solution followed by its images."""
    parts: list[Part] = [text.strip() + "\n"] if text.strip() else []
    if images:
        parts.append(IMAGE_NOTE.format(what=what, s="s" if len(images) > 1 else "") + "\n")
        for i, img in enumerate(images, 1):
            if len(images) > 1:
                parts.append(f"[{what} image {i} of {len(images)}]\n")
            parts += [img, "\n"]
    return parts


def problem_parts(statement: str, images: list[Path], answer: Answer | None) -> list[Part]:
    parts = _with_images("problem", statement, images)
    if answer is not None and answer.type == "choice":
        parts.append("\n" + "\n".join(f"{k}) {v}" for k, v in sorted(answer.options.items())) + "\n")
    return parts


def solve_prompt(p: Problem) -> Content:
    return _join([f"[problem {p.id}]\n\n", *problem_parts(p.statement, p.images, p.answer),
                  "\n" + answer_format(p.answer)])


def free_solve_prompt(statement: str, images: list[Path], pid: str = "adhoc") -> Content:
    """Solve prompt for a problem outside the benchmark, with no reference answer."""
    return _join([f"[problem {pid}]\n\n", *problem_parts(statement, images, None),
                  "\n" + answer_format(None)])


VERIFY_SYSTEM = (
    "You are reviewing a solution to a problem in {subject} written by someone else. "
    "Check the reasoning and the final answer independently. "
    "End your reply with exactly two lines:\n"
    "VERDICT: CORRECT or INCORRECT\n"
    "CONFIDENCE: <integer 0-100, your probability that your verdict is right>"
)


def solve_system(subject: str = "solid mechanics") -> str:
    return SOLVE_SYSTEM.format(subject=subject)


def verify_system(subject: str = "solid mechanics") -> str:
    return VERIFY_SYSTEM.format(subject=subject)


def verify_prompt(p: Problem, solution: str, solution_images: list[Path] = ()) -> Content:
    return free_verify_prompt(p.statement, p.images, solution, list(solution_images), p.id, p.answer)


def free_verify_prompt(statement: str, images: list[Path], solution: str,
                       solution_images: list[Path], pid: str = "adhoc",
                       answer: Answer | None = None) -> Content:
    return _join([
        f"[problem {pid}]\n\nPROBLEM:\n", *problem_parts(statement, images, answer),
        "\nPROPOSED SOLUTION:\n", *_with_images("solution", solution, solution_images),
        "\nIs the proposed final answer correct?",
    ])
