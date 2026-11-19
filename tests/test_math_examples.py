"""Local-only checks for math_examples/: photos of real notebooks, kept out of
git. Skipped when the folder is not on this machine."""

import hashlib
import json
from pathlib import Path

import pytest

from mathscanbench.cli import main
from mathscanbench.grade import grade
from mathscanbench.images import IMAGE_TYPES
from mathscanbench.prompts import solve_prompt, solve_system
from mathscanbench.schema import load_problems

FOLDER = Path(__file__).parent.parent / "math_examples"
YAML = FOLDER / "math_examples.yaml"
pytestmark = pytest.mark.skipif(not YAML.exists(), reason="math_examples/ is local only")


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def problems():
    return load_problems(YAML)


def test_every_photo_is_used(problems):
    photos = {p for p in FOLDER.rglob("*") if p.suffix.lower() in IMAGE_TYPES}
    used = {img for p in problems for img in p.images}
    unused = photos - used
    # The only photos left out are byte-identical copies of ones that are used.
    used_hashes = {_md5(p) for p in used}
    assert all(_md5(p) in used_hashes for p in unused), sorted(map(str, unused))


def test_reference_answers_grade_as_correct(problems):
    for p in problems:
        a = p.answer
        text = a.value if a.type != "numeric" else f"{a.value} {a.unit}".strip()
        assert grade(str(text), a).correct, p.id


def test_prompts_are_maths_with_one_photo(problems):
    for p in problems:
        assert "mathematics" in solve_system(p.subject)
        prompt = solve_prompt(p)
        assert sum(isinstance(x, Path) for x in prompt) == 1


def test_ids_do_not_contain_the_answer(problems):
    for p in problems:
        if p.answer.type == "numeric":
            person_and_photo = p.id.rsplit("-", 1)[0]   # the last part is the item number
            assert f"-{p.answer.value}-" not in f"-{person_and_photo}-", p.id


def test_offline_pipeline(tmp_path, problems):
    results = tmp_path / "results"
    main(["--results", str(results), "run", str(YAML), "--model", "mock", "--samples", "1"])
    main(["--results", str(results), "verify", str(YAML), "--verifier", "mock", "--solver", "student"])
    verify = [json.loads(l) for l in (results / "verify.jsonl").read_text().splitlines()]
    assert len(verify) == sum(len(p.submissions) for p in problems)
