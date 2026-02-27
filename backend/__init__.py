"""
Module purpose:
- Public package entrypoint for backend game systems.

This file re-exports symbols from `map_system` so callers can use:
- from backend import GameEngine, CommandPipeline, PlayerRole, GlobalConfig, ...
"""

from .map_system import (
    BASE_HOLY_WATER_PER_TIME,
    MOVE_TIME_COST,
    PHASE_BATTLE,
    PHASE_EMERGENCY,
    AttackPreference,
    CampusMap,
    CommandPipeline,
    DeployedUnit,
    GameEngine,
    GlobalConfig,
    MapNode,
    MovementTask,
    NearbyUnitStatus,
    PlayerRole,
    QueueMessage,
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
