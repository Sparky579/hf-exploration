export interface PlayerState {
  time: number;
  location: string;
  hp: number;
  holy_water: number;
  card_deck: string[];
  neighbors: string[];
  companions: string[];
  game_over: boolean;
  game_result: string | null;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'system';
  text: string;
  isStreaming?: boolean;
  isError?: boolean;
}

export interface LogState {
  roles: {
    name: string;
    location: string;
    health: number;
    is_moving: boolean;
    target: string | null;
  }[];
  pipeline_logs: string[];
}
