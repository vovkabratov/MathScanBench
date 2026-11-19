"""Recompute every numeric reference answer from its formula, so a typo in a
problem file cannot silently become a wrong 'ground truth'."""

import math
from pathlib import Path

import pytest

from mathscanbench.schema import load_problems

PROBLEMS = {p.id: p for p in load_problems(Path(__file__).parent.parent / "problems")}

EXPECTED = {
    "beam-cantilever-tip-load": 1000 * 2**3 / (3 * 200e9 * 8e-6),
    "beam-simply-supported-udl": 5000 * 6**2 / 8,
    "axial-composite-bar-series": (50e3 / 500e-6) * (1 / 200e9 + 1 / 70e9),
    "axial-suddenly-applied-load": 2 * 100 * 9.81 / 100e-6,
    "torsion-solid-shaft-max-shear": 16 * 1000 / (math.pi * 0.05**3),
    "buckling-euler-pinned-pinned": math.pi**2 * 70e9 * 2e-7 / 1.5**2,
    "fracture-centre-crack-critical-stress": 30e6 / math.sqrt(math.pi * 0.005),
    "waves-bar-velocity-steel": math.sqrt(200e9 / 7850),
    # theoretical mechanics
    "tm-atwood-massive-pulley": (5 - 3) * 9.81 / (5 + 3 + 2 / 2),
    "tm-bowling-ball-slip-distance": 12 * 8**2 / (49 * 0.1 * 9.81),
    "tm-bead-rotating-hoop-angle": math.degrees(math.acos(9.81 / (10**2 * 0.2))),
    "tm-bead-rotating-hoop-frequency": 10 * math.sqrt(1 - (9.81 / (10**2 * 0.2))**2),
    "tm-hohmann-leo-geo": (lambda mu, r1, r2: math.sqrt(mu / r1) * (math.sqrt(2 * r2 / (r1 + r2)) - 1)
                           + math.sqrt(mu / r2) * (1 - math.sqrt(2 * r1 / (r1 + r2))))(3.986e14, 7000e3, 42164e3),
    "tm-ball-in-bowl-period": 2 * math.pi * math.sqrt(7 * (0.5 - 0.05) / (5 * 9.81)),
    "tm-coriolis-dropped-mass": 7.292e-5 * 9.81 * math.sqrt(2 * 100 / 9.81)**3 * math.cos(math.pi / 4) / 3,
    "tm-sliding-ladder-leaves-wall": math.degrees(math.asin(2 / 3 * math.sin(math.radians(60)))),
    "tm-torque-free-symmetric-precession": math.hypot(2 * 2, 3 * 10) / 2,
    "tm-apsidal-angle-power-law": 180 / math.sqrt(-2.5 + 3),
    "tm-heavy-top-slow-precession": (0.4 - math.sqrt(0.4**2 - 4 * 0.01 * math.cos(math.pi / 6) * 0.5))
                                    / (2 * 0.01 * math.cos(math.pi / 6)),
    # waves
    "wave-shear-speed-steel": math.sqrt(200e9 / (2 * 1.3) / 7850),
    "wave-fixed-free-bar-fundamental": math.sqrt(200e9 / 7850) / 4,
    "wave-p-speed-unbounded-steel": math.sqrt(200e9 * 0.7 / (1.3 * 0.4 * 7850)),
    "wave-bar-on-bar-impact-stress": math.sqrt(200e9 * 7850) * 10 / 2,
    "wave-area-change-transmission": 90e6 * 2 / 3,
    "wave-steel-to-aluminium-transmission": 100e6 * 2 * math.sqrt(70e9 * 2700)
                                            / (math.sqrt(70e9 * 2700) + math.sqrt(200e9 * 7850)),
    "wave-rayleigh-speed-poisson-solid": 3000 * math.sqrt(2 - 2 / math.sqrt(3)),
    "wave-flexural-group-velocity": 2 * math.sqrt(2 * math.pi * 1000) * (200e9 * 0.01**2 / (12 * 7850))**0.25,
    "wave-second-critical-angle-water-steel": math.degrees(math.asin(1480 / 3200)),
    "wave-spall-triangular-pulse": 100 / 300 * 0.1 / 2,
    "wave-von-karman-critical-velocity": 250e6 / math.sqrt(200e9 * 7850) + 150e6 / math.sqrt(2e9 * 7850),
    "wave-hertz-sphere-collision-duration": (lambda m, R, Es: 2.9432 * (15 * m / 2 / (16 * Es * math.sqrt(R / 2)))**0.4)(
        7850 * 4 / 3 * math.pi * 0.01**3, 0.01, 200e9 / (2 * (1 - 0.3**2))),
    # fracture
    "frac-edge-crack-sif": 1.12 * 100 * math.sqrt(math.pi * 0.002),
    "frac-astm-e399-thickness": 2.5 * (50 / 500)**2,
    "frac-g-from-k-plane-strain": 40e6**2 * (1 - 0.3**2) / 200e9,
    "frac-griffith-glass": math.sqrt(2 * 70e9 * 1 / (math.pi * 1e-6)),
    "frac-finite-width-secant": 150 * math.sqrt(math.pi * 0.02 / math.cos(math.pi * 0.2)),
    "frac-weibull-size-effect": 300e6 * 8**-0.1,
    "frac-penny-crack-critical-size": 2 * math.pi / 4 * (30 / 300)**2,
    "frac-leak-before-break": 100e6 * 0.02 / (1 * math.sqrt(math.pi * 0.02)),
    "frac-paris-law-life": 2 / (1e-11 * (100 * math.sqrt(math.pi))**3)
                           * (0.001**-0.5 - (1 / math.pi * (50 / 100)**2)**-0.5),
    "frac-mts-mode-ii-kink-angle": math.degrees(math.acos(1 / 3)),
    "frac-dugdale-ctod": 8 * 400e6 * 0.01 / (math.pi * 200e9) * math.log(1 / math.cos(math.pi / 4)),
    "frac-r-curve-instability": math.sqrt(2e5 * 70e9 / (2 * math.pi * math.sqrt(0.01))),
    # plasticity
    "plast-von-mises-tension-shear": math.sqrt(200e6**2 + 3 * 100e6**2),
    "plast-rectangular-plastic-moment": 250e6 * 0.05 * 0.1**2 / 4,
    "plast-shape-factor-circle": 16 / (3 * math.pi),
    "plast-partially-plastic-torsion": 2 * math.pi / 3 * 150e6 * 0.02**3 * (1 - 0.5**3 / 4),
    "plast-torsion-residual-surface": 150e6 / 3,
    "plast-considere-uts": 500e6 * 0.2**0.2 * math.exp(-0.2),
    "plast-kinematic-hardening-reverse-yield": 2 * 200e6 - (200e6 + 10e9 * (0.01 - 200e6 / 200e9)),
    "plast-prandtl-punch": (2 + math.pi) * 300e6 / math.sqrt(3),
    "plast-portal-frame-collapse": 6 * 100e3 / (4 / 2 + 4 / 2),  # (P/2) h + P (L/2) = 6 Mp
    "plast-thick-cylinder-partial-yield": 300e6 * (math.log(75 / 50) + (100**2 - 75**2) / (2 * 100**2)),
}


@pytest.mark.parametrize("pid,value", sorted(EXPECTED.items()))
def test_reference_matches_formula(pid, value):
    ref = PROBLEMS[pid].answer
    assert math.isclose(float(ref.value), value, rel_tol=1e-3), (pid, ref.value, value)


def test_every_numeric_problem_is_checked():
    numeric = {p.id for p in PROBLEMS.values() if p.answer.type == "numeric"}
    assert numeric == set(EXPECTED)
