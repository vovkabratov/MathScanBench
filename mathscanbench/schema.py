"""Problem format and loading.

Each problem is a YAML file (or a YAML list of problems) with a statement and a
reference answer that can be checked automatically. Three answer types:

- numeric:  a value with a unit and a relative tolerance
- symbolic: a closed-form expression, checked for equivalence with sympy
- choice:   one letter out of a list of options

A problem may also come as images (a scan of handwriting, a photo, a screenshot)
listed under `images`, with paths relative to the YAML file. And it may carry
`submissions`: solutions written outside the benchmark, for example scanned
student work, each marked correct or not, for the verify experiment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .images import check_image

ANSWER_TYPES = {"numeric", "symbolic", "choice"}


@dataclass
class Answer:
    type: str
    value: Any
    unit: str | None = None          # numeric only
    rel_tol: float = 0.01            # numeric only
    symbols: list[str] = field(default_factory=list)  # symbolic only
    options: dict[str, str] = field(default_factory=dict)  # choice only
    form: str = ""                   # symbolic only: how to write it, shown to the model

    def __post_init__(self) -> None:
        if self.type not in ANSWER_TYPES:
            raise ValueError(f"answer type must be one of {sorted(ANSWER_TYPES)}, got {self.type!r}")
        if self.type == "numeric" and self.unit is None:
            raise ValueError("numeric answers need a unit (use '' for dimensionless)")
        if self.type == "choice" and str(self.value) not in self.options:
            raise ValueError(f"choice answer {self.value!r} is not among the options")


@dataclass
class Submission:
    """A solution written outside the benchmark, as text, images or both."""

    correct: bool                    # known from grading it by hand
    text: str = ""
    images: list[Path] = field(default_factory=list)
    author: str = "submitted"        # reported as the solver in verify results

    def __post_init__(self) -> None:
        if not self.text.strip() and not self.images:
            raise ValueError("a submission needs text or images")


@dataclass
class Problem:
    id: str
    topic: str
    difficulty: int                  # 1 (textbook) to 5 (research-level)
    statement: str
    answer: Answer
    solution: str = ""               # reference reasoning, never shown to the model
    tags: list[str] = field(default_factory=list)
    source: str = "original"
    subject: str = "solid mechanics"                      # named in the system prompt
    images: list[Path] = field(default_factory=list)     # statement given as images
    submissions: list[Submission] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.statement.strip() and not self.images:
            raise ValueError(f"problem {self.id!r} needs a statement or images")

    @classmethod
    def from_dict(cls, d: dict[str, Any], base_dir: str | Path = ".") -> "Problem":
        """Build a problem; image paths are resolved relative to `base_dir`."""
        base = Path(base_dir)

        def resolve(paths: list[str]) -> list[Path]:
            out = [base / p for p in paths]
            for p in out:
                check_image(p)
            return out

        d = dict(d)
        d.setdefault("statement", "")
        d["answer"] = Answer(**d["answer"])
        d["images"] = resolve(d.get("images", []))
        d["submissions"] = [Submission(**{**s, "images": resolve(s.get("images", []))})
                            for s in d.get("submissions", [])]
        return cls(**d)


def load_problems(path: str | Path) -> list[Problem]:
    """Load problems from a YAML file or from every *.yaml file in a directory."""
    path = Path(path)
    files = sorted(path.glob("**/*.yaml")) if path.is_dir() else [path]
    problems: list[Problem] = []
    for f in files:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        problems.extend(Problem.from_dict(item, f.parent) for item in items)
    ids = [p.id for p in problems]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate problem ids: {sorted(dupes)}")
    return problems
