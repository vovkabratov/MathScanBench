"""Model clients. Each client turns a system prompt and user content (text, or
text mixed with images; see images.py) into a reply string.

Model names:
- "claude-..."      -> Anthropic API (needs ANTHROPIC_API_KEY)
- "gpt-..." / "o..." -> OpenAI API (needs OPENAI_API_KEY)
- "ollama:<model>"  -> Ollama at OLLAMA_HOST (default http://localhost:11434),
                       including cloud models such as ollama:gemma4:31b-cloud
- "openrouter:<vendor>/<model>" -> OpenRouter (needs OPENROUTER_API_KEY), for
                       example openrouter:anthropic/claude-haiku-5.5
- "claude-code:<model>" -> the Claude Code CLI (`claude -p`), using its logged-in
                       subscription, for example claude-code:claude-opus-5-5
- "mock:<file>"     -> replies read from a JSON file, for offline tests
- "mock"            -> a deterministic fake model, for offline tests
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Protocol

from .images import Content, text_only, to_anthropic, to_openai


class ModelClient(Protocol):
    name: str

    def complete(self, system: str, user: Content, temperature: float = 1.0) -> str: ...


def _retry(fn, attempts: int = 4, rate_limit_attempts: int = 8):
    """Retry network errors a few times, and rate limits (HTTP 429) for longer,
    waiting as long as the server's Retry-After header asks."""
    i = 0
    while True:
        try:
            return fn()
        except RequestError:
            raise
        except Exception as e:
            limited = getattr(e, "code", None) == 429
            i += 1
            if i >= (rate_limit_attempts if limited else attempts):
                raise
            wait = 2 ** i
            if limited:
                after = (getattr(e, "headers", None) or {}).get("Retry-After", "")
                wait = float(after) if after.replace(".", "", 1).isdigit() else min(60, 5 * 2 ** (i - 1))
            time.sleep(wait)


@dataclass
class AnthropicClient:
    name: str
    max_tokens: int = 8000

    def __post_init__(self) -> None:
        import anthropic  # optional dependency

        self._client = anthropic.Anthropic()

    def complete(self, system: str, user: Content, temperature: float = 1.0) -> str:
        content = to_anthropic(user)

        def call():
            msg = self._client.messages.create(
                model=self.name,
                max_tokens=self.max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": content}],
            )
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

        return _retry(call)


@dataclass
class OpenAIClient:
    name: str

    def __post_init__(self) -> None:
        import openai  # optional dependency

        self._client = openai.OpenAI()

    def complete(self, system: str, user: Content, temperature: float = 1.0) -> str:
        content = to_openai(user)

        def call():
            r = self._client.chat.completions.create(
                model=self.name,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
            )
            return r.choices[0].message.content or ""

        return _retry(call)


class RequestError(Exception):
    """An API error that retrying will not fix (bad key, unknown model, no credits)."""


@dataclass
class ChatCompletionsClient:
    """Any OpenAI-compatible /chat/completions endpoint, called with the standard
    library. Used for Ollama and OpenRouter; images are sent as data URLs."""

    name: str
    url: str
    api_key: str = ""
    headers: dict[str, str] | None = None
    timeout: float = 600
    max_tokens: int = 32000  # room for hidden reasoning; OpenRouter otherwise reserves the model's maximum

    def __post_init__(self) -> None:
        self._model = self.name.split(":", 1)[1]

    def complete(self, system: str, user: Content, temperature: float = 1.0) -> str:
        import urllib.error
        import urllib.request

        body = json.dumps({
            "model": self._model,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": to_openai(user)}],
        }).encode()
        headers = {"Content-Type": "application/json", **(self.headers or {})}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key

        def call():
            req = urllib.request.Request(self.url, data=body, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    reply = json.loads(_read_with_deadline(r, self.timeout))
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:500]
                if e.code in (400, 401, 402, 403, 404):
                    raise RequestError(f"{self.name}: HTTP {e.code}: {detail}") from None
                raise
            if "choices" not in reply:  # OpenRouter can report errors with status 200
                raise RuntimeError(f"{self.name}: {reply.get('error', reply)}")
            return reply["choices"][0]["message"]["content"] or ""

        # Providers behind OpenRouter occasionally return an empty reply; ask again.
        for _ in range(3):
            text = _retry(call)
            if text.strip():
                break
        return text


def _read_with_deadline(response, seconds: float) -> bytes:
    """Read a whole response, failing if it takes longer than `seconds` in total.
    OpenRouter keeps a slow request open by sending blank keep-alive bytes, so a
    stalled provider never trips the socket's per-read timeout."""
    deadline = time.monotonic() + seconds
    chunks = []
    while chunk := response.read1(65536):
        chunks.append(chunk)
        if time.monotonic() > deadline:
            raise TimeoutError(f"no complete reply within {seconds:.0f} s")
    return b"".join(chunks)


