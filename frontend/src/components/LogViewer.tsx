import { useState, useEffect } from 'react';
import { X, Activity, MapPin, Heart, Target } from 'lucide-react';
import { fetchLogs } from '../api';
import type { LogState } from '../types';

interface LogViewerProps {
    sessionId: string;
    onClose: () => void;
}

export default function LogViewer({ sessionId, onClose }: LogViewerProps) {
    const [logs, setLogs] = useState<LogState | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchLogs(sessionId)
            .then(data => {
                setLogs(data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to fetch logs", err);
                setLoading(false);
            });
    }, [sessionId]);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
            <div className="glass-panel w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden relative">
                <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                    <h2 className="text-xl font-semibold flex items-center gap-2">
                        <Activity className="w-5 h-5 text-accent-primary" />
                        System Runtime Logs
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-2 bg-white/5 hover:bg-white/10 rounded-full transition-colors"
                    >
                        <X className="w-5 h-5 text-text-secondary hover:text-white" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
                    {loading ? (
                        <div className="flex justify-center py-10">
                            <div className="w-8 h-8 rounded-full border-2 border-accent-primary border-t-transparent animate-spin" />
                        </div>
                    ) : logs ? (
                        <>
                            <div>
                                <h3 className="text-lg font-medium mb-3 text-text-secondary">角色实时状态 (Role Snapshot)</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {logs.roles.map(role => (
                                        <div key={role.name} className="bg-white/5 border border-white/5 rounded-lg p-3 flex flex-col gap-2">
                                            <div className="flex items-center justify-between font-medium">
                                                <span className="text-accent-primary">{role.name}</span>
                                                {role.is_moving && <span className="text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full">Moving</span>}
                                            </div>
                                            <div className="flex items-start gap-4 text-sm text-text-secondary">
                                                <span className="flex items-center gap-1"><Heart className="w-3.5 h-3.5" /> {role.health.toFixed(1)}</span>
                                                <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {role.location}</span>
                                                {role.target && <span className="flex items-center gap-1"><Target className="w-3.5 h-3.5" /> {role.target}</span>}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <h3 className="text-lg font-medium mb-3 text-text-secondary">后台指令流水线 (Pipeline Actions)</h3>
                                <div className="bg-[#0b0c10] border border-white/10 rounded-lg p-4 font-mono text-sm h-64 overflow-y-auto">
                                    {logs.pipeline_logs.length === 0 ? (
                                        <span className="text-text-muted italic">No logs available.</span>
                                    ) : (
                                        logs.pipeline_logs.map((item, idx) => {
                                            const line = typeof item === 'string'
                                                ? item
                                                : `[t=${Number(item.time ?? 0).toFixed(1)}] ${item.command ?? ''} :: ${item.detail ?? ''}`;
                                            const status = typeof item === 'string' ? '' : String(item.status ?? '').toLowerCase();
                                            const isError = status === 'error' || line.toLowerCase().includes('error');
                                            return (
                                                <div key={idx} className="mb-1">
                                                    <span className="text-[#64748b]">[{idx.toString().padStart(4, '0')}]</span>{' '}
                                                    <span className={isError ? 'text-red-400' : 'text-emerald-400'}>{line}</span>
                                                </div>
                                            );
                                        })
                                    )}
                                </div>
                            </div>

                            <div>
                                <h3 className="text-lg font-medium mb-3 text-text-secondary">Pending Retry Commands</h3>
                                <div className="bg-[#0b0c10] border border-white/10 rounded-lg p-4 font-mono text-sm h-24 overflow-y-auto">
                                    {(logs.pending_failed_commands ?? []).length === 0 ? (
                                        <span className="text-text-muted italic">None.</span>
                                    ) : (
                                        (logs.pending_failed_commands ?? []).map((line, idx) => (
                                            <div key={`${line}-${idx}`} className="text-amber-300 mb-1">{line}</div>
                                        ))
                                    )}
                                </div>
                            </div>

                            <div>
                                <h3 className="text-lg font-medium mb-3 text-text-secondary">LLM Raw Logs</h3>
                                <div className="bg-[#0b0c10] border border-white/10 rounded-lg p-4 font-mono text-xs h-56 overflow-y-auto whitespace-pre-wrap">
                                    {(logs.llm_logs ?? []).length === 0 ? (
                                        <span className="text-text-muted italic">No LLM logs yet.</span>
                                    ) : (
                                        (logs.llm_logs ?? []).map((item, idx) => (
                                            <div key={idx} className="mb-3 border-b border-white/10 pb-3">
                                                <div className="text-slate-400 mb-1">#{idx + 1}</div>
                                                <div className="text-slate-200">{JSON.stringify(item, null, 2)}</div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="text-center py-10 text-red-400">Failed to load logs.</div>
                    )}
                </div>
            </div>
        </div>
    );
}
