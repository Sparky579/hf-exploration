from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend import CommandPipeline, GameEngine, GlobalConfig, PlayerRole, Role, build_default_campus_map
from backend.gemini_client import GeminiClient
from backend.llm_agent_bridge import LLMAgentBridge
import backend.scripts.play_game_cli as cli  # reuse cli helpers

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

class InitResponse(BaseModel):
    session_id: str
    message: str
    state: dict[str, Any]

class ActionRequest(BaseModel):
    session_id: str
    action_text: str

class StartRequest(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = "gemini-3-flash-preview"


def _build_runtime() -> tuple[GameEngine, CommandPipeline]:
    campus = build_default_campus_map()
    cfg = GlobalConfig()
    engine = GameEngine(campus, cfg)

    main_player = PlayerRole("主控玩家", campus, cfg, "东教学楼内部")
    engine.register_player(main_player)
    engine.set_main_player("主控玩家")

    Role("李再斌", campus, cfg, "宿舍")
    Role("黎诺存", campus, cfg, "西教学楼南")
    Role("颜宏帆", campus, cfg, "东教学楼内部")

    for name, profile in engine.character_profiles.items():
        if "敌对" not in str(profile.alignment):
            continue
        if name not in campus.roles:
            continue
        engine.promote_role_to_player(name, card_deck=list(profile.card_deck), card_valid=4)

    pipeline = CommandPipeline(engine)
    pipeline.compile_line("[global.main_player=主控玩家]")
    return engine, pipeline

def _get_player_state(engine: GameEngine) -> dict[str, Any]:
    main = engine.get_player(engine.main_player_name or "主控玩家")
    role = engine.get_role(engine.main_player_name or "主控玩家")
    
    current_node = engine.campus_map.get_node(role.current_location)
    neighbors = sorted([
        name for name in current_node.neighbors
        if engine.campus_map.get_node(name).valid
    ])
    
    companions = engine.global_config.list_team_companions()
    
    return {
        "time": engine.global_config.current_time_unit,
        "location": role.current_location,
        "hp": role.health,
        "holy_water": main.holy_water,
        "card_deck": list(main.card_deck),
        "neighbors": neighbors,
        "companions": companions,
        "game_over": engine.game_over,
        "game_result": engine.game_result
    }


@app.post("/api/start", response_model=InitResponse)
def start_game(req: StartRequest):
    api_key = (req.api_key or os.getenv("GOOGLE_API_KEY", "")).strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing Gemini API key.")
        
    engine, pipeline = _build_runtime()
    client = GeminiClient(api_key=api_key, model=req.model)
    bridge = LLMAgentBridge(client)
    
    recent_turns = [
        "User: 开始游戏",
        "System: 你是向西中学的一名普通学生。最近，一款名为《皇室战争》的游戏在班级里掀起了狂热的风暴，即便是最严厉的课堂，也有人甘冒被抓的风险在课桌下偷偷沉迷于此，也包括你和你的好朋友罗宾，陈洛和马超鹏。\n枯燥的数学课上，老师正在讲解着复数的定义。这正如催眠曲般回荡。你埋下头偷偷按亮手机，一条爆炸性的消息突然跃入眼帘，好消息：《皇室战争：超现实大更新》！\n\"超现实？\"你盯着屏幕微微发愣，\"这是什么意思？以前怎么从来没听说过这个版本？\"\n尽管心中充满疑惑，但对新版本的好奇心犹如猫挠。你激动得掌心微汗，必须立刻决断，请选择：\n1. 流量更新\n2. 借马超鹏热点更新\n3. 不更新，先认真听数学课",
    ]
    
    last_system_text = recent_turns[1].replace("System: ", "", 1)
    session_id = str(uuid.uuid4())
    
    sessions[session_id] = {
        "engine": engine,
        "pipeline": pipeline,
        "client": client,
        "bridge": bridge,
        "recent_turns": recent_turns,
        "last_system_text": last_system_text,
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
    last_system_text: str = session["last_system_text"]
    
    if engine.game_over:
        raise HTTPException(status_code=400, detail="Game is already over.")

    raw_input = req.action_text.strip()
    if len(raw_input) > 15:
        raise HTTPException(status_code=400, detail="Input exceeds 15 characters limit.")

    resolved_action_text = cli._resolve_user_action_text(raw_input, last_system_text)
    backend_step_notes: list[str] = []
    
    cli._apply_opening_choice_markers(engine, pipeline, resolved_action_text)
    
    allow_narrative_time_advance = True
    block_main_player_move = False
    auto_move = cli._try_auto_apply_main_move(engine, pipeline, resolved_action_text)
    
    if auto_move is not None:
        allow_narrative_time_advance = False
        block_main_player_move = True
        backend_step_notes.append(
            "主控玩家已由后台自动执行相邻移动："
            f"{auto_move['from_node']} -> {auto_move['to_node']}，"
            f"并已自动推进 time.advance={float(auto_move['time_advanced']):g}。"
        )

    async def event_generator():
        final_packet = None
        # bridge.run_step_stream is a synchronous generator holding network calls.
        # We wrap it in a thread to keep the async loop smooth, although yielding blockingly is OK since it's just a demo.
        for event in bridge.run_step_stream(
            pipeline=pipeline,
            recent_user_turns=recent_turns,
            current_user_input=resolved_action_text,
            apply_commands=True,
            backend_step_notes=backend_step_notes,
            allow_narrative_time_advance=allow_narrative_time_advance,
            block_main_player_move=block_main_player_move,
        ):
            if event["type"] == "narrative_chunk":
                yield json.dumps({"type": "chunk", "text": event["text"]}) + "\\n"
            elif event["type"] == "final":
                final_packet = event
        
        # Stream the final state
        if final_packet is not None:
            system_text = str(final_packet.get("main_text", "")).strip()
            session["recent_turns"] = [*recent_turns[-4:], f"User: {resolved_action_text}", f"System: {system_text}"]
            session["last_system_text"] = system_text
            
            yield json.dumps({
                "type": "final",
                "state": _get_player_state(engine)
            }) + "\\n"
            
    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@app.get("/api/logs/{session_id}")
def get_logs(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    session = sessions[session_id]
    engine: GameEngine = session["engine"]
    pipeline: CommandPipeline = session["pipeline"]
    
    roles_state = []
    for name, role in engine.campus_map.roles.items():
        r = engine.get_role(name)
        roles_state.append({
            "name": name,
            "location": r.current_location,
            "health": r.health,
            "is_moving": r.query_movement_status() is not None,
            "target": r.battle_target
        })
        
    return {
        "roles": roles_state,
        "pipeline_logs": pipeline.get_recent_logs(50)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
