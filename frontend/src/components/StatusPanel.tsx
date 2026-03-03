import { useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import { createPortal } from 'react-dom';
import type { CardDetail, CompanionDetail, NeighborDetail, PlayerState } from '../types';
import { Clock, MapPin, Heart, Droplet, Users, Shield, Compass, Navigation, Info } from 'lucide-react';
import clsx from 'clsx';

const TOOLTIP_WIDTH = 420;
const TOOLTIP_OFFSET_X = 16;
const TOOLTIP_OFFSET_Y = 20;

type FloatingTooltip = {
    visible: boolean;
    x: number;
    y: number;
    title: string;
    lines: string[];
    status: 'ok' | 'warn' | null;
};

const EMPTY_TOOLTIP: FloatingTooltip = {
    visible: false,
    x: 0,
    y: 0,
    title: '',
    lines: [],
    status: null,
};

const formatCost = (cost: number): string => (Number.isInteger(cost) ? `${cost}` : cost.toFixed(1));

const fallbackNeighbors = (state: PlayerState): NeighborDetail[] =>
    state.neighbor_details ??
    state.neighbors.map((name) => ({
        name,
        description: '暂无地点介绍',
    }));

const fallbackCards = (state: PlayerState): CardDetail[] =>
    state.card_details ??
    state.card_deck.map((name, index) => {
        const inValidWindow = index < (state.card_valid ?? 0);
        return {
            name,
            consume: 0,
            description: '',
            index,
            in_valid_window: inValidWindow,
            holy_water_enough: true,
            playable: inValidWindow,
            unavailable_reason: inValidWindow ? null : '当前排序没到',
        };
    });

const dedupeCompanions = (rows: CompanionDetail[]): CompanionDetail[] => {
    const map = new Map<string, CompanionDetail>();
    for (const row of rows) {
        const name = String(row?.name ?? '').trim();
        if (!name) continue;
        const prev = map.get(name);
        if (!prev) {
            map.set(name, row);
            continue;
        }
        // Prefer the row carrying richer runtime fields.
        const prevScore =
            (typeof prev.health === 'number' ? 1 : 0) +
            (prev.status ? 1 : 0);
        const nextScore =
            (typeof row.health === 'number' ? 1 : 0) +
            (row.status ? 1 : 0);
        if (nextScore >= prevScore) {
            map.set(name, row);
        }
    }
    return Array.from(map.values());
};

const getTooltipPosition = (event: ReactMouseEvent): { x: number; y: number } => {
    const maxX = Math.max(12, window.innerWidth - TOOLTIP_WIDTH - 12);
    const x = Math.min(maxX, event.clientX + TOOLTIP_OFFSET_X);
    const y = Math.max(8, event.clientY + TOOLTIP_OFFSET_Y);
    return { x, y };
};

export default function StatusPanel({ state }: { state: PlayerState | null }) {
    const [tooltip, setTooltip] = useState<FloatingTooltip>(EMPTY_TOOLTIP);

    if (!state) {
        return (
            <div className="w-full h-full flex items-center justify-center text-text-muted">
                Waiting for game to start...
            </div>
        );
    }

    const neighbors = fallbackNeighbors(state);
    const cards = fallbackCards(state);
    const companionRowsRaw: CompanionDetail[] =
        state.companion_details && state.companion_details.length > 0
            ? state.companion_details
            : state.companions.map((name) => ({ name }));
    const companionRows = dedupeCompanions(companionRowsRaw);
    const locationDescription = state.location_description?.trim() || '暂无地点介绍';
    const cardValid = state.card_valid ?? 0;
    const friendlyUnits = state.friendly_units ?? state.scene_units ?? [];
    const enemyUnits = state.enemy_units ?? [];
    const globalStates = state.global_states ?? [];
    const globalDynamicStates = state.global_dynamic_states ?? [];
    const battleTarget = (state.battle_target ?? '').trim();

    const hideTooltip = () => setTooltip(EMPTY_TOOLTIP);

    const showNeighborTooltip = (event: ReactMouseEvent, n: NeighborDetail) => {
        const pos = getTooltipPosition(event);
        setTooltip({
            visible: true,
            x: pos.x,
            y: pos.y,
            title: n.name,
            lines: [n.description || '暂无地点介绍'],
            status: null,
        });
    };

    const showCardTooltip = (event: ReactMouseEvent, card: CardDetail) => {
        const pos = getTooltipPosition(event);
        const reason =
            card.playable
                ? '当前可用'
                : card.unavailable_reason || (!card.holy_water_enough ? '圣水花费不足' : '当前排序没到');
        setTooltip({
            visible: true,
            x: pos.x,
            y: pos.y,
            title: card.name,
            lines: [
                `圣水花费: ${formatCost(card.consume)}`,
                card.description || '暂无卡牌介绍',
                `状态: ${reason}`,
            ],
            status: card.playable ? 'ok' : 'warn',
        });
    };

    const tooltipNode =
        tooltip.visible && typeof document !== 'undefined'
            ? createPortal(
                  <div
                      className="pointer-events-none fixed z-[9999] rounded-xl bg-slate-900/95 border border-slate-600 shadow-2xl p-4 text-sm text-slate-100 whitespace-pre-wrap"
                      style={{ left: tooltip.x, top: tooltip.y, width: TOOLTIP_WIDTH, minHeight: 140 }}
                  >
                      <div className="font-bold text-base mb-2 text-white">{tooltip.title}</div>
                      <div className="space-y-1.5 leading-relaxed">
                          {tooltip.lines.map((line, idx) => (
                              <div key={idx} className="text-slate-200">
                                  {line}
                              </div>
                          ))}
                      </div>
                      <div
                          className={clsx(
                              'mt-3 flex items-center gap-1.5 text-xs font-semibold',
                              tooltip.status === 'ok'
                                  ? 'text-emerald-300'
                                  : tooltip.status === 'warn'
                                    ? 'text-red-300'
                                    : 'text-slate-400'
                          )}
                      >
                          <Info className="w-3.5 h-3.5" />
                          鼠标悬停查看详细说明
                      </div>
                  </div>,
                  document.body
              )
            : null;

    return (
        <>
            <div className="w-full h-full min-h-0 p-6 pr-4 overflow-y-auto overflow-x-hidden space-y-6 select-none animate-fade-in">
            <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2 mb-2">
                <Shield className="text-accent-primary" />
                状态面板
            </h2>

            <div className="grid grid-cols-2 gap-4">
                <div className="glass-panel p-4 flex flex-col gap-1 relative overflow-hidden">
                    <div className="text-text-secondary text-sm font-medium flex items-center gap-1.5 z-10">
                        <Clock className="w-4 h-4" /> 时间刻度
                    </div>
                    <div className="text-2xl font-bold text-white z-10">t = {state.time.toFixed(1)}</div>
                    <div className="absolute top-0 right-0 p-4 opacity-10">
                        <Clock className="w-12 h-12" />
                    </div>
                </div>

                <div className="glass-panel p-4 flex flex-col gap-1 relative overflow-hidden">
                    <div className="text-text-secondary text-sm font-medium flex items-center gap-1.5 z-10">
                        <Heart className="w-4 h-4 text-rose-400" /> 生命值
                    </div>
                    <div className="text-2xl font-bold text-rose-100 z-10">{state.hp.toFixed(1)}</div>
                    <div className="absolute top-0 right-0 p-4 opacity-10 text-rose-500">
                        <Heart className="w-12 h-12" />
                    </div>
                </div>

                <div className="glass-panel p-4 flex flex-col gap-1 col-span-2 relative overflow-hidden bg-fuchsia-950/20 border-fuchsia-500/20">
                    <div className="text-fuchsia-300 text-sm font-medium flex items-center gap-1.5 z-10">
                        <Droplet className="w-4 h-4" /> 圣水能量
                    </div>
                    <div className="text-3xl font-bold text-fuchsia-100 z-10 drop-shadow-[0_0_8px_rgba(217,70,239,0.5)]">
                        {state.holy_water.toFixed(1)} / 10
                    </div>
                    <div className="w-full h-2 bg-black/40 rounded-full mt-2 overflow-hidden relative z-10 border border-white/5">
                        <div
                            className="h-full bg-gradient-to-r from-fuchsia-600 to-pink-400 rounded-full transition-all duration-500 shadow-[0_0_10px_rgba(192,38,211,0.8)]"
                            style={{ width: `${Math.min(100, (state.holy_water / 10) * 100)}%` }}
                        />
                    </div>
                    <div className="absolute top-0 right-0 p-4 opacity-10 text-fuchsia-500">
                        <Droplet className="w-16 h-16" />
                    </div>
                </div>
            </div>

            <div className="glass-panel">
                <div className="bg-white/5 px-4 py-3 border-b border-white/5 font-medium flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-amber-400" /> 当前位置
                </div>
                <div className="p-4">
                    <div className="text-xl font-bold text-white mb-2 ml-1">{state.location}</div>
                    <p className="text-sm text-slate-300 leading-relaxed mb-4 whitespace-pre-wrap">{locationDescription}</p>

                    <div className="text-sm font-medium text-text-secondary mb-2 flex items-center gap-1 cursor-default">
                        <Compass className="w-3.5 h-3.5" /> 可前往位置
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {neighbors.length === 0 ? (
                            <span className="text-sm text-text-muted italic">无可前往位置</span>
                        ) : (
                            neighbors.map((n) => (
                                <div
                                    key={n.name}
                                    className="px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-md text-sm text-amber-200 flex items-center gap-1.5 hover:bg-amber-500/20 transition-colors cursor-default"
                                    onMouseEnter={(event) => showNeighborTooltip(event, n)}
                                    onMouseMove={(event) => showNeighborTooltip(event, n)}
                                    onMouseLeave={hideTooltip}
                                >
                                    <Navigation className="w-3 h-3" /> {n.name}
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            <div className="glass-panel">
                <div className="bg-white/5 px-4 py-3 border-b border-white/5 font-medium flex items-center justify-between">
                    <span>卡组手牌</span>
                    <span className="text-xs text-slate-300">可用窗口: {cardValid}/8</span>
                </div>
                <div className="p-4 flex flex-col gap-2">
                    {cards.length === 0 ? (
                        <div className="text-sm text-text-muted italic p-2 text-center border border-white/5 rounded-lg border-dashed">
                            暂无卡牌
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 gap-2">
                            {cards.map((card, i) => (
                                <div
                                    key={`${card.name}-${i}`}
                                    className={clsx(
                                        'flex items-center justify-center p-2 rounded-lg border shadow-inner text-sm font-medium transition-colors cursor-default text-center',
                                        card.playable
                                            ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200 hover:border-emerald-300'
                                            : 'bg-red-500/10 border-red-500/35 text-red-200 hover:border-red-400'
                                    )}
                                    onMouseEnter={(event) => showCardTooltip(event, card)}
                                    onMouseMove={(event) => showCardTooltip(event, card)}
                                    onMouseLeave={hideTooltip}
                                >
                                    {card.name} ({formatCost(card.consume)}圣水)
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {state.companions.length > 0 && (
                <div className="glass-panel">
                    <div className="bg-white/5 px-4 py-3 border-b border-white/5 font-medium flex items-center gap-2">
                        <Users className="w-4 h-4 text-emerald-400" /> 队伍成员
                    </div>
                    <div className="p-4 flex flex-col gap-2 max-h-72 overflow-y-auto overflow-x-hidden">
                        {companionRows.length === 0 ? (
                            <div className="text-sm text-text-muted italic">队伍信息同步中...</div>
                        ) : (
                            companionRows.map((c, i) => (
                                <div
                                    key={`${c.name}-${i}`}
                                    className="px-3 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-sm text-emerald-200 break-words flex flex-col leading-relaxed"
                                >
                                    <div className="font-medium">{c.name}</div>
                                    <div className="text-xs text-emerald-300/90 mt-1 leading-relaxed whitespace-normal">
                                        <div>
                                            {typeof c.health === 'number' ? `hp: ${c.health.toFixed(1)}` : 'hp: -'}
                                            {c.status ? ` | status: ${c.status}` : ''}
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            )}

            <div className="glass-panel overflow-hidden">
                <div className="bg-white/5 px-4 py-3 border-b border-white/5 font-medium flex items-center gap-2">
                    <Shield className="w-4 h-4 text-cyan-300" /> 伴随单位
                </div>
                <div className="p-4 space-y-3 max-h-96 overflow-y-auto overflow-x-hidden">
                    <div className="text-xs uppercase tracking-wider text-cyan-300/90">我方单位</div>
                    {friendlyUnits.length === 0 ? (
                        <div className="text-sm text-text-muted italic">无</div>
                    ) : (
                        friendlyUnits.map((u) => (
                            <div
                                key={u.unit_id}
                                className="px-3 py-2 bg-cyan-500/10 border border-cyan-500/20 rounded-lg text-sm text-cyan-100"
                            >
                                <div className="font-medium">{u.owner}: {u.name}</div>
                                <div className="text-xs text-cyan-200/90 mt-1">
                                    hp {u.health.toFixed(1)}/{u.max_health.toFixed(1)} | atk {u.attack.toFixed(1)} | {u.is_flying ? 'air' : 'ground'} | {u.node}
                                </div>
                            </div>
                        ))
                    )}
                    <div className="text-xs uppercase tracking-wider text-rose-300/90 pt-1">敌方单位</div>
                    {enemyUnits.length === 0 ? (
                        <div className="text-sm text-text-muted italic">无</div>
                    ) : (
                        enemyUnits.map((u) => (
                            <div
                                key={u.unit_id}
                                className="px-3 py-2 bg-rose-500/10 border border-rose-500/20 rounded-lg text-sm text-rose-100"
                            >
                                <div className="font-medium">{u.owner}: {u.name}</div>
                                <div className="text-xs text-rose-200/90 mt-1">
                                    hp {u.health.toFixed(1)}/{u.max_health.toFixed(1)} | atk {u.attack.toFixed(1)} | {u.is_flying ? 'air' : 'ground'} | {u.node}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            <div className="glass-panel overflow-hidden">
                <div className="bg-white/5 px-4 py-3 border-b border-white/5 font-medium">角色全局状态</div>
                <div className="p-4 space-y-3 max-h-80 overflow-y-auto overflow-x-hidden">
                    <div>
                        <div className="text-xs uppercase tracking-wider text-slate-300 mb-1">global_states</div>
                        {globalStates.length === 0 ? (
                            <div className="text-sm text-text-muted italic">无</div>
                        ) : (
                            <div className="space-y-1">
                                {globalStates.map((row, idx) => (
                                    <div key={`gs-${idx}`} className="text-sm text-slate-200 break-words">{row}</div>
                                ))}
                            </div>
                        )}
                    </div>
                    <div>
                        <div className="text-xs uppercase tracking-wider text-slate-300 mb-1">global_dynamic_states</div>
                        {globalDynamicStates.length === 0 ? (
                            <div className="text-sm text-text-muted italic">无</div>
                        ) : (
                            <div className="space-y-1">
                                {globalDynamicStates.map((row, idx) => (
                                    <div key={`gds-${idx}`} className="text-sm text-slate-200 break-words">{row}</div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="glass-panel">
                <div className="bg-white/5 px-4 py-3 border-b border-white/5 font-medium flex items-center gap-2">
                    <Shield className="w-4 h-4 text-rose-300" /> 交战状态
                </div>
                <div className="p-4 text-sm">
                    {battleTarget ? (
                        <div className="text-rose-200">正在与 <span className="font-semibold">{battleTarget}</span> 交战</div>
                    ) : (
                        <div className="text-slate-300">当前未进入角色交战</div>
                    )}
                </div>
            </div>

            {state.game_over && (
                <div
                    className={clsx(
                        'p-4 rounded-xl border font-bold text-center uppercase tracking-widest animate-pulse',
                        state.game_result === 'win'
                            ? 'bg-amber-500/20 border-amber-500/50 text-amber-400 shadow-[0_0_20px_rgba(245,158,11,0.3)]'
                            : 'bg-red-500/20 border-red-500/50 text-red-400 shadow-[0_0_20px_rgba(239,68,68,0.3)]'
                    )}
                >
                    {state.game_result === 'win' ? 'VICTORY' : 'GAME OVER'}
                </div>
            )}

            </div>
            {tooltipNode}
        </>
    );
}
