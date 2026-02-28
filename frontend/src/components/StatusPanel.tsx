import { PlayerState } from '../types';
import { Clock, MapPin, Heart, Droplet, Users, Shield, Compass, Navigation } from 'lucide-react';
import clsx from 'clsx';

export default function StatusPanel({ state }: { state: PlayerState | null }) {
    if (!state) return (
        <div className="w-full h-full flex items-center justify-center text-text-muted">
            Waiting for game to start...
        </div>
    );

    return (
        <div className="w-full h-full p-6 overflow-y-auto flex flex-col gap-6 select-none animate-fade-in">
            <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2 mb-2">
                <Shield className="text-accent-primary" />
                状态面板
            </h2>

            {/* Core Stats */}
            <div className="grid grid-cols-2 gap-4">
                <div className="glass-panel p-4 flex flex-col gap-1 relative overflow-hidden">
                    <div className="text-text-secondary text-sm font-medium flex items-center gap-1.5 z-10">
                        <Clock className="w-4 h-4" /> 时间刻度
                    </div>
                    <div className="text-2xl font-bold text-white z-10">t = {state.time.toFixed(1)}</div>
                    <div className="absolute top-0 right-0 p-4 opacity-10"><Clock className="w-12 h-12" /></div>
                </div>

                <div className="glass-panel p-4 flex flex-col gap-1 relative overflow-hidden">
                    <div className="text-text-secondary text-sm font-medium flex items-center gap-1.5 z-10">
                        <Heart className="w-4 h-4 text-rose-400" /> 生命值
                    </div>
                    <div className="text-2xl font-bold text-rose-100 z-10">{state.hp.toFixed(1)}</div>
                    <div className="absolute top-0 right-0 p-4 opacity-10 text-rose-500"><Heart className="w-12 h-12" /></div>
                </div>

                <div className="glass-panel p-4 flex flex-col gap-1 col-span-2 relative overflow-hidden bg-fuchsia-950/20 border-fuchsia-500/20">
                    <div className="text-fuchsia-300 text-sm font-medium flex items-center gap-1.5 z-10">
                        <Droplet className="w-4 h-4" /> 圣水能量 (Elixir)
                    </div>
                    <div className="text-3xl font-bold text-fuchsia-100 z-10 drop-shadow-[0_0_8px_rgba(217,70,239,0.5)]">
                        {state.holy_water.toFixed(1)} / 10
                    </div>

                    {/* Elixir bar */}
                    <div className="w-full h-2 bg-black/40 rounded-full mt-2 overflow-hidden relative z-10 border border-white/5">
                        <div
                            className="h-full bg-gradient-to-r from-fuchsia-600 to-pink-400 rounded-full transition-all duration-500 shadow-[0_0_10px_rgba(192,38,211,0.8)]"
                            style={{ width: `${Math.min(100, (state.holy_water / 10) * 100)}%` }}
                        />
                    </div>
                    <div className="absolute top-0 right-0 p-4 opacity-10 text-fuchsia-500"><Droplet className="w-16 h-16" /></div>
                </div>
            </div>

            {/* Location info */}
            <div className="glass-panel overflow-hidden">
                <div className="bg-white/5 px-4 py-3 border-b border-white/5 font-medium flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-amber-400" /> 当前位置
                </div>
                <div className="p-4">
                    <div className="text-xl font-bold text-white mb-4 ml-1">{state.location}</div>

                    <div className="text-sm font-medium text-text-secondary mb-2 flex items-center gap-1 cursor-default">
                        <Compass className="w-3.5 h-3.5" /> 相邻路线 (可前往)
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {state.neighbors.length === 0 ? (
                            <span className="text-sm text-text-muted italic">无出路</span>
                        ) : (
                            state.neighbors.map(n => (
                                <div key={n} className="px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-md text-sm text-amber-200 flex items-center gap-1.5 hover:bg-amber-500/20 transition-colors">
                                    <Navigation className="w-3 h-3" /> {n}
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Cards Deck */}
            <div className="glass-panel overflow-hidden">
                <div className="bg-white/5 px-4 py-3 border-b border-white/5 font-medium flex items-center gap-2">
                    卡组手牌
                </div>
                <div className="p-4 flex flex-col gap-2">
                    {state.card_deck.length === 0 ? (
                        <div className="text-sm text-text-muted italic p-2 text-center border border-white/5 rounded-lg border-dashed">
                            暂无卡牌
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 gap-2">
                            {state.card_deck.map((card, i) => (
                                <div key={i} className="flex items-center justify-center p-2 rounded-lg bg-gradient-to-b from-slate-800 to-slate-900 border border-slate-700 shadow-inner text-sm font-medium text-slate-200 hover:border-accent-primary transition-colors cursor-default text-center">
                                    {card}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Companions */}
            {state.companions.length > 0 && (
                <div className="glass-panel overflow-hidden">
                    <div className="bg-white/5 px-4 py-3 border-b border-white/5 font-medium flex items-center gap-2">
                        <Users className="w-4 h-4 text-emerald-400" /> 队伍成员
                    </div>
                    <div className="p-4 flex flex-wrap gap-2">
                        {state.companions.map(c => (
                            <div key={c} className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-sm text-emerald-300">
                                {c}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Game End Status */}
            {state.game_over && (
                <div className={clsx(
                    "p-4 rounded-xl border font-bold text-center uppercase tracking-widest animate-pulse",
                    state.game_result === 'win'
                        ? "bg-amber-500/20 border-amber-500/50 text-amber-400 shadow-[0_0_20px_rgba(245,158,11,0.3)]"
                        : "bg-red-500/20 border-red-500/50 text-red-400 shadow-[0_0_20px_rgba(239,68,68,0.3)]"
                )}>
                    {state.game_result === 'win' ? 'VICTORY - 逃出生天' : 'GAME OVER - 葬身校园'}
                </div>
            )}
        </div>
    );
}
