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

    def __init__(self, api_key: str, model: str = "gemini-3-flash-preview", timeout_seconds: int = 120) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key must be non-empty.")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_seconds = int(timeout_seconds)

    def generate_text(self, prompt: str) -> str:
        """Generate one complete response text."""

        url = self._build_url(stream=False)
        body = self._build_body(prompt)
        data = self._post_json(url, body)
        return self._extract_text(data)

    def stream_generate_text(self, prompt: str) -> Generator[str, None, str]:
        """Generate response text in stream mode and yield chunks."""

        url = self._build_url(stream=True)
        body = self._build_body(prompt)
        req = urllib.request.Request(
            url=url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        chunks: list[str] = []
        prev_full = ""
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
                    full_or_delta = self._extract_text(packet)
                    if not full_or_delta:
                        continue
                    # Gemini SSE packets may be cumulative; normalize to delta stream.
                    if full_or_delta.startswith(prev_full):
                        delta = full_or_delta[len(prev_full) :]
                    else:
                        delta = full_or_delta
                    if not delta:
                        continue
                    prev_full = full_or_delta
                    chunks.append(delta)
                    yield delta
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Gemini stream request failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Gemini stream request failed: {exc}") from exc
        return "".join(chunks)

    def _build_url(self, stream: bool) -> str:
        action = "streamGenerateContent?alt=sse" if stream else "generateContent"
        model_name = urllib.parse.quote(self.model, safe="")
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:{action}"
            f"&key={urllib.parse.quote(self.api_key, safe='')}"
            if stream
            else f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:{action}?key={urllib.parse.quote(self.api_key, safe='')}"
        )

    @staticmethod
    def _build_body(prompt: str) -> dict[str, Any]:
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ]
        }

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
