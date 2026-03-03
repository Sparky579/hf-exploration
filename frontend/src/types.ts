export interface NeighborDetail {
  name: string;
  description: string;
}

export interface CardDetail {
  name: string;
  consume: number;
  description: string;
  index: number;
  in_valid_window: boolean;
  holy_water_enough: boolean;
  playable: boolean;
  unavailable_reason: string | null;
}

export interface CompanionDetail {
  name: string;
  health?: number;
  status?: string;
}

export interface SceneUnit {
  unit_id: string;
  owner: string;
  name: string;
  health: number;
  max_health: number;
  attack: number;
  is_flying: boolean;
  card_type: string;
  node: string;
}

export interface PlayerState {
  time: number;
  location: string;
  location_description?: string;
  hp: number;
  holy_water: number;
  main_game_state?: string;
  card_deck: string[];
  card_valid?: number;
  card_details?: CardDetail[];
  neighbors: string[];
  neighbor_details?: NeighborDetail[];
  companions: string[];
  companion_details?: CompanionDetail[];
  scene_units?: SceneUnit[];
  friendly_units?: SceneUnit[];
  enemy_units?: SceneUnit[];
  global_states?: string[];
  global_dynamic_states?: string[];
  battle_target?: string | null;
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
  pipeline_logs: Array<{
    time?: number;
    command?: string;
    status?: string;
    detail?: string;
  } | string>;
  llm_logs?: Array<Record<string, unknown>>;
  pending_failed_commands?: string[];
}
