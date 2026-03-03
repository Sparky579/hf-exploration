from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map, get_scene_paragraph
from backend.gemini_client import GeminiClient
from backend.llm_agent_bridge import LLMAgentBridge
from backend.openai_chat_client import OpenAIChatClient
from backend.state_snapshot import _predict_next_node_from_input

app = FastAPI(title="Campus Game API")

# Allow local frontend to access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store
# session_id -> dict with engine, pipeline, client, bridge, recent_turns, last_system_text
sessions: dict[str, dict[str, Any]] = {}
LOG_DIR = ROOT_DIR / "backend" / "logs"
OPENING_FIXED_TEXT = (
    "你是向西中学的一名普通学生。最近，一款名为《皇室战争》的游戏在班级里掀起了狂热的风暴，即便是最严厉的课堂，也有人甘冒被抓的风险在课桌下偷偷沉迷于此，也包括你和你的好朋友罗宾，陈洛和马超鹏。\n"
    "枯燥的数学课上，老师正在讲解着复数的定义。这正如催眠曲般回荡。你埋下头偷偷按亮手机，一条爆炸性的消息突然跃入眼帘，好消息：《皇室战争：超现实大更新》！\n"
    "\"超现实？\"你盯着屏幕微微发愣，\"这是什么意思？以前怎么从来没听说过这个版本？\"\n"
    "尽管心中充满疑惑，但对新版本的好奇心犹如猫挠。你激动得掌心微汗，必须立刻决断，请选择：\n"
    "1. 流量更新\n"
    "2. 借同桌马超鹏热点更新\n"
    "3. 先认真听数学课"
)

class InitResponse(BaseModel):
    session_id: str
    message: str
    state: dict[str, Any]

class ActionRequest(BaseModel):
    session_id: str
    action_text: str
    resume_hint: Optional[str] = None
    is_retry: Optional[bool] = False

class StartRequest(BaseModel):
    provider: Optional[str] = "gemini"
    api_key: Optional[str] = None
    model: Optional[str] = "gemini-3-flash-preview"
    base_url: Optional[str] = None
    reasoning_effort: Optional[str] = None
    thinking_level: Optional[str] = None


def _build_runtime() -> tuple[GameEngine, CommandPipeline]:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)

    main_player_name = "主控玩家"
    main_player = PlayerRole(main_player_name, campus, cfg, "东教学楼内部", health=10)
    engine.register_player(main_player)
    engine.set_main_player(main_player_name)
    engine.set_main_game_state("not_installed")

    Role("李再斌", campus, cfg, "宿舍", health=10)
    Role("黎诺存", campus, cfg, "西教学楼南", health=10)
    Role("颜宏帆", campus, cfg, "东教学楼内部", health=10)
    Role("信息老师", campus, cfg, "国际部", health=10)
    Role("陈洛", campus, cfg, "南教学楼", health=10)
    Role("李秦彬", campus, cfg, "食堂", health=10)

    for name, profile in engine.character_profiles.items():
        if "敌对" not in str(profile.alignment):
            continue
        if name not in campus.roles:
            continue
        engine.promote_role_to_player(name, card_deck=list(profile.card_deck), card_valid=4)

    pipeline = CommandPipeline(engine)
    pipeline.compile_line("[global.main_player=主控玩家]")
    return engine, pipeline


def _get_node_description(engine: GameEngine, node_name: str) -> str:
    node = engine.campus_map.get_node(node_name)
    state_rows = [str(text).strip() for text in node.states if str(text).strip()]
    if state_rows:
        return " ".join(state_rows)
    return str(get_scene_paragraph(node_name)).strip()


