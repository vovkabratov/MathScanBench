"""Problems and solutions given as images."""

import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from mathscanbench import images
from mathscanbench.cli import main
from mathscanbench.models import MockClient
from mathscanbench.prompts import free_verify_prompt, solve_prompt, verify_prompt
from mathscanbench.schema import load_problems

ROOT = Path(__file__).parent.parent
EXAMPLE = ROOT / "examples" / "image_problems.yaml"
REPLIES = ROOT / "examples" / "mock_replies.json"


def test_image_paths_resolve_relative_to_yaml():
    (p,) = load_problems(EXAMPLE)
    assert p.images == [ROOT / "examples" / "images" / "beam_midspan_problem.png"]
    assert [s.correct for s in p.submissions] == [True, False]
    assert all(img.is_file() for s in p.submissions for img in s.images)


def test_missing_image_is_a_load_error(tmp_path):
    (tmp_path / "p.yaml").write_text(
        "id: x\ntopic: t\ndifficulty: 1\nimages: [missing.png]\n"
        "answer: {type: numeric, value: 1, unit: m}\n")
    with pytest.raises(FileNotFoundError):
        load_problems(tmp_path)


def test_unsupported_image_type(tmp_path):
    with pytest.raises(ValueError, match="HEIC"):
        images.check_image(tmp_path / "scan.heic")


def test_prompt_places_images_under_their_headings():
    (p,) = load_problems(EXAMPLE)
    prompt = verify_prompt(p, "", p.submissions[1].images)
    kinds = [type(x).__name__ if not isinstance(x, str) else "text" for x in prompt]
    assert kinds.count("text") == 3 and len(prompt) == 5
    assert "PROBLEM:" in prompt[0] and prompt[1] == p.images[0]
    assert "PROPOSED SOLUTION:" in prompt[2] and prompt[3] == p.submissions[1].images[0]


def test_text_only_problems_still_give_plain_text_prompts():
    problems = load_problems(ROOT / "problems")
    assert all(isinstance(solve_prompt(p), str) for p in problems)
    assert isinstance(free_verify_prompt("statement", [], "solution", []), str)


def test_anthropic_and_openai_content_blocks():
    (p,) = load_problems(EXAMPLE)
    blocks = images.to_anthropic(solve_prompt(p))
    img = [b for b in blocks if b["type"] == "image"]
    assert len(img) == 1 and img[0]["source"]["media_type"] == "image/png"
    assert base64.b64decode(img[0]["source"]["data"]) == p.images[0].read_bytes()
    assert "[problem beam-midspan-from-image]" in blocks[0]["text"]

    oblocks = images.to_openai(solve_prompt(p))
    assert any(b["type"] == "image_url" and b["image_url"]["url"].startswith("data:image/png;base64,")
               for b in oblocks)


def test_phone_photo_is_rotated_and_large_scan_shrunk(tmp_path):
    path = tmp_path / "photo.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise to display
    Image.new("RGB", (6000, 3000), "white").save(path, exif=exif)
    media_type, data = images.load_image(path)
    out = Image.open(io.BytesIO(data))
    assert media_type == "image/jpeg"
    assert out.size == (images.MAX_EDGE // 2, images.MAX_EDGE)   # upright and within limits


def test_mock_sees_image_placeholders():
    (p,) = load_problems(EXAMPLE)
    assert "[image: beam_midspan_problem.png]" in images.text_only(solve_prompt(p))
    assert "FINAL ANSWER" in MockClient().complete("", solve_prompt(p))


def test_image_pipeline_with_submissions(tmp_path):
    results = tmp_path / "results"
    main(["--results", str(results), "run", str(EXAMPLE), "--model", f"mock:{REPLIES}", "--samples", "1"])
    main(["--results", str(results), "verify", str(EXAMPLE), "--verifier", f"mock:{REPLIES}"])
    main(["--results", str(results), "report"])

    (solve,) = [json.loads(l) for l in (results / "solve.jsonl").read_text().splitlines()]
    assert solve["correct"] and solve["input"] == "image"
    verify = [json.loads(l) for l in (results / "verify.jsonl").read_text().splitlines()]
    assert sorted((r["solver"], r["solution_correct"]) for r in verify) == [
        (f"mock:{REPLIES}", True), ("student", False), ("student", True)]


def test_ask_and_check_commands(capsys):
    img = ROOT / "examples" / "images" / "beam_midspan_problem.png"
    main(["ask", "--model", "mock", str(img)])
    assert "--- answer:" in capsys.readouterr().out
    main(["check", "--model", "mock", "--problem", str(img),
          "--solution", str(ROOT / "examples" / "images" / "beam_midspan_solution_wrong.png")])
    assert "--- verdict:" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["check", "--model", "mock", "--problem", str(img)])


