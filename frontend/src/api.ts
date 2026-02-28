import { PlayerState, LogState } from './types';

const API_BASE = 'http://localhost:8000/api';

export const startGame = async (apiKey?: string): Promise<{ sessionId: string, message: string, state: PlayerState }> => {
    const res = await fetch(`${API_BASE}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey })
    });
    if (!res.ok) throw new Error("Failed to start game");
    const data = await res.json();
    return {
        sessionId: data.session_id,
        message: data.message,
        state: data.state
    };
};

export const fetchLogs = async (sessionId: string): Promise<LogState> => {
    const res = await fetch(`${API_BASE}/logs/${sessionId}`);
    if (!res.ok) throw new Error("Failed to fetch logs");
    return res.json();
};

export const API_ACTION_URL = `${API_BASE}/action`;