def _build_card_details(main: PlayerRole) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    holy_water = float(main.holy_water)
    for idx, card_name in enumerate(main.card_deck):
        card = main.available_cards.get(card_name)
        consume = float(getattr(card, "consume", 0.0))
        in_valid_window = idx < int(main.card_valid)
        holy_water_enough = holy_water + 1e-9 >= consume
        unavailable_reason: str | None = None
        if not in_valid_window:
            unavailable_reason = "当前排序没到"
        elif not holy_water_enough:
            unavailable_reason = "圣水花费不足"
        rows.append(
            {
                "name": card_name,
                "consume": consume,
                "description": str(getattr(card, "describe", "")).strip(),
                "index": idx,
                "in_valid_window": in_valid_window,
                "holy_water_enough": holy_water_enough,
                "playable": in_valid_window and holy_water_enough,
                "unavailable_reason": unavailable_reason,
            }
        )
    return rows


def _collect_scene_units(engine: GameEngine, node_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner_name, player in engine.players.items():
        for unit in player.list_active_units():
            if unit.node_name != node_name:
                continue
            rows.append(
                {
                    "unit_id": unit.unit_id,
                    "owner": owner_name,
                    "name": unit.card.name,
                    "health": float(unit.current_health),
                    "max_health": float(unit.card.health),
                    "attack": float(unit.card.attack),
                    "is_flying": bool(unit.card.is_flying),
                    "card_type": str(unit.card.unit_class),
                    "node": unit.node_name,
                }
            )
    return rows


def _collect_nearby_scene_units(engine: GameEngine, center_node: str) -> list[dict[str, Any]]:
    node = engine.campus_map.get_node(center_node)
    nearby_nodes = [center_node, *sorted(node.neighbors)]
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for node_name in nearby_nodes:
        for item in _collect_scene_units(engine, node_name):
            unit_id = str(item.get("unit_id", "")).strip()
            if not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            row = dict(item)
            row["node"] = node_name
            rows.append(row)
    return rows


def _get_player_state(engine: GameEngine) -> dict[str, Any]:
    main_name = engine.main_player_name or "主控玩家"
    main = engine.get_player(main_name)
    role = engine.get_role(main_name)
    
    current_node = engine.campus_map.get_node(role.current_location)
    neighbors = sorted(list(current_node.neighbors))

    companions = engine.global_config.list_team_companions()
    companion_details: list[dict[str, Any]] = []
    for name in companions:
        row: dict[str, Any] = {"name": name}
        if name in engine.campus_map.roles:
            r = engine.get_role(name)
            row["health"] = r.health
        elif name in engine.character_profiles and engine.get_character_profile(name).status == "存活":
            row["health"] = 10.0
        if name in engine.character_profiles:
            p = engine.get_character_profile(name)
            row["status"] = p.status
        companion_details.append(row)
    location_description = _get_node_description(engine, role.current_location)
    neighbor_details = [
        {
            "name": name,
            "description": _get_node_description(engine, name),
        }
        for name in neighbors
    ]
    card_details = _build_card_details(main)
    scene_units = _collect_scene_units(engine, role.current_location)
    nearby_scene_units = _collect_nearby_scene_units(engine, role.current_location)
    friendly_owners = {main_name, *companions}
    friendly_units = [u for u in nearby_scene_units if str(u.get("owner", "")) in friendly_owners]
    enemy_units = [u for u in nearby_scene_units if str(u.get("owner", "")) not in friendly_owners]
    
    return {
        "time": engine.global_config.current_time_unit,
        "location": role.current_location,
        "location_description": location_description,
        "hp": role.health,
        "holy_water": main.holy_water,
        "main_game_state": engine.global_config.main_game_state,
        "card_deck": list(main.card_deck),
        "card_valid": int(main.card_valid),
        "card_details": card_details,
        "neighbors": neighbors,
        "neighbor_details": neighbor_details,
        "companions": companions,
        "companion_details": companion_details,
        "scene_units": scene_units,
        "friendly_units": friendly_units,
        "enemy_units": enemy_units,
        "global_states": list(engine.global_config.global_states),
        "global_dynamic_states": list(engine.global_config.dynamic_states[-7:]),
        "battle_target": engine.global_config.battle_state or role.battle_target,
        "game_over": engine.game_over,
        "game_result": engine.game_result
    }


def _extract_retryable_commands(errors: list[Any]) -> list[str]:
    rows: list[str] = []
    marker = "command failed:"
    permanent_markers = (
        "invalid bool value",
        "unknown game event id",
        "unknown scene event id",
        "role not found",
        "unsupported",
        "requires main player",
    )
    for item in errors:
        text = str(item or "").strip()
        if marker not in text:
            continue
        tail = text.split(marker, 1)[1].strip()
        reason = tail.split("->", 1)[1].strip().lower() if "->" in tail else ""
        if any(x in reason for x in permanent_markers):
            continue
        command = tail.split("->", 1)[0].strip()
        if command:
            rows.append(command)
    dedup: list[str] = []
    seen: set[str] = set()
    for line in rows:
        if line in seen:
            continue
        seen.add(line)
        dedup.append(line)
    return dedup


def _apply_pending_retries(session: dict[str, Any], pipeline: CommandPipeline) -> list[str]:
    pending = list(session.get("pending_failed_commands", []) or [])
    if not pending:
        return []
    notes: list[str] = []
    keep: list[str] = []
    permanent_markers = (
        "invalid bool value",
        "unknown game event id",
        "unknown scene event id",
        "role not found",
        "unsupported",
        "requires main player",
    )
    for line in pending:
        try:
            pipeline.compile_line(str(line))
            notes.append(f"auto-retry success: {line}")
        except Exception as exc:
            reason = str(exc).lower()
            if any(x in reason for x in permanent_markers):
                notes.append(f"auto-retry dropped(permanent): {line} -> {exc}")
                continue
            keep.append(str(line))
            notes.append(f"auto-retry failed: {line} -> {exc}")
    session["pending_failed_commands"] = keep[-30:]
    return notes


def _try_auto_apply_main_move(
    engine: GameEngine,
    pipeline: CommandPipeline,
    action_text: str,
    recent_user_turns: list[str],
) -> dict[str, Any] | None:
    main_name = engine.main_player_name
    if not main_name:
        return None
    role = engine.get_role(main_name)
    current_node = role.current_location
    target = _predict_next_node_from_input(
        engine=engine,
        current_node=current_node,
        current_user_input=action_text,
        recent_user_turns=recent_user_turns,
    )
    if not target or target == current_node:
        return None
    node = engine.campus_map.get_node(current_node)
    if target not in set(node.neighbors):
        return None

    move_cost = float(engine.global_config.get_effective_main_move_cost(1.0))
    pipeline.compile_line(f"[{main_name}.move={target}]")
    pipeline.compile_line("[queue.flush=true]")
    pipeline.compile_line(f"[time.advance={move_cost:g}]")
    return {
        "from_node": current_node,
        "to_node": target,
        "time_advanced": move_cost,
    }


def _append_session_debug_log(session: dict[str, Any], payload: dict[str, Any]) -> None:
    path_text = str(session.get("debug_log_file", "")).strip()
    if not path_text:
        return
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "logged_at": datetime.now().isoformat(timespec="seconds"),
        **payload,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _init_prompt_text_log(path_text: str, session_id: str) -> None:
    path = Path(str(path_text or "").strip())
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(f"SESSION {session_id}\n")
        f.write(f"CREATED_AT {datetime.now().isoformat(timespec='seconds')}\n\n")


def _append_prompt_text_log(
    session: dict[str, Any],
    *,
    action: str,
    prompt_text: str,
    time_value: float,
) -> None:
    path_text = str(session.get("prompt_log_file", "")).strip()
    if not path_text:
        return
    text = str(prompt_text or "").strip()
    if not text:
        return
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    round_index = int(session.get("prompt_round_index", 0)) + 1
    session["prompt_round_index"] = round_index
    with path.open("a", encoding="utf-8") as f:
        f.write(f"ROUND {round_index} | t={time_value:g} | action={action}\n\n")
        f.write(text.rstrip() + "\n\n")


def _read_debug_log_all(path_text: str) -> list[dict[str, Any]]:
    path = Path(str(path_text or "").strip())
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _read_prompt_log_text(path_text: str) -> str:
    path = Path(str(path_text or "").strip())
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


@app.post("/api/start", response_model=InitResponse)
def start_game(req: StartRequest):
    provider = str(req.provider or "gemini").strip().lower()
    if provider not in {"gemini", "openai"}:
        raise HTTPException(status_code=400, detail="provider must be 'gemini' or 'openai'.")

    api_key = (req.api_key or "").strip()
    if not api_key:
        env_name = "GOOGLE_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
        api_key = str(os.getenv(env_name, "")).strip()
    if not api_key:
        missing = "Gemini API key" if provider == "gemini" else "OpenAI API key"
        raise HTTPException(status_code=400, detail=f"Missing {missing}.")

    reasoning_effort = str(
        req.reasoning_effort
        or req.thinking_level
        or os.getenv("HF_REASONING_EFFORT", "")
        or os.getenv("HF_THINKING_LEVEL", "minimal")
    ).strip().lower()
    if reasoning_effort == "default":
        reasoning_effort = "medium"

    model = str(req.model or "").strip()
    if provider == "openai" and not model:
        raise HTTPException(status_code=400, detail="OpenAI provider requires a non-empty model.")

    engine, pipeline = _build_runtime()
    try:
        if provider == "gemini":
            client = GeminiClient(
                api_key=api_key,
                model=model or "gemini-3-flash-preview",
                base_url=(
                    str(req.base_url or "").strip()
                    or str(os.getenv("HF_GEMINI_BASE_URL", "")).strip()
                    or str(os.getenv("GEMINI_BASE_URL", "")).strip()
                ),
                thinking_level=reasoning_effort,
            )
        else:
            client = OpenAIChatClient(
                api_key=api_key,
                model=model,
                base_url=(
                    str(req.base_url or "").strip()
                    or str(os.getenv("HF_OPENAI_BASE_URL", "")).strip()
                    or str(os.getenv("OPENAI_BASE_URL", "")).strip()
                    or "https://api.openai.com/v1"
                ),
                reasoning_effort=reasoning_effort,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    bridge = LLMAgentBridge(client)
    opening_text = OPENING_FIXED_TEXT

    recent_turns = [
        "User: 开始游戏",
        f"System: {opening_text}",
    ]

    last_system_text = recent_turns[1].replace("System: ", "", 1)
    session_id = str(uuid.uuid4())
    debug_log_file = LOG_DIR / f"{session_id}.jsonl"
    prompt_log_file = LOG_DIR / f"{session_id}.prompts.txt"
    _init_prompt_text_log(str(prompt_log_file), session_id)
    
    sessions[session_id] = {
        "engine": engine,
        "pipeline": pipeline,
        "client": client,
        "bridge": bridge,
        "recent_turns": recent_turns,
        "last_system_text": last_system_text,
        "pending_failed_commands": [],
        "llm_logs": [],
        "debug_log_file": str(debug_log_file),
        "prompt_log_file": str(prompt_log_file),
        "prompt_round_index": 0,
        "first_round_fixed": True,
    }
    
    return InitResponse(
        session_id=session_id,
        message=last_system_text,
        state=_get_player_state(engine)
    )

@app.post("/api/action")
async def take_action(req: ActionRequest):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    session = sessions[req.session_id]
    engine: GameEngine = session["engine"]
    pipeline: CommandPipeline = session["pipeline"]
    bridge: LLMAgentBridge = session["bridge"]
    recent_turns: list[str] = session["recent_turns"]
    
    if engine.game_over:
        raise HTTPException(status_code=400, detail="Game is already over.")

    raw_input = req.action_text.strip()
    if len(raw_input) > 15:
        raise HTTPException(status_code=400, detail="Input exceeds 15 characters limit.")
    req_resume_hint = str(req.resume_hint or "").strip()
    is_retry_turn = bool(req.is_retry) or bool(req_resume_hint)

    # First round must stay deterministic: no LLM call on "start game" action.
    if bool(session.get("first_round_fixed", False)) and raw_input in {"开始", "开始游戏", "start", "Start"}:
        session["first_round_fixed"] = False
        fixed_text = str(session.get("last_system_text", "")).strip()
        state = _get_player_state(engine)
        _append_prompt_text_log(
            session=session,
            action=raw_input,
            prompt_text="[NO_LLM_PROMPT] first round is fixed text; model not called.",
            time_value=float(engine.global_config.current_time_unit),
        )
        _append_session_debug_log(
            session=session,
            payload={
                "type": "first_round_fixed",
                "time": float(engine.global_config.current_time_unit),
                "action": raw_input,
                "model_called": False,
                "text": fixed_text,
                "state": state,
            },
        )

        def fixed_first_round():
            yield json.dumps(
                {
                    "type": "final",
                    "state": state,
                    "text": fixed_text,
                    "interrupted": False,
                    "errors": [],
                }
            ) + "\n"

        return StreamingResponse(fixed_first_round(), media_type="application/x-ndjson")

    resolved_action_text = raw_input
    backend_step_notes: list[str] = []
    if not is_retry_turn:
        backend_step_notes = _apply_pending_retries(session, pipeline)
    else:
        backend_step_notes.append("重试模式：冻结本轮位置/时间更新，避免重复结算。")
    recent_turns_for_model = list(recent_turns)
    allow_narrative_time_advance = not is_retry_turn
    block_main_player_move = True
    freeze_time_position_updates = is_retry_turn
    auto_move_state: dict[str, Any] | None = None
    if not is_retry_turn:
        auto_move = _try_auto_apply_main_move(
            engine=engine,
            pipeline=pipeline,
            action_text=resolved_action_text,
            recent_user_turns=recent_turns_for_model,
        )
        if auto_move is not None:
            allow_narrative_time_advance = False
            backend_step_notes.append(
                "主控玩家已由后端自动执行相邻移动："
                f"{auto_move['from_node']} -> {auto_move['to_node']}，"
                f"并已自动推进 time.advance={float(auto_move['time_advanced']):g}。"
            )
            auto_move_state = _get_player_state(engine)

    recovery_tails: list[str] = []
    pending_recovery = session.pop("pending_recovery", None)
    if isinstance(pending_recovery, dict):
        tail = str(pending_recovery.get("tail", "")).strip()
        if tail:
            recovery_tails.append(tail)
    if req_resume_hint:
        recovery_tails.append(req_resume_hint)
    if recovery_tails:
        merged_tail = " / ".join(x for x in recovery_tails if x)
        recovery_note = (
            "系统内部衔接提示：上轮叙事流中断。"
            "请先自然补完上轮未说完的剧情，再响应本轮玩家输入。"
            "不要提及网络、报错、系统或中断。"
        )
        if merged_tail:
            recovery_note += f" 上轮末尾片段：{merged_tail}"
        recent_turns_for_model.append(f"System: {recovery_note}")

    def event_generator():
        final_packet = None
        streamed_text_parts: list[str] = []
        prompt_logged = False
        if auto_move_state is not None:
            yield json.dumps({"type": "state", "state": auto_move_state}) + "\n"
        # bridge.run_step_stream is a synchronous generator holding network calls.
        # Removing async def allows Starlette to safely offload to threadpool and push stream immediately.
        try:
            for event in bridge.run_step_stream(
                pipeline=pipeline,
                recent_user_turns=recent_turns_for_model,
                current_user_input=resolved_action_text,
                apply_commands=True,
                backend_step_notes=backend_step_notes,
                allow_narrative_time_advance=allow_narrative_time_advance,
                block_main_player_move=block_main_player_move,
                freeze_time_position_updates=freeze_time_position_updates,
            ):
                if event["type"] == "narrative_chunk":
                    text = str(event.get("text", ""))
                    if text:
                        streamed_text_parts.append(text)
                    yield json.dumps({"type": "chunk", "text": text}) + "\n"
                elif event["type"] == "thinking":
                    yield json.dumps(
                        {
                            "type": "thinking",
                            "status": str(event.get("status", "tick")),
                            "tick": int(event.get("tick", 0)),
                        }
                    ) + "\n"
                elif event["type"] == "prompt":
                    prompt_text = str(event.get("narrative_prompt", ""))
                    if prompt_text and (not prompt_logged):
                        _append_prompt_text_log(
                            session=session,
                            action=resolved_action_text,
                            prompt_text=prompt_text,
                            time_value=float(engine.global_config.current_time_unit),
                        )
                        prompt_logged = True
                elif event["type"] == "final":
                    # Push latest state immediately once model commands are applied,
                    # so frontend panel updates without waiting for final text handling.
                    live_state = _get_player_state(engine)
                    yield json.dumps({"type": "state", "state": live_state}) + "\n"
                    final_packet = event
        except Exception as exc:
            if not prompt_logged:
                _append_prompt_text_log(
                    session=session,
                    action=resolved_action_text,
                    prompt_text=f"[NO_PROMPT_CAPTURED] stream exception before prompt logged: {exc}",
                    time_value=float(engine.global_config.current_time_unit),
                )
            partial_text = "".join(streamed_text_parts).strip()
            session["pending_recovery"] = {
                "tail": partial_text,
                "error": str(exc),
            }
            llm_logs = list(session.get("llm_logs", []) or [])
            llm_logs.append(
                {
                    "time": float(engine.global_config.current_time_unit),
                    "action": resolved_action_text,
                    "status": "interrupted",
                    "error": str(exc),
                    "stream_tail": partial_text,
                }
            )
            session["llm_logs"] = llm_logs[-80:]
            _append_session_debug_log(
                session=session,
                payload={
                    "type": "round_stream_exception",
                    "time": float(engine.global_config.current_time_unit),
                    "action": resolved_action_text,
                    "resume_hint": req_resume_hint,
                    "recent_turns_for_model": list(recent_turns_for_model),
                    "backend_step_notes": list(backend_step_notes),
                    "stream_tail": partial_text,
                    "error": str(exc),
                    "state": _get_player_state(engine),
                },
            )
            state = _get_player_state(engine)
            yield json.dumps(
                {
                    "type": "final",
                    "state": state,
                    "interrupted": True,
                    "text": partial_text,
                }
            ) + "\n"
            return
        
        # Stream the final state
        try:
            if final_packet is None:
                if not prompt_logged:
                    _append_prompt_text_log(
                        session=session,
                        action=resolved_action_text,
                        prompt_text="[NO_PROMPT_CAPTURED] final packet missing.",
                        time_value=float(engine.global_config.current_time_unit),
                    )
                state = _get_player_state(engine)
                _append_session_debug_log(
                    session=session,
                    payload={
                        "type": "round_missing_final_packet",
                        "time": float(engine.global_config.current_time_unit),
                        "action": resolved_action_text,
                        "resume_hint": req_resume_hint,
                        "recent_turns_for_model": list(recent_turns_for_model),
                        "backend_step_notes": list(backend_step_notes),
                        "state": state,
                    },
                )
                yield json.dumps(
                    {
                        "type": "final",
                        "state": state,
                        "text": "",
                        "interrupted": True,
                        "errors": ["missing final packet"],
                    }
                ) + "\n"
                return

            system_text = str(final_packet.get("main_text", "")).strip()
            errors = [str(x) for x in (final_packet.get("errors") or []) if str(x).strip()]
            retryable = _extract_retryable_commands(errors)
            if retryable:
                existing = list(session.get("pending_failed_commands", []) or [])
                merged: list[str] = []
                seen: set[str] = set()
                for line in [*existing, *retryable]:
                    if line in seen:
                        continue
                    seen.add(line)
                    merged.append(line)
                session["pending_failed_commands"] = merged[-30:]

            state = _get_player_state(engine)
            interrupted = bool(final_packet.get("interrupted", False))
            round_failed = interrupted or (not system_text)
            if not round_failed:
                session["recent_turns"] = [
                    *recent_turns[-6:],
                    f"User: {resolved_action_text}",
                    f"System: {system_text}",
                ]
                session["last_system_text"] = system_text

            llm_logs = list(session.get("llm_logs", []) or [])
            llm_logs.append(
                {
                    "time": float(engine.global_config.current_time_unit),
                    "action": resolved_action_text,
                    "status": "ok" if not round_failed else "interrupted",
                    "narrative_prompt": str(final_packet.get("narrative_prompt", "")),
                    "enemy_prompt": str(final_packet.get("enemy_prompt", "")),
                    "main_output": str(final_packet.get("main_text", "")),
                    "enemy_init_output": str(final_packet.get("enemy_init_text", "")),
                    "enemy_output": str(final_packet.get("enemy_text", "")),
                    "enemy_post_output": str(final_packet.get("enemy_post_text", "")),
                    "errors": errors,
                    "applied_commands": list(final_packet.get("applied_commands", []) or []),
                }
            )
            session["llm_logs"] = llm_logs[-80:]
            _append_session_debug_log(
                session=session,
                payload={
                    "type": "round_final",
                    "time": float(engine.global_config.current_time_unit),
                    "action": resolved_action_text,
                    "resume_hint": req_resume_hint,
                    "round_failed": bool(round_failed),
                    "recent_turns_for_model": list(recent_turns_for_model),
                    "backend_step_notes": list(backend_step_notes),
                    "narrative_prompt": str(final_packet.get("narrative_prompt", "")),
                    "model_output": str(final_packet.get("main_text", "")),
                    "narrative_commands": list(final_packet.get("narrative_commands", []) or []),
                    "applied_commands": list(final_packet.get("applied_commands", []) or []),
                    "errors": list(errors),
                    "model_context": final_packet.get("step_context", {}),
                    "final_packet_meta": {
                        "type": str(final_packet.get("type", "")),
                        "interrupted": bool(final_packet.get("interrupted", False)),
                        "error_count": len(list(errors)),
                    },
                    "state": state,
                },
            )

            yield json.dumps(
                {
                    "type": "final",
                    "state": state,
                    "text": system_text,
                    "interrupted": round_failed,
                    "errors": errors,
                }
            ) + "\n"
        except Exception as exc:
            state = _get_player_state(engine)
            yield json.dumps(
                {
                    "type": "final",
                    "state": state,
                    "text": "".join(streamed_text_parts).strip(),
                    "interrupted": True,
                    "errors": [f"finalize failed: {exc}"],
                }
            ) + "\n"
            
    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@app.get("/api/logs/{session_id}")
def get_logs(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    session = sessions[session_id]
    engine: GameEngine = session["engine"]
    pipeline: CommandPipeline = session["pipeline"]
    debug_log_file = str(session.get("debug_log_file", "")).strip()
    prompt_log_file = str(session.get("prompt_log_file", "")).strip()
    
    roles_state = []
    for name, role in engine.campus_map.roles.items():
        r = engine.get_role(name)
        move_state = r.query_movement_status() or {}
        roles_state.append({
            "name": name,
            "location": r.current_location,
            "health": r.health,
            "is_moving": bool(move_state.get("is_moving", False)),
            "target": r.battle_target
        })
        
    return {
        "roles": roles_state,
        "pipeline_logs": pipeline.get_recent_logs(80),
        "llm_logs": list(session.get("llm_logs", []) or []),
        "pending_failed_commands": list(session.get("pending_failed_commands", []) or []),
        "debug_log_file": debug_log_file,
        "prompt_log_file": prompt_log_file,
        "debug_log_entries": _read_debug_log_all(debug_log_file),
    }


@app.get("/api/state/{session_id}")
def get_state(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    session = sessions[session_id]
    engine: GameEngine = session["engine"]
    return {"state": _get_player_state(engine)}


@app.get("/api/prompt-log/{session_id}")
def get_prompt_log(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    session = sessions[session_id]
    prompt_log_file = str(session.get("prompt_log_file", "")).strip()
    return {
        "prompt_log_file": prompt_log_file,
        "content": _read_prompt_log_text(prompt_log_file),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)

