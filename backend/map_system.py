"""
Module purpose:
- Compatibility facade for existing imports.

Usage:
- Import all game primitives from this module if caller expects the old single-file layout.

Re-exported items:
- Constants: MOVE_TIME_COST, BASE_HOLY_WATER_PER_TIME, PHASE_EMERGENCY, PHASE_BATTLE.
- Config: GlobalConfig.
- Map: MapNode, CampusMap, build_default_campus_map.
- Units: UnitClass, AttackPreference, TargetKind, UnitCard, DeployedUnit, build_default_unit_cards.
- Roles: Role, PlayerRole.
- Engine: MovementTask, GameEngine.
"""

from .constants import BASE_HOLY_WATER_PER_TIME, MOVE_TIME_COST, PHASE_BATTLE, PHASE_EMERGENCY
from .engine import GameEngine, MovementTask
from .global_config import GlobalConfig
from .map_core import CampusMap, MapNode, build_default_campus_map
from .roles import PlayerRole, Role
from .units import AttackPreference, DeployedUnit, TargetKind, UnitCard, UnitClass, build_default_unit_cards

__all__ = [
    "AttackPreference",
    "BASE_HOLY_WATER_PER_TIME",
    "CampusMap",
    "DeployedUnit",
    "GameEngine",
    "GlobalConfig",
    "MapNode",
    "MOVE_TIME_COST",
    "MovementTask",
    "PHASE_BATTLE",
    "PHASE_EMERGENCY",
    "PlayerRole",
    "Role",
    "TargetKind",
    "UnitCard",
    "UnitClass",
    "build_default_campus_map",
    "build_default_unit_cards",
]