def test_ollama_client_sends_openai_blocks(monkeypatch):
    import urllib.request

    from mathscanbench.models import get_client

    sent = {}

    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_urlopen(req, timeout):
        sent["url"], sent["body"] = req.full_url, json.loads(req.data)
        return Reply(json.dumps({"choices": [{"message": {"content": "FINAL ANSWER: 1"}}]}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    (p,) = load_problems(EXAMPLE)
    assert get_client("ollama:gemma4:31b-cloud").complete("sys", solve_prompt(p)) == "FINAL ANSWER: 1"
    assert sent["url"] == "http://localhost:11434/v1/chat/completions"
    assert sent["body"]["model"] == "gemma4:31b-cloud"
    assert any(b["type"] == "image_url" for b in sent["body"]["messages"][1]["content"])


def test_openrouter_client_and_no_retry_on_bad_key(monkeypatch):
    import urllib.error
    import urllib.request

    from mathscanbench.models import RequestError, get_client

    calls = []

    def bad_key(req, timeout):
        calls.append(req)
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"error":"bad key"}'))

    monkeypatch.setattr(urllib.request, "urlopen", bad_key)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    client = get_client("openrouter:anthropic/claude-haiku-5.5")
    with pytest.raises(RequestError, match="401"):
        client.complete("sys", "hello")
    assert len(calls) == 1                                   # not retried
    assert calls[0].full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert calls[0].get_header("Authorization") == "Bearer test-key"
    body = json.loads(calls[0].data)
    assert body["model"] == "anthropic/claude-haiku-5.5" and body["max_tokens"] == 32000

    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_client("openrouter:anthropic/claude-haiku-5.5")


def test_rate_limit_waits_and_retries(monkeypatch):
    import urllib.error

    from mathscanbench import models

    waits, calls = [], []
    monkeypatch.setattr(models.time, "sleep", waits.append)

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError("u", 429, "Too Many Requests", {"Retry-After": "7"}, None)
        return "ok"

    assert models._retry(flaky) == "ok"
    assert waits == [7.0, 7.0]


def test_endless_keep_alive_reply_times_out(monkeypatch):
    from mathscanbench import models

    clock = iter(range(0, 10_000, 100))
    monkeypatch.setattr(models.time, "monotonic", lambda: next(clock))

    class KeepAlive:
        def read1(self, n):
            return b" "

    with pytest.raises(TimeoutError):
        models._read_with_deadline(KeepAlive(), 600)
    assert models._read_with_deadline(io.BytesIO(b'{"a": 1}'), 600) == b'{"a": 1}'


def test_claude_code_client_puts_images_in_an_empty_folder(tmp_path, monkeypatch):
    import subprocess

    from mathscanbench.models import get_client

    img = tmp_path / "page.png"
    Image.new("RGB", (40, 30), "white").save(img)
    seen = {}

    def fake_run(cmd, cwd, **kw):
        seen["cmd"], seen["files"] = cmd, sorted(p.name for p in Path(cwd).iterdir())
        out = {"result": "FINAL ANSWER: 3\nCONFIDENCE: 90", "is_error": False, "usage": {}, "total_cost_usd": 0.01}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(out), "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    log = tmp_path / "usage.jsonl"
    monkeypatch.setenv("MATHSCANBENCH_USAGE_LOG", str(log))
    reply = get_client("claude-code:claude-opus-5-5").complete("system", ["Solve this.", img])
    assert reply.startswith("FINAL ANSWER: 3")
    assert seen["files"] == ["image1.png"]
    cmd = seen["cmd"]
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5"
    assert cmd[cmd.index("--tools") + 1] == "Read" and "--strict-mcp-config" in cmd
    assert "./image1.png" in cmd[2]
    assert json.loads(log.read_text())["cost_usd"] == 0.01
