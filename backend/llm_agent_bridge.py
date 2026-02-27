"""
Module purpose:
- Coordinate one game step with two parallel LLM calls:
  1) main narrative stream call (剧情 + [command]),
  2) lazy NPC control call (related roles only, direct state override commands).

Functions:
- extract_command_blocks(text): pull command blocks wrapped in [command]...[/command].

Class:
- LLMAgentBridge
  - run_step_stream(...): stream narrative chunks and apply parsed commands to CommandPipeline.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from .command_pipeline import CommandPipeline
from .gemini_client import GeminiClient
from .llm_prompting import build_lazy_npc_prompt, build_narrative_prompt
from .narrative_assets import roles_related_to_node
from .state_snapshot import build_step_context


def extract_command_blocks(text: str) -> list[str]:
    """Extract command block payloads from `[command]...[/command]` sections."""

    if not text:
        return []
    pattern = re.compile(r"\[command\](.*?)\[/command\]", re.IGNORECASE | re.DOTALL)
    return [m.strip() for m in pattern.findall(text) if m.strip()]


class LLMAgentBridge:
    """Bridge runtime game state with two-parallel LLM request strategy."""

    def __init__(self, client: GeminiClient) -> None:
        self.client = client

    def run_step_stream(
        self,
        pipeline: CommandPipeline,
        recent_user_turns: list[str],
        current_user_input: str,
        apply_commands: bool = True,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Stream one step:
        - yield narrative chunks as they arrive.
        - finally yield summary packet with parsed commands and lazy-NPC output.
        """

        context = build_step_context(
            engine=pipeline.engine,
            pipeline=pipeline,
            recent_user_turns=recent_user_turns,
            current_user_input=current_user_input,
        )
        node_name = str(context["current_scene"]["name"])
        related_roles = roles_related_to_node(node_name)

        narrative_prompt = build_narrative_prompt(context)
        npc_prompt = build_lazy_npc_prompt(context, related_roles)

        with ThreadPoolExecutor(max_workers=1) as executor:
            npc_future: Future[str] = executor.submit(self.client.generate_text, npc_prompt)
            main_chunks: list[str] = []

            for chunk in self.client.stream_generate_text(narrative_prompt):
                main_chunks.append(chunk)
                yield {"type": "narrative_chunk", "text": chunk}

            main_text = "".join(main_chunks)
            npc_text = npc_future.result()

        npc_commands = self._flatten_commands(npc_text)
        narrative_commands = self._flatten_commands(main_text)
        applied: list[str] = []
        errors: list[str] = []

        if apply_commands:
            # NPC side should not directly drive global time; ignore such lines.
            for line in npc_commands:
                if line.startswith("time.advance"):
                    continue
                try:
                    pipeline.compile_line(line)
                    applied.append(line)
                except Exception as exc:  # keep runtime robust for story loop.
                    errors.append(f"NPC command failed: {line} -> {exc}")
            for line in narrative_commands:
                try:
                    pipeline.compile_line(line)
                    applied.append(line)
                except Exception as exc:
                    errors.append(f"Narrative command failed: {line} -> {exc}")

        yield {
            "type": "final",
            "node_name": node_name,
            "related_roles": related_roles,
            "main_text": main_text,
            "npc_text": npc_text,
            "narrative_commands": narrative_commands,
            "npc_commands": npc_commands,
            "applied_commands": applied,
            "errors": errors,
        }

    @staticmethod
    def _flatten_commands(text: str) -> list[str]:
        blocks = extract_command_blocks(text)
        lines: list[str] = []
        for block in blocks:
            for raw in block.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                lines.append(line)
        return lines
