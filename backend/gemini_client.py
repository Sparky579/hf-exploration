"""
Module purpose:
- Provide minimal Gemini HTTP client with both normal and stream (SSE) output modes.

Class:
- GeminiClient
  - generate_text(prompt): single-response call.
  - stream_generate_text(prompt): generator yielding text chunks in streaming mode.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Generator
from typing import Any


class GeminiClient:
    """Gemini API client using stdlib HTTP."""

    THINKING_DEFAULT = "default"
    THINKING_MINIMAL = "minimal"
    THINKING_LOW = "low"
    THINKING_MEDIUM = "medium"
    THINKING_HIGH = "high"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3-flash-preview",
        base_url: str = "",
        timeout_seconds: int = 120,
        thinking_level: str = THINKING_MINIMAL,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key must be non-empty.")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.timeout_seconds = int(timeout_seconds)
        self.thinking_level = self._normalize_thinking_level(thinking_level)

    def set_thinking_level(self, thinking_level: str) -> None:
        self.thinking_level = self._normalize_thinking_level(thinking_level)

    def generate_text(self, prompt: str) -> str:
        """Generate one complete response text."""

        url = self._build_url(stream=False)
        try:
            body = self._build_body(prompt, thinking_level=self.thinking_level)
            data = self._post_json(url, body)
        except RuntimeError as exc:
            if not self._looks_like_thinking_config_error(str(exc)):
                raise
            body = self._build_body(prompt, thinking_level=self.THINKING_DEFAULT)
            data = self._post_json(url, body)
        return self._extract_text(data)

    def stream_generate_text(self, prompt: str) -> Generator[str, None, str]:
        """Generate response text in stream mode and yield chunks."""

        chunks: list[str] = []
        for part in self.stream_generate_parts(prompt):
            if part.get("thought", False):
                continue
            text = str(part.get("text", ""))
            if not text:
                continue
            chunks.append(text)
            yield text
        return "".join(chunks)

    def stream_generate_parts(self, prompt: str) -> Generator[dict[str, Any], None, None]:
        """Generate response in stream mode and yield delta parts with thought flag."""

        level = self.thinking_level
        try:
            yield from self._stream_generate_parts_once(
                prompt,
                thinking_level=level,
            )
            return
        except RuntimeError as exc:
            if not self._looks_like_thinking_config_error(str(exc)):
                raise
        # Fallback for endpoints/models that do not support thinking config payload.
        yield from self._stream_generate_parts_once(
            prompt,
            thinking_level=self.THINKING_DEFAULT,
        )

    def _stream_generate_parts_once(
        self,
        prompt: str,
        thinking_level: str,
    ) -> Generator[dict[str, Any], None, None]:
        url = self._build_url(stream=True)
        body = self._build_body(prompt, thinking_level=thinking_level)
        req = urllib.request.Request(
            url=url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        prev_thought = ""
        prev_answer = ""
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    data_text = line[len("data:") :].strip()
                    if not data_text or data_text == "[DONE]":
                        continue
                    packet = json.loads(data_text)
                    thought_full, answer_full = self._extract_text_by_thought(packet)

                    thought_delta = (
                        thought_full[len(prev_thought) :]
                        if thought_full.startswith(prev_thought)
                        else thought_full
                    )
                    answer_delta = (
                        answer_full[len(prev_answer) :]
                        if answer_full.startswith(prev_answer)
                        else answer_full
                    )

                    prev_thought = thought_full
                    prev_answer = answer_full

                    if thought_delta:
                        yield {"text": thought_delta, "thought": True}
                    if answer_delta:
                        yield {"text": answer_delta, "thought": False}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Gemini stream request failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Gemini stream request failed: {exc}") from exc

    def _build_url(self, stream: bool) -> str:
        action = "streamGenerateContent?alt=sse" if stream else "generateContent"
        model_name = urllib.parse.quote(self.model, safe="")
        base = self.base_url or "https://generativelanguage.googleapis.com/v1beta"
        return (
            f"{base}/models/{model_name}:{action}"
            f"&key={urllib.parse.quote(self.api_key, safe='')}"
            if stream
            else f"{base}/models/{model_name}:{action}?key={urllib.parse.quote(self.api_key, safe='')}"
        )

    @staticmethod
    def _build_body(
        prompt: str,
        thinking_level: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ]
        }
        if thinking_level != GeminiClient.THINKING_DEFAULT:
            body["generationConfig"] = {
                "thinkingConfig": {
                    "thinkingLevel": thinking_level,
                    "includeThoughts": True,
                }
            }
        return body

    @staticmethod
    def _normalize_thinking_level(raw: str) -> str:
        level = str(raw or "").strip().lower()
        if level == "none":
            # Compatibility: treat old "none" as fastest "minimal".
            return GeminiClient.THINKING_MINIMAL
        if level in {
            GeminiClient.THINKING_DEFAULT,
            GeminiClient.THINKING_MINIMAL,
            GeminiClient.THINKING_LOW,
            GeminiClient.THINKING_MEDIUM,
            GeminiClient.THINKING_HIGH,
        }:
            return level
        raise ValueError("thinking_level must be one of: default/minimal/low/medium/high")

    @staticmethod
    def _looks_like_thinking_config_error(message: str) -> bool:
        msg = message.lower()
        return (
            "thinking" in msg
            or "thinkingconfig" in msg
            or "generationconfig" in msg
            or "unknown name" in msg
            or "invalid json payload" in msg
        )

    def _post_json(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            url=url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                payload = resp.read().decode("utf-8")
            return json.loads(payload)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Gemini request failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        texts: list[str] = []
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
        return "".join(texts)

    @staticmethod
    def _extract_text_by_thought(data: dict[str, Any]) -> tuple[str, str]:
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return ("", "")
        parts = candidates[0].get("content", {}).get("parts", [])
        thought_texts: list[str] = []
        answer_texts: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if not isinstance(text, str) or not text:
                continue
            if bool(part.get("thought")):
                thought_texts.append(text)
            else:
                answer_texts.append(text)
        return ("".join(thought_texts), "".join(answer_texts))
