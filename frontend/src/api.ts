import type { PlayerState, LogState } from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api';

const parseErrorMessage = async (res: Response): Promise<string> => {
    const body = await res.text();
    if (!body) return `HTTP ${res.status}`;
    try {
        const parsed = JSON.parse(body) as { detail?: unknown };
        if (parsed?.detail) return String(parsed.detail);
    } catch {
        // Fall back to raw text when response body is not JSON.
    }
    return body;
};

export type StartGameOptions = {
    provider?: 'gemini' | 'openai';
    apiKey?: string;
    model?: string;
    baseUrl?: string;
    reasoningEffort?: 'minimal' | 'low' | 'medium' | 'high';
};

export const startGame = async (
    options: StartGameOptions = {}
): Promise<{ sessionId: string, message: string, state: PlayerState }> => {
    const res = await fetch(`${API_BASE}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            provider: options.provider,
            api_key: options.apiKey,
            model: options.model,
            base_url: options.baseUrl,
            reasoning_effort: options.reasoningEffort,
        })
    });
    if (!res.ok) throw new Error(await parseErrorMessage(res));
    const data = await res.json();
    return {
        sessionId: data.session_id,
        message: data.message,
        state: data.state
    };
};

export const fetchLogs = async (sessionId: string): Promise<LogState> => {
    const res = await fetch(`${API_BASE}/logs/${sessionId}`);
    if (!res.ok) throw new Error(await parseErrorMessage(res));
    return res.json();
};

export const fetchState = async (sessionId: string): Promise<PlayerState> => {
    const res = await fetch(`${API_BASE}/state/${sessionId}`);
    if (!res.ok) throw new Error(await parseErrorMessage(res));
    const data = await res.json();
    return data.state as PlayerState;
};

export const API_ACTION_URL = `${API_BASE}/action`;
