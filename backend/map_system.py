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
"""

from .command_pipeline import CommandPipeline, QueueMessage
from .constants import BASE_HOLY_WATER_PER_TIME, MOVE_TIME_COST, PHASE_BATTLE, PHASE_EMERGENCY
from .engine import GameEngine, MovementTask
from .global_config import GlobalConfig
from .map_core import CampusMap, MapNode, build_default_campus_map
from .roles import PlayerRole, Role
from .units import (
    AttackPreference,
    DeployedUnit,
    NearbyUnitStatus,
    TargetKind,
    UnitCard,
    UnitClass,
    build_default_unit_cards,
)

__all__ = [
    "AttackPreference",
    "BASE_HOLY_WATER_PER_TIME",
    "CampusMap",
    "CommandPipeline",
    "DeployedUnit",
    "GameEngine",
    "GlobalConfig",
    "MapNode",
    "MOVE_TIME_COST",
    "MovementTask",
    "NearbyUnitStatus",
    "PHASE_BATTLE",
    "PHASE_EMERGENCY",
    "PlayerRole",
    "QueueMessage",
    "Role",
    "TargetKind",
    "UnitCard",
    "UnitClass",
    "build_default_campus_map",
    "build_default_unit_cards",
]
