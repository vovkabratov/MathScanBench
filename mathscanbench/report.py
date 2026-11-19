"""Summarise results as a Markdown report with two figures.

Headline metrics:
- accuracy per model, overall and by topic and difficulty
- confidently-wrong rate: share of answers that are wrong with confidence >= 0.8
- calibration: stated confidence vs observed accuracy
- for the verify experiment: how often wrong solutions are caught, and how often
  correct solutions are falsely rejected
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CONFIDENT = 0.8


def _pct(n: int, d: int) -> str:
    return "–" if d == 0 else f"{100 * n / d:.0f}% ({n}/{d})"


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def calibration_bins(rows: list[dict], n_bins: int = 5) -> list[tuple[float, float, int]]:
    """(mean confidence, accuracy, count) per confidence bin."""
    bins: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("confidence") is not None:
            bins[min(int(r["confidence"] * n_bins), n_bins - 1)].append(r)
    out = []
    for b in sorted(bins):
        rs = bins[b]
        out.append((sum(r["confidence"] for r in rs) / len(rs), sum(r["correct"] for r in rs) / len(rs), len(rs)))
    return out


def write_report(solve: list[dict], verify: list[dict], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = ["# MathScanBench results", ""]

    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in solve:
        by_model[r["model"]].append(r)

    # Overall
    rows = []
    for m, rs in sorted(by_model.items()):
        n_ok = sum(r["correct"] for r in rs)
        cw = sum((not r["correct"]) and (r.get("confidence") or 0) >= CONFIDENT for r in rs)
        rows.append([m, _pct(n_ok, len(rs)), _pct(cw, len(rs))])
    md += ["## Accuracy", "", _table(["Model", "Correct", f"Wrong with confidence ≥ {CONFIDENT:.0%}"], rows), ""]

    # By topic and difficulty, and by input (text vs image) when both occur
    for r in solve:
        r.setdefault("input", "text")
    breakdowns = [("topic", "By topic"), ("difficulty", "By difficulty")]
    if len({r["input"] for r in solve}) > 1:
        breakdowns.append(("input", "By input (text vs image)"))
    for key, title in breakdowns:
        values = sorted({r[key] for r in solve}, key=str)
        models = sorted(by_model)
        trows = []
        for v in values:
            cells = [str(v)]
            for m in models:
                rs = [r for r in by_model[m] if r[key] == v]
                cells.append(_pct(sum(r["correct"] for r in rs), len(rs)))
            trows.append(cells)
        md += [f"## {title}", "", _table([key.capitalize()] + models, trows), ""]

    # Confidently wrong examples: the cases worth reading by hand
    cw_rows = [r for r in solve if not r["correct"] and (r.get("confidence") or 0) >= CONFIDENT]
    if cw_rows:
        md += ["## Confidently wrong answers", "",
               _table(["Model", "Problem", "Answer given", "Reference", "Confidence"],
                      [[r["model"], r["problem_id"], str(r["answer_text"]), str(r["reference"]),
                        f"{r['confidence']:.0%}"] for r in cw_rows[:40]]), ""]

    # Calibration figure
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], color="#999", lw=1, ls="--", label="perfect calibration")
    for m, rs in sorted(by_model.items()):
        pts = calibration_bins(rs)
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", label=m)
    ax.set_xlabel("Stated confidence")
    ax.set_ylabel("Observed accuracy")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Calibration")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "calibration.png", dpi=160)
    plt.close(fig)
    md += ["## Calibration", "", "![Calibration](calibration.png)", ""]

    # Verify experiment
    if verify:
        pairs: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for r in verify:
            pairs[(r["verifier"], r["solver"])].append(r)
        vrows = []
        for (v, s), rs in sorted(pairs.items()):
            wrong = [r for r in rs if not r["solution_correct"]]
            right = [r for r in rs if r["solution_correct"]]
            caught = sum(r["verdict"] == "INCORRECT" for r in wrong)
            false_alarm = sum(r["verdict"] == "INCORRECT" for r in right)
            vrows.append([v, s, _pct(caught, len(wrong)), _pct(false_alarm, len(right))])
        md += ["## Verification", "",
               "Can a verifier model spot wrong solutions without seeing the reference answer?", "",
               _table(["Verifier", "Solver", "Wrong solutions caught", "Correct solutions rejected"], vrows), ""]

        missed = [r for r in verify if not r["solution_correct"] and r["verdict"] == "CORRECT"]
        if missed:
            md += ["Wrong solutions the verifier accepted: " +
                   ", ".join(sorted({r["problem_id"] for r in missed})), ""]

    path = out_dir / "report.md"
    path.write_text("\n".join(md), encoding="utf-8")
    return path
