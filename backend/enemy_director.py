"""
Deterministic hostile-role runtime director.

This module drives hostile/neutral-script roles with fixed logic plans (no enemy-side LLM).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .constants import (
    DYNAMIC_LZB_DEZHENG_BANNED,
    DYNAMIC_LZB_DEZHENG_PENDING,
)

if TYPE_CHECKING:
    from .engine import GameEngine


MAIN_PLAYER_NAME = "主控玩家"

ROLE_YAN_HONGFAN = "颜宏帆"
ROLE_LI_NUOCUN = "黎诺存"
ROLE_LI_ZAIBIN = "李再斌"

NODE_DORM = "宿舍"
NODE_INTL = "国际部"
NODE_EAST_SOUTH = "东教学楼南"
NODE_WEST_SOUTH = "西教学楼南"
NODE_LIBRARY = "图书馆"
NODE_DEZHENG = "德政楼"

CARD_HOG_RIDER = "野猪骑士"
CARD_GOBLIN_GANG = "哥布林团伙"
CARD_INFERNO_TOWER = "地狱之塔"
CARD_PEKKA = "皮卡超人"
CARD_BATTLE_RAM = "野蛮人攻城锤"
CARD_BANDIT = "幻影刺客"

DEZHENG_BLUE_DEVICE_SEEN = "场景事件:德政楼蓝光装置已发现"
DEZHENG_BLUE_DEVICE_DESTROYED = "场景事件:德政楼蓝光装置已摧毁"

BUILDING_NODE_MAP: dict[str, list[str]] = {
    "东教学楼": ["东教学楼南", "东教学楼内部", "东教学楼北"],
    "西教学楼": ["西教学楼南", "西教学楼北"],
    "南教学楼": ["南教学楼"],
    "德政楼": ["德政楼"],
    "图书馆": ["图书馆"],
    "国际部": ["国际部"],
    "宿舍": ["宿舍"],
    "食堂": ["食堂"],
    "体育馆": ["体育馆"],
    "生化楼": ["生化楼"],
    "田径场": ["田径场"],
}


@dataclass(frozen=True)
class EnemyPlanStep:
    step_id: str
    delay: float
    action: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnemyPlan:
    plan_id: str
    steps: list[EnemyPlanStep]
    loop: bool = False


@dataclass
class EnemyRuntimeState:
    role_name: str
    plan_id: str
    step_index: int
    remaining_time: float
    paused_reason: str = ""
    completed: bool = False


@dataclass(frozen=True)
class StepExecResult:
    status: str  # ok | skip | retry
    reason: str = ""
    retry_after: float = 1.0


class EnemyDirector:
    """Advance fixed hostile-role plans with pause-aware counters."""

    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine
        self._plans: dict[str, EnemyPlan] = {}
        self._runtime: dict[str, EnemyRuntimeState] = {}

    def on_time_advanced(self, amount: float) -> None:
        if amount <= 0:
            return
        self._cleanup_pending_enemy_events()
        for role_name in self._iter_script_roles():
            self._ensure_runtime(role_name)
        for role_name in sorted(self._runtime.keys()):
            self._tick_role(role_name, float(amount))

    def on_role_status_changed(self, role_name: str) -> None:
        if str(role_name).strip() == ROLE_LI_ZAIBIN:
            self._cleanup_pending_enemy_events()

    def snapshot(self) -> dict[str, Any]:
        rows: dict[str, Any] = {}
        for role_name, state in self._runtime.items():
            plan = self._plans.get(role_name)
            next_step_id = ""
            if plan and (not state.completed) and 0 <= state.step_index < len(plan.steps):
                next_step_id = plan.steps[state.step_index].step_id
            rows[role_name] = {
                "plan_id": state.plan_id,
                "step_index": state.step_index,
                "next_step_id": next_step_id,
                "remaining_time": float(state.remaining_time),
                "paused_reason": state.paused_reason,
                "completed": bool(state.completed),
            }
        return rows

    def preview_planned_events_until(self, end_time: float) -> list[dict[str, Any]]:
        """
        Build virtual countdown hints for upcoming deterministic enemy steps.
        These rows are prompt-only hints and are NOT executable triggers.
        """
        now = float(self.engine.global_config.current_time_unit)
        horizon = float(end_time)
        if horizon <= now:
            return []
        for role_name in self._iter_script_roles():
            self._ensure_runtime(role_name)

        rows: list[dict[str, Any]] = []
        seq = 0
        for role_name in sorted(self._runtime.keys()):
            state = self._runtime.get(role_name)
            plan = self._plans.get(role_name)
            if state is None or plan is None:
                continue
            if state.completed or (not self._is_role_alive(role_name)):
                continue
            if self._pause_reason(role_name):
                # Enemy timeline countdown pauses only for that role.
                continue
            if not (0 <= state.step_index < len(plan.steps)):
                continue

            step_index = int(state.step_index)
            remaining = float(state.remaining_time)
            event_time = now
            while 0 <= step_index < len(plan.steps):
                step = plan.steps[step_index]
                event_time += max(remaining, 0.0)
                if event_time - horizon > 1e-9:
                    break
                seq += 1
                rows.extend(
                    self._preview_rows_for_step(
                        role_name=role_name,
                        step=step,
                        event_time=event_time,
                        end_time=horizon,
                        seed=seq,
                    )
                )
                step_index += 1
                if step_index >= len(plan.steps):
                    break
                remaining = float(plan.steps[step_index].delay)

        rows.sort(key=lambda x: (float(x.get("trigger_time", 0.0)), int(x.get("id", 0))))
        return rows

    def _iter_script_roles(self) -> list[str]:
        rows: list[str] = []
        scripted_order = [ROLE_YAN_HONGFAN, ROLE_LI_NUOCUN, ROLE_LI_ZAIBIN]
        for name in scripted_order:
            if name in self.engine.campus_map.roles:
                rows.append(name)
        for name, profile in self.engine.character_profiles.items():
            if name in rows:
                continue
            if "敌对" not in str(profile.alignment):
                continue
            if name not in self.engine.campus_map.roles:
                continue
            rows.append(name)
        return rows

    def _ensure_runtime(self, role_name: str) -> None:
        if role_name not in self._plans:
            plan = self._build_default_plan(role_name)
            self._plans[role_name] = plan
            if self._plan_requires_player(plan):
                self._ensure_player_role(role_name)
        if role_name in self._runtime:
            return
        plan = self._plans[role_name]
        first_delay = float(plan.steps[0].delay) if plan.steps else 0.0
        self._runtime[role_name] = EnemyRuntimeState(
            role_name=role_name,
            plan_id=plan.plan_id,
            step_index=0,
            remaining_time=max(first_delay, 0.0),
            paused_reason="",
            completed=(len(plan.steps) == 0),
        )

    @staticmethod
    def _plan_requires_player(plan: EnemyPlan) -> bool:
        for step in plan.steps:
            if step.action in {"deploy_forced", "relocate_and_deploy_forced", "deploy_and_alarm"}:
                return True
        return False

    def _ensure_player_role(self, role_name: str) -> None:
        if role_name in self.engine.players:
            return
        deck = None
        if role_name in self.engine.character_profiles:
            deck = list(self.engine.get_character_profile(role_name).card_deck)
        self.engine.promote_role_to_player(role_name, card_deck=deck, card_valid=4)

    def _tick_role(self, role_name: str, amount: float) -> None:
        state = self._runtime.get(role_name)
        if state is None or state.completed:
            return
        if not self._is_role_alive(role_name):
            state.completed = True
            state.paused_reason = "dead"
            return

        budget = float(amount)
        while budget > 1e-9 and (not state.completed):
            pause_reason = self._pause_reason(role_name)
            if pause_reason:
                state.paused_reason = pause_reason
                return
            state.paused_reason = ""
            if state.remaining_time > budget + 1e-9:
                state.remaining_time -= budget
                return
            budget -= max(state.remaining_time, 0.0)
            state.remaining_time = 0.0

            plan = self._plans.get(role_name)
            if plan is None or not plan.steps:
                state.completed = True
                state.paused_reason = "no_plan"
                return
            if state.step_index < 0 or state.step_index >= len(plan.steps):
                if plan.loop:
                    state.step_index = 0
                else:
                    state.completed = True
                    state.paused_reason = "completed"
                    return

            step = plan.steps[state.step_index]
            result = self._execute_step(role_name, step)
            if result.status == "retry":
                state.remaining_time = max(float(result.retry_after), 0.5)
                state.paused_reason = result.reason or "retry"
                return
            if result.reason:
                self._log(role_name, f"{step.step_id}: {result.status} ({result.reason})")

            state.step_index += 1
            if state.step_index >= len(plan.steps):
                if plan.loop and plan.steps:
                    state.step_index = 0
                else:
                    state.completed = True
                    state.paused_reason = "completed"
                    return
            next_step = plan.steps[state.step_index]
            state.remaining_time = max(float(next_step.delay), 0.0)

    def _execute_step(self, role_name: str, step: EnemyPlanStep) -> StepExecResult:
        action = step.action
        if action == "force_set_location":
            target = str(step.payload.get("target_node", "")).strip()
            return self._action_force_set_location(role_name, target)
        if action == "deploy_forced":
            cards = [str(x).strip() for x in step.payload.get("cards", []) if str(x).strip()]
            node_name = str(step.payload.get("deploy_node", "")).strip() or None
            return self._action_deploy_forced(role_name, cards, node_name=node_name)
        if action == "relocate_and_deploy_forced":
            target = str(step.payload.get("target_node", "")).strip()
            cards = [str(x).strip() for x in step.payload.get("cards", []) if str(x).strip()]
            node_name = str(step.payload.get("deploy_node", "")).strip() or None
            move_result = self._action_force_set_location(role_name, target)
            if move_result.status == "retry":
                return move_result
            deploy_result = self._action_deploy_forced(role_name, cards, node_name=node_name)
            if deploy_result.status == "retry":
                return deploy_result
            if move_result.reason and deploy_result.reason:
                return StepExecResult(status="ok", reason=f"{move_result.reason}; {deploy_result.reason}")
            if move_result.reason:
                return StepExecResult(status="ok", reason=move_result.reason)
            return deploy_result
        if action == "deploy_and_alarm":
            cards = [str(x).strip() for x in step.payload.get("cards", []) if str(x).strip()]
            node_name = str(step.payload.get("deploy_node", "")).strip() or None
            deploy_result = self._action_deploy_forced(role_name, cards, node_name=node_name)
            if deploy_result.status == "retry":
                return deploy_result
            alarm_result = self._action_trigger_school_alarm(role_name)
            if alarm_result.reason and deploy_result.reason:
                return StepExecResult(status="ok", reason=f"{deploy_result.reason}; {alarm_result.reason}")
            if deploy_result.reason:
                return StepExecResult(status="ok", reason=deploy_result.reason)
            return alarm_result
        if action == "collapse_building":
            target = str(step.payload.get("target", "")).strip()
            preserve_actor = bool(step.payload.get("preserve_actor", True))
            return self._action_collapse_building(role_name, target, preserve_actor=preserve_actor)
        if action == "launch_rocket":
            target = str(step.payload.get("target", "")).strip()
            return self._action_launch_rocket(role_name, target)
        if action == "destroy_dezheng_device":
            return self._action_destroy_dezheng_device(role_name)
        if action == "add_dynamic_state":
            text = str(step.payload.get("text", "")).strip()
            if not text:
                return StepExecResult(status="skip", reason="empty_state_text")
            self.engine.add_global_dynamic_state(text)
            return StepExecResult(status="ok")
        return StepExecResult(status="skip", reason=f"unknown_action:{action}")

    def _pause_reason(self, role_name: str) -> str:
        if not self._is_role_alive(role_name):
            return "dead"
        if self.engine.game_over:
            return "game_over"
        role = self.engine.get_role(role_name)
        if bool(role.query_movement_status().get("is_moving", False)):
            return "moving"
        battle_state = str(self.engine.global_config.battle_state or "").strip()
        if battle_state and battle_state == role_name:
            return "in_battle"
        return ""

    def _is_role_alive(self, role_name: str) -> bool:
        if role_name in self.engine.character_profiles:
            profile = self.engine.get_character_profile(role_name)
            if str(profile.status) != "存活":
                return False
        if role_name not in self.engine.campus_map.roles:
            return False
        return self.engine.get_role(role_name).health > 0

    def _action_force_set_location(self, role_name: str, target_node: str) -> StepExecResult:
        if not target_node:
            return StepExecResult(status="skip", reason="missing_target")
        if target_node not in self.engine.campus_map.nodes:
            return StepExecResult(status="skip", reason=f"unknown_target:{target_node}")
        if role_name not in self.engine.campus_map.roles:
            return StepExecResult(status="skip", reason="role_missing")
        role = self.engine.get_role(role_name)
        current = role.current_location
        if current == target_node:
            return StepExecResult(status="ok", reason="already_at_target")
        self.engine.set_role_location(role_name, target_node)
        self._log(role_name, f"relocate {current} -> {target_node}")
        return StepExecResult(status="ok")

    def _action_deploy_forced(
        self,
        role_name: str,
        cards: list[str],
        node_name: str | None = None,
    ) -> StepExecResult:
        if role_name not in self.engine.players:
            self._ensure_player_role(role_name)
        if role_name not in self.engine.players:
            return StepExecResult(status="skip", reason="role_not_player")

        player = self.engine.get_player(role_name)
        ordered = [card for card in cards if card in player.available_cards]
        if not ordered:
            ordered = [card for card in player.card_deck if card in player.available_cards]
        chosen = ordered[0] if ordered else ""
        if not chosen:
            return StepExecResult(status="skip", reason="no_card_available")

        try:
            consume = float(player.available_cards[chosen].consume)
        except KeyError:
            return StepExecResult(status="skip", reason=f"card_missing:{chosen}")
        try:
            chosen_index = list(player.card_deck).index(chosen)
            if player.card_valid < (chosen_index + 1):
                player.set_card_valid(chosen_index + 1)
        except ValueError:
            pass
        self.engine.set_player_holy_water(role_name, max(float(player.holy_water), consume))
        try:
            player.deploy_from_deck(card_name=chosen, node_name=node_name)
        except Exception as exc:  # noqa: BLE001 - keep deterministic scheduler resilient
            return StepExecResult(status="retry", reason=str(exc), retry_after=1.0)

        where = node_name or self.engine.get_role(role_name).current_location
        self._log(role_name, f"deploy_forced {chosen} @ {where}")
        return StepExecResult(status="ok")

    def _action_trigger_school_alarm(self, role_name: str) -> StepExecResult:
        changed = False
        if "警报状态" not in set(self.engine.global_config.global_states):
            self.engine.global_config.add_global_state("警报状态")
            changed = True
        self.engine.event_checker.state.alert_triggered = True
        self.engine.add_global_dynamic_state("触发：学校进入警报状态")
        self.engine.add_global_dynamic_state("全校响起尖锐刺耳的警报声，几乎所有人都能听见。")
        now = float(self.engine.global_config.current_time_unit)
        self.engine.event_checker.state.trigger_history.append(f"t={now:g}: 警报状态触发（敌对脚本）")
        if changed:
            self._log(role_name, "school alarm -> true")
        return StepExecResult(status="ok")

    def _action_launch_rocket(self, role_name: str, target: str) -> StepExecResult:
        if not target:
            return StepExecResult(status="skip", reason="rocket_target_missing")
        now = float(self.engine.global_config.current_time_unit)
        self.engine.add_global_dynamic_state(f"提示：你听到火箭升空声，{target}将在1时间单位后坍塌")
        trigger_text = f"角色:系统|时间{now + 1:g} 若火箭命中{target} 则 建筑倒塌:{target}"
        self.engine.global_config.add_scripted_trigger(trigger_text)
        self._log(role_name, f"rocket_launch -> {target} (impact t={now + 1:g})")
        return StepExecResult(status="ok")

    def _action_destroy_dezheng_device(self, role_name: str) -> StepExecResult:
        if not self.engine.campus_map.is_node_valid("德政楼"):
            return StepExecResult(status="skip", reason="dezheng_already_destroyed")
        # Hard rule:
        # - If main player is not at 德政楼 or adjacent nodes, collapse applies immediately.
        # - Otherwise enter a per-round pending decision event and let main narrative decide.
        if self._is_main_near_dezheng():
            if DYNAMIC_LZB_DEZHENG_PENDING not in set(self.engine.global_config.dynamic_states):
                self.engine.add_global_dynamic_state(DYNAMIC_LZB_DEZHENG_PENDING)
                self.engine.add_global_dynamic_state(
                    "李再斌已逼近德政楼核心装置，是否立刻引爆将由下一步局势决定。"
                )
                self._log(role_name, "dezheng blast switched to pending-decision mode")
            return StepExecResult(status="ok", reason="pending_decision")
        return self._apply_dezheng_device_blast(role_name=role_name, source="enemy_auto_far")

    def _action_collapse_building(
        self,
        role_name: str,
        target: str,
        *,
        preserve_actor: bool,
    ) -> StepExecResult:
        if not target:
            return StepExecResult(status="skip", reason="collapse_target_missing")
        affected_nodes = self._resolve_building_nodes(target)
        if not affected_nodes:
            return StepExecResult(status="skip", reason=f"unknown_collapse_target:{target}")
        blocked = set(affected_nodes)
        if preserve_actor:
            self._evacuate_script_roles_before_collapse(
                primary_role=role_name,
                blocked_nodes=blocked,
                include_others=False,
            )
        now = float(self.engine.global_config.current_time_unit)
        trigger_text = f"角色:系统|时间{now:g} 若敌对脚本推进 则 建筑倒塌:{target}"
        self.engine.global_config.add_scripted_trigger(trigger_text)
        self._log(role_name, f"collapse scheduled now -> {target}")
        return StepExecResult(status="ok")

    def _evacuate_script_roles_before_collapse(
        self,
        primary_role: str,
        blocked_nodes: set[str],
        include_others: bool,
    ) -> None:
        ordered_roles = [primary_role]
        if include_others:
            ordered_roles.extend([ROLE_YAN_HONGFAN, ROLE_LI_NUOCUN, ROLE_LI_ZAIBIN])
        seen: set[str] = set()
        for role_name in ordered_roles:
            if role_name in seen:
                continue
            seen.add(role_name)
            if role_name not in self.engine.campus_map.roles:
                continue
            if not self._is_role_alive(role_name):
                continue
            role = self.engine.get_role(role_name)
            old_node = role.current_location
            if old_node not in blocked_nodes:
                continue
            fallback = self._pick_safe_neighbor(
                old_node,
                blocked_nodes,
                preferred=self._preferred_evacuation_nodes(role_name),
            )
            if not fallback:
                continue
            self.engine.set_role_location(role_name, fallback)
            self._log(role_name, f"evacuate before collapse: {old_node} -> {fallback}")

    def _preferred_evacuation_nodes(self, role_name: str) -> list[str]:
        if role_name == ROLE_LI_NUOCUN:
            return [NODE_LIBRARY, NODE_DEZHENG, NODE_WEST_SOUTH, NODE_EAST_SOUTH]
        if role_name == ROLE_LI_ZAIBIN:
            return [NODE_EAST_SOUTH, NODE_WEST_SOUTH, NODE_INTL, NODE_DEZHENG]
        if role_name == ROLE_YAN_HONGFAN:
            return [NODE_EAST_SOUTH, NODE_WEST_SOUTH, NODE_LIBRARY]
        return []

    def _resolve_building_nodes(self, target: str) -> list[str]:
        if target in BUILDING_NODE_MAP:
            return list(BUILDING_NODE_MAP[target])
        if target in self.engine.campus_map.nodes:
            return [target]
        hits = [name for name in self.engine.campus_map.nodes if target in name]
        return sorted(hits)

    def _pick_safe_neighbor(
        self,
        node_name: str,
        blocked: set[str],
        preferred: list[str] | None = None,
    ) -> str | None:
        if node_name not in self.engine.campus_map.nodes:
            return None
        node = self.engine.campus_map.get_node(node_name)
        preferred_nodes = [str(x).strip() for x in (preferred or []) if str(x).strip()]
        for nxt in preferred_nodes:
            if nxt not in node.neighbors:
                continue
            if nxt in blocked:
                continue
            if nxt not in self.engine.campus_map.nodes:
                continue
            return nxt
        for nxt in sorted(node.neighbors):
            if nxt in blocked:
                continue
            if nxt not in self.engine.campus_map.nodes:
                continue
            return nxt
        return None

    def _build_default_plan(self, role_name: str) -> EnemyPlan:
        if role_name == ROLE_YAN_HONGFAN:
            return EnemyPlan(
                plan_id="yan_fixed_v2",
                loop=False,
                steps=[
                    EnemyPlanStep(
                        "yan_t9_west_and_hog",
                        8.0,
                        "relocate_and_deploy_forced",
                        {
                            "target_node": NODE_WEST_SOUTH,
                            "deploy_node": NODE_WEST_SOUTH,
                            "cards": [CARD_HOG_RIDER],
                        },
                    ),
                    EnemyPlanStep(
                        "yan_t11_destroy_west",
                        2.0,
                        "collapse_building",
                        {"target": "西教学楼", "preserve_actor": True},
                    ),
                ],
            )

        if role_name == ROLE_LI_NUOCUN:
            return EnemyPlan(
                plan_id="lnc_fixed_v2",
                loop=False,
                steps=[
                    EnemyPlanStep(
                        "lnc_t8_goblin_and_alarm",
                        7.0,
                        "deploy_and_alarm",
                        {"cards": [CARD_GOBLIN_GANG]},
                    ),
                    EnemyPlanStep(
                        "lnc_t19_rocket_to_east",
                        11.0,
                        "launch_rocket",
                        {"target": "东教学楼"},
                    ),
                    EnemyPlanStep(
                        "lnc_t25_library_inferno",
                        6.0,
                        "relocate_and_deploy_forced",
                        {
                            "target_node": NODE_LIBRARY,
                            "deploy_node": NODE_LIBRARY,
                            "cards": [CARD_INFERNO_TOWER],
                        },
                    ),
                    EnemyPlanStep(
                        "lnc_t27_burn_library",
                        2.0,
                        "collapse_building",
                        {"target": "图书馆", "preserve_actor": True},
                    ),
                ],
            )

        if role_name == ROLE_LI_ZAIBIN:
            return EnemyPlan(
                plan_id="lzb_fixed_v2",
                loop=False,
                steps=[
                    EnemyPlanStep(
                        "lzb_t7_pekka",
                        6.0,
                        "deploy_forced",
                        {"deploy_node": NODE_DORM, "cards": [CARD_PEKKA]},
                    ),
                    EnemyPlanStep(
                        "lzb_t9_destroy_dorm",
                        2.0,
                        "collapse_building",
                        {"target": "宿舍", "preserve_actor": True},
                    ),
                    EnemyPlanStep(
                        "lzb_t16_intl_ram",
                        7.0,
                        "relocate_and_deploy_forced",
                        {
                            "target_node": NODE_INTL,
                            "deploy_node": NODE_INTL,
                            "cards": [CARD_BATTLE_RAM],
                        },
                    ),
                    EnemyPlanStep(
                        "lzb_t17_destroy_intl",
                        1.0,
                        "collapse_building",
                        {"target": "国际部", "preserve_actor": True},
                    ),
                    EnemyPlanStep(
                        "lzb_t18_move_east_south",
                        1.0,
                        "force_set_location",
                        {"target_node": NODE_EAST_SOUTH},
                    ),
                    EnemyPlanStep(
                        "lzb_t19_move_west_south",
                        1.0,
                        "force_set_location",
                        {"target_node": NODE_WEST_SOUTH},
                    ),
                    EnemyPlanStep(
                        "lzb_t24_dezheng_bandit",
                        5.0,
                        "relocate_and_deploy_forced",
                        {
                            "target_node": NODE_DEZHENG,
                            "deploy_node": NODE_DEZHENG,
                            "cards": [CARD_BANDIT],
                        },
                    ),
                    EnemyPlanStep(
                        "lzb_t26_destroy_dezheng_device",
                        2.0,
                        "destroy_dezheng_device",
                        {},
                    ),
                ],
            )

        return EnemyPlan(
            plan_id="enemy_fallback_idle_v1",
            loop=False,
            steps=[
                EnemyPlanStep("fallback_wait", 100.0, "add_dynamic_state", {"text": f"{role_name}保持静默。"}),
            ],
        )

    def is_lzb_dezheng_pending(self) -> bool:
        return DYNAMIC_LZB_DEZHENG_PENDING in set(self.engine.global_config.dynamic_states)

    def resolve_lzb_dezheng_pending(self) -> bool:
        """
        Resolve pending dezheng-device event from main narrative event trigger.
        Returns True when collapse is really applied.
        """
        states = set(self.engine.global_config.dynamic_states)
        if DYNAMIC_LZB_DEZHENG_PENDING not in states:
            return False
        if not self._is_role_alive(ROLE_LI_ZAIBIN):
            self.engine.global_config.remove_dynamic_state(DYNAMIC_LZB_DEZHENG_PENDING)
            self.engine.add_global_dynamic_state(DYNAMIC_LZB_DEZHENG_BANNED)
            return False
        result = self._apply_dezheng_device_blast(role_name=ROLE_LI_ZAIBIN, source="pending_event")
        return result.status == "ok"

    def _cleanup_pending_enemy_events(self) -> None:
        if DYNAMIC_LZB_DEZHENG_PENDING not in set(self.engine.global_config.dynamic_states):
            return
        if not self._is_role_alive(ROLE_LI_ZAIBIN):
            self.engine.global_config.remove_dynamic_state(DYNAMIC_LZB_DEZHENG_PENDING)
            self.engine.add_global_dynamic_state(DYNAMIC_LZB_DEZHENG_BANNED)
            now = float(self.engine.global_config.current_time_unit)
            self.engine.event_checker.state.trigger_history.append(
                f"t={now:g}: pending_dezheng canceled (李再斌已死亡)"
            )
            return
        if not self.engine.campus_map.is_node_valid("德政楼"):
            self.engine.global_config.remove_dynamic_state(DYNAMIC_LZB_DEZHENG_PENDING)

    def _is_main_near_dezheng(self) -> bool:
        main = str(self.engine.main_player_name or "").strip()
        if not main or main not in self.engine.campus_map.roles:
            return False
        if "德政楼" not in self.engine.campus_map.nodes:
            return False
        main_node = self.engine.get_role(main).current_location
        dezheng_neighbors = set(self.engine.campus_map.get_node("德政楼").neighbors)
        return main_node == "德政楼" or main_node in dezheng_neighbors

    def _apply_dezheng_device_blast(self, role_name: str, source: str) -> StepExecResult:
        if not self.engine.campus_map.is_node_valid("德政楼"):
            return StepExecResult(status="skip", reason="dezheng_already_destroyed")
        self.engine.global_config.remove_dynamic_state(DYNAMIC_LZB_DEZHENG_PENDING)
        self.engine.add_global_dynamic_state(DEZHENG_BLUE_DEVICE_SEEN)
        self.engine.add_global_dynamic_state(DEZHENG_BLUE_DEVICE_DESTROYED)
        self.engine.add_global_dynamic_state("德政楼蓝光装置被摧毁，德政楼结构同步崩解。")
        self.engine.add_global_dynamic_state("蓝光结界解除，学校进入不可阻挡的自爆倒计时阶段。")
        self.engine.event_checker.collapse_structure_now("德政楼", reason=f"enemy_director:{role_name}:{source}")
        self._log(role_name, f"dezheng_device_blast applied ({source})")
        return StepExecResult(status="ok")

    def _preview_rows_for_step(
        self,
        role_name: str,
        step: EnemyPlanStep,
        event_time: float,
        end_time: float,
        seed: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        base_id = 900000 + (seed * 10)
        action = str(step.action)

        def _row(idx: int, owner: str, result: str, condition: str = "敌对主线推进") -> dict[str, Any]:
            return {
                "id": base_id + idx,
                "owner": owner,
                "trigger_time": float(event_time),
                "condition": condition,
                "result": result,
                "text": f"时间{event_time:g} 若{condition} 则 {result}",
                "triggered": False,
                "handled": False,
            }

        if action == "force_set_location":
            target = str(step.payload.get("target_node", "")).strip()
            if target:
                rows.append(_row(1, role_name, f"{role_name}移动至{target}"))
            return rows

        if action in {"deploy_forced", "relocate_and_deploy_forced", "deploy_and_alarm"}:
            cards = [str(x).strip() for x in (step.payload.get("cards", []) or []) if str(x).strip()]
            card = cards[0] if cards else "单位"
            node = (
                str(step.payload.get("deploy_node", "")).strip()
                or str(step.payload.get("target_node", "")).strip()
                or (self.engine.get_role(role_name).current_location if role_name in self.engine.campus_map.roles else "")
            )
            place_text = f"{node}" if node else "当前位置"
            rows.append(_row(1, role_name, f"{role_name}将在{place_text}部署{card}"))
            if action == "deploy_and_alarm":
                rows.append(_row(2, "global", "警报状态触发"))
            return rows

        if action == "collapse_building":
            target = str(step.payload.get("target", "")).strip()
            if target:
                rows.append(_row(1, role_name, f"建筑倒塌:{target}"))
            return rows

        if action == "launch_rocket":
            target = str(step.payload.get("target", "")).strip()
            if target:
                rows.append(_row(1, role_name, f"{role_name}向{target}发射火箭"))
                impact_time = float(event_time) + 1.0
                if impact_time <= float(end_time) + 1e-9:
                    rows.append(
                        {
                            "id": base_id + 2,
                            "owner": "global",
                            "trigger_time": impact_time,
                            "condition": f"{role_name}火箭命中",
                            "result": f"建筑倒塌:{target}",
                            "text": f"时间{impact_time:g} 若{role_name}火箭命中 则 建筑倒塌:{target}",
                            "triggered": False,
                            "handled": False,
                        }
                    )
            return rows

        if action == "destroy_dezheng_device":
            rows.append(_row(1, role_name, "待决事件:李再斌尝试引爆德政楼装置"))
            return rows

        return rows

    def _log(self, role_name: str, text: str) -> None:
        now = float(self.engine.global_config.current_time_unit)
        self.engine.event_checker.state.trigger_history.append(
            f"t={now:g}: enemy_director:{role_name} {text}"
        )
