"""
Module purpose:
- Provide a single game-time driver for movement, regen, trigger checks, game-over checks, and companion flow.

Data classes:
- MovementTask: one queued movement command with remaining travel time.

Class:
- GameEngine
  - register_player/set_main_player: main-player registration and selection.
  - issue_move/advance_time: movement and world tick APIs.
  - set_emergency_phase/set_battle_phase/set_battle_state: global phase state writes.
  - set_node_valid/attempt_escape: map state and story escape handling.
  - role/player state write APIs.
  - character profile APIs.
  - companion APIs: discover/invite/remove/team/affection/noticer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .character_profiles import CharacterProfile, build_default_character_profiles
from .companion_profiles import CompanionProfile, build_default_companion_profiles
from .constants import MOVE_TIME_COST, PHASE_EMERGENCY
from .global_config import GlobalConfig
from .global_event_checker import GlobalEventChecker
from .map_core import CampusMap
from .roles import PlayerRole, Role
from .story_settings import GlobalStorySetting, build_default_story_setting


@dataclass
class MovementTask:
    role_name: str
    from_node: str
    to_node: str
    remaining_time: float = MOVE_TIME_COST


class GameEngine:
    """Unified time source for world updates and story/companion checks."""

    def __init__(
        self,
        campus_map: CampusMap,
        global_config: GlobalConfig,
        story_setting: GlobalStorySetting | None = None,
    ) -> None:
        self.campus_map = campus_map
        self.global_config = global_config
        self.players: dict[str, PlayerRole] = {}
        self._movement_tasks: dict[str, MovementTask] = {}
        self.character_profiles: dict[str, CharacterProfile] = build_default_character_profiles()
        self.companion_profiles: dict[str, CompanionProfile] = build_default_companion_profiles()
        self.global_config.init_companion_registry(self.companion_profiles)

        self.story_setting = story_setting or build_default_story_setting()
        self.event_checker = GlobalEventChecker(self, self.story_setting)

        self.main_player_name: str | None = None
        self.game_over: bool = False
        self.game_result: str | None = None

    def register_player(self, player: PlayerRole) -> None:
        if player.name in self.players:
            raise ValueError(f"player already registered: {player.name}")
        self.players[player.name] = player
        if self.main_player_name is None:
            self.main_player_name = player.name

    def set_main_player(self, player_name: str) -> None:
        self.get_player(player_name)
        self.main_player_name = player_name

    def get_role(self, role_name: str) -> Role:
        if role_name not in self.campus_map.roles:
            raise KeyError(f"role not found: {role_name}")
        return self.campus_map.roles[role_name]

    def get_player(self, player_name: str) -> PlayerRole:
        if player_name not in self.players:
            raise KeyError(f"player not registered: {player_name}")
        return self.players[player_name]

    def get_character_profile(self, name: str) -> CharacterProfile:
        if name not in self.character_profiles:
            raise KeyError(f"character profile not found: {name}")
        return self.character_profiles[name]

    def get_companion_profile(self, name: str) -> CompanionProfile:
        if name not in self.companion_profiles:
            raise KeyError(f"companion profile not found: {name}")
        return self.companion_profiles[name]

    def issue_move(self, role_name: str, target_node_name: str) -> MovementTask:
        role = self.get_role(role_name)
        if role_name in self._movement_tasks:
            raise ValueError(f"role is already moving: {role_name}")

        target_node = self.campus_map.get_node(target_node_name)
        if not target_node.valid:
            raise ValueError(f"cannot move to destroyed node: {target_node_name}")

        current_node_name = role.current_location
        current_node = self.campus_map.get_node(current_node_name)
        if target_node_name not in current_node.neighbors:
            raise ValueError(
                f"cannot move from '{current_node_name}' to '{target_node_name}': not adjacent"
            )

        move_cost = self._get_move_cost_for_role(role_name)
        task = MovementTask(
            role_name=role_name,
            from_node=current_node_name,
            to_node=target_node_name,
            remaining_time=move_cost,
        )
        self._movement_tasks[role_name] = task
        role._start_move(target_node_name)
        return task

    def advance_time(self, amount: float) -> float:
        if amount < 0:
            raise ValueError("amount must be >= 0.")
        if amount == 0:
            return self.global_config.current_time_unit

        self.global_config.advance_time(amount)
        self._progress_movements(amount)
        self._regenerate_players(amount)
        self._tick_romance_affection(amount)
        self._run_companion_auto_checks()
        self.event_checker.check_time_triggers()
        self._check_main_player_game_over()
        return self.global_config.current_time_unit

    def set_emergency_phase(self, enabled: bool) -> None:
        self.global_config.set_state(PHASE_EMERGENCY, enabled)

    def set_battle_phase(self, enabled: bool) -> None:
        self.set_battle_state("__BATTLE__" if enabled else None)

    def set_battle_state(self, target: str | None) -> None:
        was_battle = self.global_config.is_battle_phase
        self.global_config.set_battle_state(target)
        if was_battle and not self.global_config.is_battle_phase:
            for player in self.players.values():
                player.clear_wartime_units()

    def add_global_dynamic_state(self, text: str) -> None:
        self.global_config.add_dynamic_state(text)

    def add_role_dynamic_state(self, role_name: str, text: str) -> None:
        role = self.get_role(role_name)
        role.add_dynamic_state(text)

    def set_node_valid(self, node_name: str, valid: bool) -> None:
        self.campus_map.set_node_valid(node_name, valid)

    def attempt_escape(self, role_name: str, node_name: str) -> None:
        self.event_checker.attempt_escape(role_name, node_name)

    def set_role_location(self, role_name: str, node_name: str) -> None:
        role = self.get_role(role_name)
        target_node = self.campus_map.get_node(node_name)
        if not target_node.valid:
            raise ValueError(f"cannot set location to destroyed node: {node_name}")
        old_node = role.current_location
        if role_name in self._movement_tasks:
            del self._movement_tasks[role_name]
            role._finish_move(old_node)
        self.campus_map.transfer_role(role_name, old_node, node_name)
        role._finish_move(node_name)
        self._run_companion_auto_checks()

    def set_role_health(self, role_name: str, value: float) -> None:
        role = self.get_role(role_name)
        role.set_health(value)
        self._check_main_player_game_over()

    def set_role_battle_target(self, role_name: str, target: str | None) -> None:
        role = self.get_role(role_name)
        role.set_battle_target(target)

    def set_player_holy_water(self, player_name: str, value: float) -> None:
        player = self.get_player(player_name)
        if value < 0:
            raise ValueError("holy_water must be >= 0.")
        player.holy_water = float(value)

    def set_character_status(self, name: str, status: str) -> None:
        self.get_character_profile(name).set_status(status)

    def add_character_history(self, name: str, text: str) -> None:
        self.get_character_profile(name).add_history(text)

    def remove_character_history(self, name: str, text: str) -> None:
        self.get_character_profile(name).remove_history(text)

    def set_character_deck(self, name: str, deck: list[str]) -> None:
        self.get_character_profile(name).set_card_deck(deck)

    def set_character_description(self, name: str, text: str) -> None:
        profile = self.get_character_profile(name)
        if not text.strip():
            raise ValueError("description must be non-empty.")
        profile.description = text

    def discover_companion(self, actor_role_name: str, companion_name: str) -> None:
        self.get_companion_profile(companion_name)
        if not self._can_discover_companion(actor_role_name, companion_name):
            raise ValueError(f"companion is not discoverable now: {companion_name}")
        self.global_config.set_companion_discovered(companion_name, True)
        self.global_config.add_dynamic_state(f"发现同伴：{companion_name}")

    def invite_companion(self, actor_role_name: str, companion_name: str) -> None:
        if self.main_player_name is not None and actor_role_name != self.main_player_name:
            raise ValueError("only main player can invite companion.")

        profile = self.get_companion_profile(companion_name)
        state = self.global_config.get_companion_state(companion_name)
        if not bool(state["discovered"]):
            raise ValueError(f"companion must be discovered first: {companion_name}")

        # Romance exclusivity: inviting a new romance companion makes existing romance companion leave.
        if profile.role_type == "romance":
            for name in self.global_config.list_team_companions():
                if name == companion_name:
                    continue
                if self.global_config.get_companion_state(name)["role_type"] == "romance":
                    self.global_config.set_companion_in_team(name, False)
                    self.global_config.add_dynamic_state(f"{name} 因你邀请其他可攻略角色而离开")

        self.global_config.set_companion_in_team(companion_name, True)
        self.add_role_dynamic_state(actor_role_name, f"队友+{companion_name}")

        # 马超鹏 joined: switch main player's battle deck to his phone deck.
        if companion_name == "马超鹏":
            main_player = self.get_player(actor_role_name)
            main_player.set_card_deck(profile.deck)
            self.global_config.add_dynamic_state("马超鹏加入，主角切换为手机战斗卡组")

    def remove_companion(self, companion_name: str) -> None:
        self.global_config.set_companion_in_team(companion_name, False)

    def set_companion_discovered(self, companion_name: str, enabled: bool) -> None:
        self.get_companion_profile(companion_name)
        self.global_config.set_companion_discovered(companion_name, enabled)

    def set_companion_in_team(self, companion_name: str, enabled: bool) -> None:
        self.get_companion_profile(companion_name)
        self.global_config.set_companion_in_team(companion_name, enabled)

    def set_companion_affection(self, companion_name: str, value: float) -> None:
        self.get_companion_profile(companion_name)
        self.global_config.set_companion_affection(companion_name, value)

    def add_companion_affection(self, companion_name: str, delta: float) -> None:
        self.get_companion_profile(companion_name)
        self.global_config.add_companion_affection(companion_name, delta)

    def set_team_companions(self, names: list[str]) -> None:
        for name in names:
            self.get_companion_profile(name)
        self.global_config.set_team_companions(names)

    def add_companion_noticer(self, companion_name: str, hostile_name: str) -> None:
        self.get_companion_profile(companion_name)
        self.global_config.add_companion_noticer(companion_name, hostile_name)
        if companion_name == "许琪琪":
            noticed_by = self.global_config.get_companion_state("许琪琪")["noticed_by"]
            if len(noticed_by) >= 2:
                self.global_config.add_dynamic_state("两名敌对角色因注意到许琪琪而吃醋愤怒")

    def remove_companion_noticer(self, companion_name: str, hostile_name: str) -> None:
        self.get_companion_profile(companion_name)
        self.global_config.remove_companion_noticer(companion_name, hostile_name)

    def set_companion_noticers(self, companion_name: str, hostiles: list[str]) -> None:
        self.get_companion_profile(companion_name)
        state = self.global_config.get_companion_state(companion_name)
        state["noticed_by"] = []
        for hostile in hostiles:
            self.global_config.add_companion_noticer(companion_name, hostile)
        if companion_name == "许琪琪" and len(state["noticed_by"]) >= 2:
            self.global_config.add_dynamic_state("两名敌对角色因注意到许琪琪而吃醋愤怒")

    def _get_move_cost_for_role(self, role_name: str) -> float:
        base = float(MOVE_TIME_COST)
        if self.main_player_name is None or role_name != self.main_player_name:
            return base
        return self.global_config.get_effective_main_move_cost(base)

    def _progress_movements(self, amount: float) -> None:
        completed: list[MovementTask] = []
        for task in self._movement_tasks.values():
            task.remaining_time -= amount
            if task.remaining_time <= 1e-9:
                completed.append(task)

        for task in completed:
            role = self.get_role(task.role_name)
            self.campus_map.transfer_role(task.role_name, task.from_node, task.to_node)
            role._finish_move(task.to_node)
            del self._movement_tasks[task.role_name]

    def _regenerate_players(self, amount: float) -> None:
        for player in self.players.values():
            player.regenerate_holy_water(amount)

    def _tick_romance_affection(self, amount: float) -> None:
        for name in self.global_config.list_team_companions():
            state = self.global_config.get_companion_state(name)
            if state["role_type"] == "romance":
                self.global_config.add_companion_affection(name, amount)

    def _run_companion_auto_checks(self) -> None:
        if self.main_player_name is None:
            return
        main_role = self.get_role(self.main_player_name)
        main_node = main_role.current_location
        now = self.global_config.current_time_unit

        # 罗宾：注意到玩家后主动提出加入（自动发现 + 动态提示）
        robin_state = self.global_config.get_companion_state("罗宾")
        if (not bool(robin_state["discovered"])) and main_node == "田径场":
            self.global_config.set_companion_discovered("罗宾", True)
            self.global_config.add_dynamic_state("罗宾注意到你并主动提出加入队伍")

        # 冬雨：在图书馆可发现
        dongyu_state = self.global_config.get_companion_state("冬雨")
        if (not bool(dongyu_state["discovered"])) and main_node == "图书馆":
            self.global_config.set_companion_discovered("冬雨", True)
            self.global_config.add_dynamic_state("你在图书馆发现了冬雨")

        # 许琪琪：仅在东教学楼内部往北侧路径且时间不在[6,9]可发现
        xu_state = self.global_config.get_companion_state("许琪琪")
        if not bool(xu_state["discovered"]):
            if main_node in ("东教学楼内部", "东教学楼北") and not (6 <= now <= 9):
                self.global_config.set_companion_discovered("许琪琪", True)
                self.global_config.add_dynamic_state("你在东教学楼北侧路径上发现了许琪琪")

        # 马超鹏：时间<4 且在东教学楼内部可发现
        ma_state = self.global_config.get_companion_state("马超鹏")
        if (not bool(ma_state["discovered"])) and now < 4 and main_node == "东教学楼内部":
            self.global_config.set_companion_discovered("马超鹏", True)
            self.global_config.add_dynamic_state("东教学楼事件触发：你发现了马超鹏")

    def _can_discover_companion(self, actor_role_name: str, companion_name: str) -> bool:
        role = self.get_role(actor_role_name)
        now = self.global_config.current_time_unit
        node = role.current_location

        if companion_name == "罗宾":
            return node == "田径场"
        if companion_name == "冬雨":
            return node == "图书馆"
        if companion_name == "许琪琪":
            return node in ("东教学楼内部", "东教学楼北") and not (6 <= now <= 9)
        if companion_name == "马超鹏":
            return now < 4 and node == "东教学楼内部"
        return False

    def _check_main_player_game_over(self) -> None:
        if self.main_player_name is None:
            return
        main_role = self.get_role(self.main_player_name)
        if main_role.health <= 0:
            self.game_over = True
            self.game_result = "main_player_dead"
