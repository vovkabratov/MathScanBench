# MathScanBench

[![tests](https://github.com/vovkabratov/MathScanBench/actions/workflows/tests.yml/badge.svg)](https://github.com/vovkabratov/MathScanBench/actions/workflows/tests.yml)

**When a language model marks handwritten maths, where does it go wrong, and does it know?**

MathScanBench tests how well language models solve and check maths and mechanics
problems, typed or photographed from handwritten notebooks. It grades answers
automatically and reports three things: solving accuracy, errors made at high
stated confidence, and how often a model accepts a wrong solution or rejects a
correct one.

## Findings

Ten models, 96 problems photographed from four students' notebooks, 82 student
solutions to check, and 60 typed mechanics problems.
Full write-up: [TestReport.pdf](TestReport.pdf).

1. **Models misread; they rarely miscalculate.** 75 of the 88 wrong photo
   answers start from reading the page wrongly (a digit, a sign, a decimal
   comma, the wrong item). Only 4 are clear maths errors.
2. **The student's working pulls the reading towards the student's answer.**
   Models copied the student's own wrong answer 8 times, and several replies say
   they chose the reading of an unclear digit or sign that fitted the student's
   working. In a separate test, four Claude models only transcribed the pages:
   on two of the three most-misread pages they read the digit or sign correctly
   in 23 of 24 attempts. Checking is harder than solving: every model lets
   through 1 to 6 of the 14 wrong solutions.
3. **Confidence separates models more than accuracy does.** Several models
   state 85–100% confidence on every error they make. Others put their errors
   among their least confident answers, which is what makes a human review
   step workable.
4. **More reasoning effort does not improve reading.** In a separate
   transcription test, effort changed how cautious a reading was, in either
   direction, but not how accurate.

| Model | Photos solved (of 96) | Errors at ≥ 80% confidence | Wrong solutions caught (of 14) | Correct solutions accepted (of 68) | Typed mechanics (of 300) |
|---|---|---|---|---|---|
| Opus 5.5 † | 96 | none | 13 | 67 | – |
| Fable 5.2 ‡ | 94 | 0 of 2 | 12 | 68 | – |
| GPT-6.1 Sol | 94 | 2 of 2 | 12 | 66 | – |
| Kimi K3.1 Pro | 94 | 2 of 2 | 10 | 65 | – |
| Gemini 3.8 Flash | 92 | 4 of 4 | 10 | 67 | – |
| Haiku 5.5 § | 88 | 1 of 8 | 12 | 47 | 295 |
| GPT-6 Luna | 86 | 7 of 10 | 9 | 66 | 297 |
| DeepSeek V4.1 Flash | 80 | 16 of 16 | 8 | 63 | 299 |
| Gemma 4 31B | 74 | 22 of 22 | 11 | 53 | 271 |
| GLM 5.3 Flash | 74 | 11 of 22 | 9 | 61 | – |

† The reference answers were drafted with Opus 5.5 and then checked by hand, so
a misreading shared by Opus and the checker would not show. Treat its row as an
upper bound.
‡ Run through agent sessions at high effort, not through an API; close to, but
not the same as, the other rows. Its raw replies are not in `results/`.
§ 19 of Haiku's 21 rejections of correct solutions come from a flaw in the
checking prompt, described in the report.

### Limits

- One sample per photo problem and only 14 wrong student solutions. Differences
  of two or three problems between models are within noise.
- The photo set is mostly school maths (70 of 96 at the lowest difficulty), in
  four people's handwriting.
- The typed mechanics set was run on four models only.

## What is in this repository

| Path | Contents |
|---|---|
| `mathscanbench/` | The framework: model clients, prompts, answer extraction, grading (numeric with units, symbolic, multiple choice), reports |
| `problems/` | 60 typed mechanics problems with reference answers, from statics to fracture and plasticity |
| `results/` | Every model reply and grade from the runs in the report, one folder per model |
| `examples/` | A small image problem and canned replies for offline runs |
| `tests/` | Unit tests and an offline end-to-end run; every numeric reference answer is recomputed from its formula |

**The notebook photos are not included.** They are other people's handwritten
work. The mechanics results can be reproduced from this repository; the photo
results can be inspected in `results/` but not rerun. To run the photo tests on
your own material, see [Add your own photos](#add-your-own-photos).

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
```

Try the whole pipeline offline, with a fake model and no API key:

```bash
.venv/bin/mathscanbench --results demo run problems/ --model mock:examples/mock_replies.json --samples 1
.venv/bin/mathscanbench --results demo verify problems/ --verifier mock
.venv/bin/mathscanbench --results demo report      # writes demo/report.md
```

Run a real model through [OpenRouter](https://openrouter.ai):

```bash
export OPENROUTER_API_KEY=your-key
.venv/bin/mathscanbench run problems/ --model openrouter:google/gemini-3.8-flash --samples 1
.venv/bin/mathscanbench verify problems/ --verifier openrouter:google/gemini-3.8-flash
.venv/bin/mathscanbench report                     # writes results/report.md
```

Full replies are saved in `results/solve.jsonl` and `results/verify.jsonl`.
An interrupted run resumes where it stopped.

### Supported models

| Model name | Runs through | Needs |
|---|---|---|
| `openrouter:<vendor>/<model>` | OpenRouter | `OPENROUTER_API_KEY` |
| `claude-...` | Anthropic API | `ANTHROPIC_API_KEY`, `pip install -e ".[anthropic]"` |
| `gpt-...` | OpenAI API | `OPENAI_API_KEY`, `pip install -e ".[openai]"` |
| `claude-code:<model>` | Claude Code CLI | a logged-in `claude` command |
| `ollama:<model>` | Ollama | `OLLAMA_HOST` (default `http://localhost:11434`) |
| `mock`, `mock:<file>` | nothing | offline testing |

### One-off problems

```bash
.venv/bin/mathscanbench ask   --model claude-opus-5-5 problem.jpg
.venv/bin/mathscanbench check --model claude-opus-5-5 --problem problem.jpg --solution page1.jpg
```

## Add your own photos

Put the photos and a YAML file under `math_examples/`; this folder is excluded
from Git. Image paths are relative to the YAML file. For example, create
`math_examples/my_photos.yaml` alongside `question.jpg` and `solution.jpg`:

```yaml
- id: my-beam-question
  topic: beams
  difficulty: 1
  images: [question.jpg]
  answer: { type: numeric, value: 1.40625e-3, unit: m, rel_tol: 0.01 }
  solution: The known reference calculation goes here.
  submissions:
    - author: student
      correct: true
      images: [solution.jpg]
```

Set `answer` to the known answer and each submission's `correct` value from
your own marking, then pass `math_examples/my_photos.yaml` in place of
`problems/`. Use PNG, JPEG, GIF or WebP images; convert HEIC photos and PDF
scans first.

## Author

Vladimir Bratov, Professor of Mathematics, Edinburgh Napier University ·
[bratov.com](https://www.bratov.com) · vladimir@bratov.com

MIT License.
