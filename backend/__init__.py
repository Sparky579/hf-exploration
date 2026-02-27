"""
Module purpose:
- Public package entrypoint for backend game systems.

This file re-exports symbols from `map_system` so callers can use:
- from backend import GameEngine, PlayerRole, GlobalConfig, build_default_campus_map, ...

No runtime logic is implemented here.
"""

from .map_system import (
    BASE_HOLY_WATER_PER_TIME,
    MOVE_TIME_COST,
    PHASE_BATTLE,
    PHASE_EMERGENCY,
    AttackPreference,
    CampusMap,
    DeployedUnit,
    GameEngine,
    GlobalConfig,
    MapNode,
    MovementTask,
    PlayerRole,
    Role,
    TargetKind,
    UnitCard,
    UnitClass,
    build_default_campus_map,
    build_default_unit_cards,
)

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
