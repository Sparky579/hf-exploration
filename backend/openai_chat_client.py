"""
Module purpose:
- Provide minimal OpenAI-compatible Chat Completions client (non-stream + stream SSE).

Class:
- OpenAIChatClient
  - generate_text(prompt): single-response call.
  - stream_generate_parts(prompt): stream delta parts with optional thought flag.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Generator
from typing import Any


class OpenAIChatClient:
    """OpenAI-compatible Chat Completions client using stdlib HTTP."""

    REASONING_MINIMAL = "minimal"
    REASONING_LOW = "low"
    REASONING_MEDIUM = "medium"
    REASONING_HIGH = "high"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: int = 120,
        reasoning_effort: str = REASONING_MINIMAL,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key must be non-empty.")
        model_text = str(model or "").strip()
        if not model_text:
            raise ValueError("model must be non-empty for openai provider.")
        self.api_key = api_key.strip()
        self.model = model_text
        self.base_url = self._normalize_base_url(base_url)
        self.timeout_seconds = int(timeout_seconds)
        self.reasoning_effort = self._normalize_reasoning_effort(reasoning_effort)

    def set_reasoning_effort(self, reasoning_effort: str) -> None:
        self.reasoning_effort = self._normalize_reasoning_effort(reasoning_effort)

    def generate_text(self, prompt: str) -> str:
        """Generate one complete response text."""

        url = self._build_url()
        try:
            body = self._build_body(prompt=prompt, stream=False, include_reasoning=True)
            data = self._post_json(url, body)
        except RuntimeError as first_exc:
            # Compatibility-first fallback: retry once without reasoning params.
            try:
                body = self._build_body(prompt=prompt, stream=False, include_reasoning=False)
                data = self._post_json(url, body)
            except RuntimeError:
                raise first_exc
        return self._extract_text(data)

    def stream_generate_text(self, prompt: str) -> Generator[str, None, str]:
        """Generate response text in stream mode and yield non-thought chunks."""

        chunks: list[str] = []
        for part in self.stream_generate_parts(prompt):
            if bool(part.get("thought", False)):
                continue
            text = str(part.get("text", ""))
            if not text:
                continue
            chunks.append(text)
            yield text
        return "".join(chunks)

    def stream_generate_parts(self, prompt: str) -> Generator[dict[str, Any], None, None]:
        """Generate response in stream mode and yield delta parts with thought flag."""

        try:
            yield from self._stream_generate_parts_once(prompt=prompt, include_reasoning=True)
            return
        except RuntimeError as first_exc:
            # Compatibility-first fallback: retry once without reasoning params.
            try:
                yield from self._stream_generate_parts_once(prompt=prompt, include_reasoning=False)
                return
            except RuntimeError:
                raise first_exc

    def _stream_generate_parts_once(
        self,
        prompt: str,
        include_reasoning: bool,
    ) -> Generator[dict[str, Any], None, None]:
        url = self._build_url()
        body = self._build_body(prompt=prompt, stream=True, include_reasoning=include_reasoning)
        req = urllib.request.Request(
            url=url,
            data=json.dumps(body).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        emitted = False
        raw_buffer_parts: list[str] = []
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                for raw_line in resp:
                    decoded = raw_line.decode("utf-8", errors="ignore")
                    raw_buffer_parts.append(decoded)
                    line = decoded.strip()
                    if not line.startswith("data:"):
                        continue
                    data_text = line[len("data:") :].strip()
                    if not data_text or data_text == "[DONE]":
                        continue
                    for packet in self._parse_maybe_packed_json(data_text):
                        thought_delta, answer_delta = self._extract_delta_text(packet)
                        if thought_delta:
                            emitted = True
                            yield {"text": thought_delta, "thought": True}
                        if answer_delta:
                            emitted = True
                            yield {"text": answer_delta, "thought": False}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenAI stream request failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI stream request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI stream parse failed: {exc}") from exc

        if emitted:
            return

        # Fallback: some OpenAI-compatible gateways return normal JSON body even on stream=true.
        raw_payload = "".join(raw_buffer_parts).strip()
        if not raw_payload:
            return
        packet = self._try_parse_json_text(raw_payload)
        if packet is None:
            return
        text = self._extract_text(packet)
        if text:
            yield {"text": text, "thought": False}

    @staticmethod
    def _parse_maybe_packed_json(text: str) -> list[dict[str, Any]]:
        text = str(text or "").strip()
        if not text:
            return []
        one = OpenAIChatClient._try_parse_json_text(text)
        if isinstance(one, dict):
            return [one]
        rows: list[dict[str, Any]] = []
        for item in OpenAIChatClient._extract_packed_json_objects(text):
            parsed = OpenAIChatClient._try_parse_json_text(item)
            if isinstance(parsed, dict):
                rows.append(parsed)
        return rows

    @staticmethod
    def _try_parse_json_text(text: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(text)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _extract_packed_json_objects(text: str) -> list[str]:
        objects: list[str] = []
        start = -1
        depth = 0
        in_string = False
        escaped = False
        for idx, ch in enumerate(text):
            if start == -1:
                if ch == "{":
                    start = idx
                    depth = 1
                    in_string = False
                    escaped = False
                continue
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                depth += 1
                continue
            if ch == "}":
                depth -= 1
                if depth == 0:
                    objects.append(text[start : idx + 1])
                    start = -1
        return objects

    def _post_json(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            url=url,
            data=json.dumps(body).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                payload = resp.read().decode("utf-8")
            return json.loads(payload)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenAI request failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    def _build_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "HF-Explore-Client/1.0",
        }

    def _build_body(self, prompt: str, stream: bool, include_reasoning: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": bool(stream),
        }
        if include_reasoning:
            body["reasoning_effort"] = self.reasoning_effort
        return body

    @classmethod
    def _normalize_reasoning_effort(cls, raw: str) -> str:
        level = str(raw or "").strip().lower()
        if level in {
            cls.REASONING_MINIMAL,
            cls.REASONING_LOW,
            cls.REASONING_MEDIUM,
            cls.REASONING_HIGH,
        }:
            return level
        raise ValueError("reasoning_effort must be one of: minimal/low/medium/high")

    @staticmethod
    def _normalize_base_url(raw: str) -> str:
        text = str(raw or "").strip()
        if not text:
            return "https://api.openai.com/v1"
        return text.rstrip("/")

    @staticmethod
    def _looks_like_reasoning_error(message: str) -> bool:
        msg = message.lower()
        return (
            "reasoning_effort" in msg
            or "unsupported" in msg
            or "unknown" in msg
            or "invalid" in msg
            or "unrecognized" in msg
        )

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content")
        return OpenAIChatClient._coerce_content_text(content)

    @staticmethod
    def _extract_delta_text(packet: dict[str, Any]) -> tuple[str, str]:
        choices = packet.get("choices")
        if not isinstance(choices, list) or not choices:
            return ("", "")
        first = choices[0]
        if not isinstance(first, dict):
            return ("", "")
        delta = first.get("delta", {})
        if (not isinstance(delta, dict)) and isinstance(first.get("message"), dict):
            # Some gateways send full message object in stream chunks.
            delta = first.get("message", {})
        if not isinstance(delta, dict):
            return ("", "")

        answer_delta = OpenAIChatClient._coerce_content_text(delta.get("content"))
        thought_delta = ""
        for key in ("reasoning_content", "reasoning", "reasoning_text"):
            value = delta.get(key)
            text = OpenAIChatClient._coerce_content_text(value)
            if text:
                thought_delta += text
        return (thought_delta, answer_delta)

    @staticmethod
    def _coerce_content_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""
        rows: list[str] = []
        for item in content:
            if isinstance(item, str):
                rows.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                rows.append(text)
                continue
            if isinstance(text, dict) and isinstance(text.get("value"), str):
                rows.append(text["value"])
                continue
            if isinstance(item.get("content"), str):
                rows.append(item["content"])
        return "".join(rows)
