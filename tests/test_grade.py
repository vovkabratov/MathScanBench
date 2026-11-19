from mathscanbench.grade import grade
from mathscanbench.schema import Answer

NUM = Answer(type="numeric", value=1.6667e-3, unit="m", rel_tol=0.01)


def test_numeric_same_unit():
    assert grade("1.667e-3 m", NUM).correct
    assert not grade("1.8e-3 m", NUM).correct


def test_numeric_converts_units():
    assert grade("1.667 mm", NUM).correct
    assert grade("239 MPa", Answer(type="numeric", value=239.4e6, unit="Pa")).correct
    assert grade("22.5 kN*m", Answer(type="numeric", value=22500, unit="N*m")).correct


def test_numeric_wrong_scale_is_caught():
    # Right digits, wrong unit: 1.667 m is not 1.667 mm.
    assert not grade("1.667 m", NUM).correct


def test_symbolic_equivalence():
    ref = Answer(type="symbolic", value="sqrt(k1*k2/(m*(k1 + k2)))", symbols=["k1", "k2", "m"])
    assert grade("sqrt(k1*k2/((k1+k2)*m))", ref).correct
    assert grade("1/sqrt(m*(1/k1 + 1/k2))", ref).correct
    assert not grade("sqrt((k1+k2)/m)", ref).correct


def test_choice():
    ref = Answer(type="choice", value="B", options={"A": "a", "B": "b"})
    assert grade("B", ref).correct
    assert grade("(B) tensile", ref).correct
    assert not grade("A", ref).correct


def test_missing_answer():
    assert not grade(None, NUM).correct


def test_solution_sets_and_intervals():
    ref = Answer(type="symbolic", value="Union(Interval(-oo, 1), FiniteSet(3), Interval(5, oo))")
    assert grade("Union(FiniteSet(3), Interval(-oo, 1), Interval(5, oo))", ref).correct
    assert not grade("Union(Interval(-oo, 1), Interval(5, oo))", ref).correct   # lost x = 3
    assert not grade("Union(Interval.open(-oo, 1), FiniteSet(3), Interval(5, oo))", ref).correct
    logs = Answer(type="symbolic", value="Interval.open(log(5)/log(7), 1)")
    assert grade("Interval.open(log(5, 7), 1)", logs).correct
    assert grade("{4, 6, 5}", Answer(type="symbolic", value="FiniteSet(4, 5, 6)")).correct
    assert grade("EmptySet", Answer(type="symbolic", value="EmptySet")).correct
    assert not grade("36", Answer(type="symbolic", value="EmptySet")).correct


def test_tuples_are_ordered():
    ref = Answer(type="symbolic", value="(-1, -5, 6)")
    assert grade("(-1, -5, 6)", ref).correct
    assert not grade("(-5, -1, 6)", ref).correct
    assert not grade("6", ref).correct


def test_exact_fractions():
    ref = Answer(type="symbolic", value="13/12")
    assert grade("13/12", ref).correct
    assert grade("1 + 1/12", ref).correct
    assert not grade("1.08", ref).correct


def test_symbolic_answer_with_unknown_symbol_is_wrong_not_a_crash():
    ref = Answer(type="symbolic", value="6*Mp/L", symbols=["Mp", "L"])
    g = grade("6*Mq/L", ref)
    assert not g.correct and "Mq" in g.note
    assert grade("6*Mp/L", ref).correct
    assert grade("6*M_p/L", ref).correct and grade("6*M_{p}/L", ref).correct   # notation only
    assert not grade("8*M_p/L", ref).correct


def test_value_after_approx_sign_is_graded():
    ref = Answer(type="numeric", value=254.56, unit="degree")
    assert grade(r"180\sqrt{2} \approx 254.6°", ref).correct
    assert grade("180*sqrt(2) ≈ 254.6 degrees", ref).correct