def ollama_client(name: str) -> ChatCompletionsClient:
    """Cloud models go through the local daemon after `ollama signin`, or directly
    with OLLAMA_HOST=https://ollama.com and OLLAMA_API_KEY."""
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if not host.startswith("http"):
        host = "http://" + host
    return ChatCompletionsClient(name, host.rstrip("/") + "/v1/chat/completions",
                                 os.environ.get("OLLAMA_API_KEY", ""))


def openrouter_client(name: str) -> ChatCompletionsClient:
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("set OPENROUTER_API_KEY to use OpenRouter models")
    return ChatCompletionsClient(name, "https://openrouter.ai/api/v1/chat/completions",
                                 os.environ["OPENROUTER_API_KEY"], {"X-Title": "MathScanBench"})


@dataclass
class ClaudeCodeClient:
    """Claude through the Claude Code CLI (`claude -p`), billed to the Claude
    subscription it is logged in with instead of an API key. Each call runs in a
    fresh, empty folder holding only that call's images, which the model opens
    with its Read tool; no other tools are allowed. The CLI sets its own
    temperature, so the temperature argument is ignored."""
    name: str                      # "claude-code:<model>", e.g. claude-code:claude-opus-5-5
    timeout: int = 900
    usage_log: str | None = None   # optional JSONL of per-call usage and notional cost

    def complete(self, system: str, user: Content, temperature: float = 1.0) -> str:
        import subprocess
        import tempfile
        from pathlib import Path

        from .images import IMAGE_TYPES, load_image, parts

        model = self.name.split(":", 1)[1]
        with tempfile.TemporaryDirectory(prefix="mathscanbench-") as tmp:
            text, n = [], 0
            for p in parts(user):
                if isinstance(p, str):
                    text.append(p)
                    continue
                n += 1
                media_type, data = load_image(p)
                ext = next(e for e, t in IMAGE_TYPES.items() if t == media_type)
                (Path(tmp) / f"image{n}{ext}").write_bytes(data)
                text.append(f"[Image {n}: ./image{n}{ext}]")
            if n:
                text.insert(0, "The images for this task are files in the current folder; "
                               "open each one with the Read tool before answering.")
            cmd = ["claude", "-p", "\n\n".join(text), "--model", model, "--system-prompt", system,
                   "--tools", "Read", "--allowedTools", "Read", "--output-format", "json",
                   "--no-session-persistence",
                   # no MCP servers or skills: they add ~30k tokens of unrelated context
                   "--strict-mcp-config", "--disable-slash-commands"]

            def call():
                r = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=self.timeout)
                if r.returncode != 0:
                    raise RuntimeError(f"{self.name}: claude exited {r.returncode}: {(r.stderr or r.stdout)[-500:]}")
                out = json.loads(r.stdout)
                if out.get("is_error"):
                    raise RuntimeError(f"{self.name}: {str(out.get('result'))[:500]}")
                return out

            out = _retry(call)
        if self.usage_log:
            with open(self.usage_log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"model": self.name, "usage": out.get("usage"),
                                    "cost_usd": out.get("total_cost_usd"),
                                    "turns": out.get("num_turns")}) + "\n")
        return out.get("result") or ""


@dataclass
class MockClient:
    """Offline stand-in. With a replies file, returns the stored reply for the
    problem id found in the prompt; otherwise returns a fixed, wrong answer."""

    name: str = "mock"
    replies: dict[str, str] | None = None

    def complete(self, system: str, user: Content, temperature: float = 1.0) -> str:
        user = text_only(user)
        if self.replies:
            for pid, reply in self.replies.items():
                if f"[problem {pid}]" in user:
                    return reply
        return "I am not sure.\nFINAL ANSWER: 1\nCONFIDENCE: 50"


def get_client(name: str) -> ModelClient:
    if name == "mock":
        return MockClient()
    if name.startswith("mock:"):
        path = name.split(":", 1)[1]
        with open(path, encoding="utf-8") as f:
            return MockClient(name=name, replies=json.load(f))
    if name.startswith("ollama:"):
        return ollama_client(name)
    if name.startswith("openrouter:"):
        return openrouter_client(name)
    if name.startswith("claude-code:"):
        return ClaudeCodeClient(name, usage_log=os.environ.get("MATHSCANBENCH_USAGE_LOG"))
    if name.startswith("claude"):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("set ANTHROPIC_API_KEY to use Claude models")
        return AnthropicClient(name)
    if name.startswith(("gpt", "o1", "o3", "o4", "o5")):
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("set OPENAI_API_KEY to use OpenAI models")
        return OpenAIClient(name)
    raise ValueError(f"unknown model {name!r}")
