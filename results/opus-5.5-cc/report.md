# MathScanBench results

## Accuracy

| Model | Correct | Wrong with confidence ≥ 80% |
|---|---|---|
| claude-code:claude-opus-5-5 | 100% (96/96) | 0% (0/96) |

## By topic

| Topic | claude-code:claude-opus-5-5 |
|---|---|
| algebra | 100% (8/8) |
| arithmetic | 100% (7/7) |
| decimals | 100% (6/6) |
| equations | 100% (1/1) |
| exponential-equations | 100% (3/3) |
| exponential-inequalities | 100% (5/5) |
| expressions | 100% (2/2) |
| fractions | 100% (2/2) |
| geometry | 100% (4/4) |
| inequalities | 100% (1/1) |
| irrational-equations | 100% (4/4) |
| irrational-inequalities | 100% (2/2) |
| linear-equations | 100% (22/22) |
| logarithmic-inequalities | 100% (2/2) |
| logarithms | 100% (9/9) |
| number-sets | 100% (1/1) |
| parameters | 100% (1/1) |
| powers | 100% (1/1) |
| quadratics | 100% (2/2) |
| ratio | 100% (1/1) |
| rational-equations | 100% (1/1) |
| roots | 100% (2/2) |
| stereometry | 100% (1/1) |
| systems | 100% (3/3) |
| word-problems | 100% (5/5) |

## By difficulty

| Difficulty | claude-code:claude-opus-5-5 |
|---|---|
| 1 | 100% (70/70) |
| 2 | 100% (16/16) |
| 3 | 100% (5/5) |
| 4 | 100% (4/4) |
| 5 | 100% (1/1) |

## Calibration

![Calibration](calibration.png)

## Verification

Can a verifier model spot wrong solutions without seeing the reference answer?

| Verifier | Solver | Wrong solutions caught | Correct solutions rejected |
|---|---|---|---|
| claude-code:claude-opus-5-5 | student | 93% (13/14) | 1% (1/68) |

Wrong solutions the verifier accepted: s2-171929-1
