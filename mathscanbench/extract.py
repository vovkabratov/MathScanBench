"""Pull the final answer, confidence and verdict out of a model's reply."""

from __future__ import annotations

import re

_FINAL = re.compile(r"FINAL\s+ANSWER\s*[:=]\s*(.+)", re.IGNORECASE)
_CONF = re.compile(r"CONFIDENCE\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*%?", re.IGNORECASE)
_VERDICT = re.compile(r"VERDICT\s*[:=]\s*\**\s*(CORRECT|INCORRECT)", re.IGNORECASE)

# 1.6e-3, 1.6E-3, 1.6 x 10^-3, 1.6 × 10^{-3}, 1.6·10⁻³, 1,600
_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_NUMBER = re.compile(
    r"(?P<mant>[-+−]?\d[\d,]*(?:\.\d+)?|[-+−]?\.\d+)"
    r"(?:\s*(?:[eE](?P<e1>[-+]?\d+)|\s*(?:x|×|\*|·|\\times|\\cdot)\s*10\s*\^?\s*\{?\s*(?P<e2>[-+−]?\d+)\s*\}?))?"
)


# Commentary after the answer on the same line: "FiniteSet(0) — reading it as ..."
_COMMENT = re.compile(r"\s+(?:—|–|--)\s+.*$|;\s+.*$")


def has_final_marker(reply: str) -> bool:
    return bool(_FINAL.search(reply))


def final_answer(reply: str) -> str | None:
    """Text after the last 'FINAL ANSWER:' marker, stripped of markdown, $ and
    trailing commentary. Scoring is about the maths, not the format: if the
    marker is missing, the last short line before the CONFIDENCE line is used."""
    matches = _FINAL.findall(reply)
    if matches:
        ans = matches[-1].strip()
    else:
        lines = [l.strip() for l in reply.splitlines() if l.strip()]
        lines = [l for l in lines if not _CONF.match(l)]
        if not lines or len(lines[-1]) > 60:
            return None
        ans = lines[-1]
    ans = _COMMENT.sub("", ans)
    # Markdown emphasis, code ticks and math delimiters around the answer.
    ans = re.sub(r"^(?:[*_`$\s]|\\\(|\\\[)+", "", ans)
    ans = re.sub(r"(?:[*_`$\s]|\\\)|\\\]|\.(?=\s*$))+$", "", ans)
    if ans.startswith("\\boxed{") and ans.endswith("}"):
        ans = ans[len("\\boxed{"):-1]
    return ans.strip() or None


def confidence(reply: str) -> float | None:
    """Confidence as a probability in [0, 1]."""
    matches = _CONF.findall(reply)
    if not matches:
        return None
    v = float(matches[-1])
    return max(0.0, min(1.0, v / 100.0 if v > 1 else v))


def verdict(reply: str) -> str | None:
    matches = _VERDICT.findall(reply)
    return matches[-1].upper() if matches else None


def parse_number(text: str) -> tuple[float, str] | None:
    """Return (value, trailing unit text) from an answer string."""
    t = text.translate(_SUPERSCRIPT).replace("−", "-").replace("~", "")
    # "180*sqrt(2) ≈ 254.6 deg" or "= 5.2 m": the value is the last thing stated
    for sep in ("\\approx", "≈", "="):
        t = t.split(sep)[-1]
    t = t.strip()
    # Repeating decimals: 0.(3) or 0.1(6) with the period in brackets, 0.33.. or 0.33… repeating the last digit
    r = re.fullmatch(r"(-?)(\d+)[.,](\d*)\((\d+)\)", t) or re.fullmatch(r"(-?)(\d+)[.,](\d*?)(\d)(?:\.{2,}|…)", t)
    if r:
        sign, whole, fixed, period = r.groups()
        value = int(whole) + (int(fixed + period) - int(fixed or "0")) / (10 ** len(fixed) * (10 ** len(period) - 1))
        return (-value if sign else value), ""
    m = _NUMBER.search(t)
    if not m:
        return None
    mant = m.group("mant").replace("−", "-").replace(",", "")
    exp = m.group("e1") or m.group("e2")
    value = float(mant) * (10 ** int(exp.replace("−", "-")) if exp else 1)
    unit = t[m.end():].strip().strip("*$.`").replace("\\,", " ").replace("\\text{", "").replace("}", "").strip()
    return value, unit


def parse_choice(text: str) -> str | None:
    m = re.search(r"\b([A-H])\b", text.upper())
    return m.group(1) if m else None
