"""
Module purpose:
- Compatibility facade for callers that import from a single module.

Re-exported groups:
- Constants: MOVE_TIME_COST, BASE_HOLY_WATER_PER_TIME, PHASE_EMERGENCY, PHASE_BATTLE.
- Config: GlobalConfig.
- Map: MapNode, CampusMap, build_default_campus_map.
- Units: UnitClass, AttackPreference, TargetKind, NearbyUnitStatus, UnitCard, DeployedUnit, build_default_unit_cards.
- Roles: Role, PlayerRole.
- Engine: MovementTask, GameEngine.
- Pipeline: QueueMessage, CommandPipeline.
- Character Profiles: CharacterProfile, CharacterStatus, build_default_character_profiles.
- Companion Profiles: CompanionProfile, CompanionRoleType, build_default_companion_profiles.
- Story: GlobalStorySetting, build_default_story_setting.
- Event Checker: GlobalEventChecker, TriggerState.
- LLM/Prompt: GeminiClient, LLMAgentBridge, build_narrative_prompt,
  build_enemy_initial_trigger_prompt, build_enemy_trigger_prompt.
- Snapshot/Narrative assets: build_step_context, build_world_base_setting, get_scene_paragraph.
"""

from .character_profiles import CharacterProfile, CharacterStatus, build_default_character_profiles
from .companion_profiles import CompanionProfile, CompanionRoleType, build_default_companion_profiles
from .command_pipeline import CommandPipeline, QueueMessage
from .constants import BASE_HOLY_WATER_PER_TIME, MOVE_TIME_COST, PHASE_BATTLE, PHASE_EMERGENCY
from .engine import GameEngine, MovementTask
from .gemini_client import GeminiClient
from .global_config import GlobalConfig
from .global_event_checker import GlobalEventChecker, TriggerState
from .llm_agent_bridge import LLMAgentBridge
from .llm_prompting import (
    build_enemy_initial_trigger_prompt,
    build_enemy_trigger_prompt,
    build_narrative_prompt,
)
from .map_core import CampusMap, MapNode, build_default_campus_map
from .narrative_assets import build_world_base_setting, get_scene_paragraph
from .roles import PlayerRole, Role
from .state_snapshot import build_step_context
from .story_settings import GlobalStorySetting, build_default_story_setting
from .units import (
    AttackPreference,
    DeployedUnit,
    NearbyUnitStatus,
    TargetKind,
    UnitCard,
    UnitClass,
    build_all_unit_cards,
    build_default_unit_cards,
)

__all__ = [
    "AttackPreference",
    "BASE_HOLY_WATER_PER_TIME",
    "CampusMap",
    "CharacterProfile",
    "CharacterStatus",
    "CompanionProfile",
    "CompanionRoleType",
    "CommandPipeline",
    "DeployedUnit",
    "GameEngine",
    "GlobalEventChecker",
    "GlobalConfig",
    "GlobalStorySetting",
    "GeminiClient",
    "LLMAgentBridge",
    "MapNode",
    "MOVE_TIME_COST",
    "MovementTask",
    "NearbyUnitStatus",
    "PHASE_BATTLE",
    "PHASE_EMERGENCY",
    "PlayerRole",
    "QueueMessage",
    "Role",
    "build_enemy_initial_trigger_prompt",
    "build_enemy_trigger_prompt",
    "build_narrative_prompt",
    "build_step_context",
    "build_world_base_setting",
    "TriggerState",
    "TargetKind",
    "UnitCard",
    "UnitClass",
    "build_all_unit_cards",
    "build_default_campus_map",
    "build_default_companion_profiles",
    "build_default_character_profiles",
    "build_default_story_setting",
    "build_default_unit_cards",
    "get_scene_paragraph",
]
