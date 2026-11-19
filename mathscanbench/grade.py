"""Grade an extracted answer against the reference answer."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import pint
import sympy as sp

from .extract import parse_choice, parse_number
from .schema import Answer

_ureg = pint.UnitRegistry()
_ureg.define("MPa_sqrt_m = MPa * m ** 0.5")


@dataclass
class Grade:
    correct: bool
    parsed: str | None      # what the grader understood the answer to be
    note: str = ""          # why it failed, if it did


def _to_unit(value: float, unit_text: str, target: str) -> float | None:
    """Convert value [unit_text] to the target unit. None if the units clash."""
    if not unit_text or unit_text.lower() in {target.lower(), "dimensionless"}:
        return value
    clean = unit_text
    for root in ("√(m)", "√m", "sqrt(m)", "m^(1/2)", "m^1/2", "m**(1/2)"):
        clean = clean.replace(root, " m**0.5")
    clean = (clean.replace("·", "*").replace("√", "sqrt").replace("²", "**2")
             .replace("³", "**3").replace("^", "**").replace("⁴", "**4"))
    try:
        q = _ureg.Quantity(value, clean)
        return q.to(target.replace("·", "*").replace("^", "**")).magnitude
    except Exception:
        return None


def grade_numeric(text: str, ref: Answer) -> Grade:
    parsed = parse_number(text)
    if parsed is None:
        return Grade(False, None, "no number found")
    value, unit = parsed
    converted = _to_unit(value, unit, ref.unit or "")
    if converted is None:
        # Units could not be reconciled: fall back to the bare number, and say so.
        converted, note = value, f"unit '{unit}' not understood; compared bare number"
    else:
        note = ""
    target = float(ref.value)
    ok = math.isclose(converted, target, rel_tol=ref.rel_tol, abs_tol=1e-12)
    return Grade(ok, f"{converted:.6g} {ref.unit}", note if not ok else "")


def grade_symbolic(text: str, ref: Answer) -> Grade:
    symbols = {s: sp.Symbol(s, positive=True) for s in ref.symbols}
    try:
        got = sp.sympify(re.sub(r"_\{(\w+)\}", r"_\1", text).replace("^", "**"), locals=symbols)
        want = sp.sympify(str(ref.value), locals=symbols)
    except Exception as e:  # unparseable expression
        return Grade(False, None, f"could not parse expression: {e}")
    got, want = _as_sympy(got), _as_sympy(want)
    if isinstance(got, (sp.Set, sp.Tuple)) or isinstance(want, (sp.Set, sp.Tuple)):
        return _grade_structured(got, want)
    if not isinstance(got, sp.Expr):
        return Grade(False, str(got), "not an expression")
    # Same symbol in other notation: M_p or M_{p} for Mp.
    plain = {re.sub(r"[_{}]", "", str(s)): s for s in got.free_symbols}
    got = got.subs({s: symbols[name] for name, s in plain.items()
                    if name in symbols and s is not symbols[name]})
    extra = got.free_symbols - set(symbols.values())
    if extra:
        return Grade(False, str(got), f"uses symbols not in the problem: {sorted(map(str, extra))}")
    if sp.simplify(got - want) == 0:
        return Grade(True, str(got))
    # Numeric spot-check at random positive points catches forms simplify misses.
    import random

    rng = random.Random(0)
    for _ in range(5):
        point = {s: rng.uniform(0.5, 3.0) for s in symbols.values()}
        g, w = complex(got.evalf(subs=point)), complex(want.evalf(subs=point))
        if not math.isclose(abs(g - w), 0, abs_tol=1e-9 * max(1, abs(w))):
            return Grade(False, str(got), "not equivalent to reference")
    return Grade(True, str(got))


def _as_sympy(x):
    """sympify leaves Python sets and tuples ({1, 2}, (1, 2)) as they are."""
    if isinstance(x, (set, frozenset)):
        return sp.FiniteSet(*x)
    if isinstance(x, (tuple, list)):
        return sp.Tuple(*x)
    return x


def _grade_structured(got, want) -> Grade:
    """Sets and intervals (solution sets of equations and inequalities) and
    tuples (solutions of systems, in the order asked)."""
    if isinstance(want, sp.Tuple):
        ok = (isinstance(got, sp.Tuple) and len(got) == len(want)
              and all(sp.simplify(g - w) == 0 for g, w in zip(got, want)))
    elif isinstance(want, sp.Set):
        ok = isinstance(got, sp.Set) and sp.simplify(got.symmetric_difference(want)) == sp.EmptySet
    else:
        ok = False
    return Grade(ok, str(got), "" if ok else "not the same set or tuple as reference")


def grade_choice(text: str, ref: Answer) -> Grade:
    letter = parse_choice(text)
    if letter is None:
        return Grade(False, None, "no option letter found")
    return Grade(letter == str(ref.value).upper(), letter)


def grade(text: str | None, ref: Answer) -> Grade:
    if text is None:
        return Grade(False, None, "no FINAL ANSWER line")
    return {"numeric": grade_numeric, "symbolic": grade_symbolic, "choice": grade_choice}[ref.type](text, ref)
