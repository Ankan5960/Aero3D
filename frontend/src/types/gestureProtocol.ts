/**
 * Gesture WebSocket protocol v1 (see Agents/API.md). Types plus *runtime* validation:
 * network input is never trusted just because TypeScript says so.
 */

export const PROTOCOL_VERSION = 1;
export const SENSITIVITY_MIN = 0.25;
export const SENSITIVITY_MAX = 2.0;

export type CameraState = 'starting' | 'ready' | 'error' | 'stopped';
export type TrackingState = 'searching' | 'tracking' | 'lost' | 'disabled' | 'error';
export type GestureKind = 'rotate' | 'zoom' | 'pan' | 'none';
export type GesturePhase = 'start' | 'update' | 'end';
export type HandLabel = 'left' | 'right' | 'unknown';

export interface HelloMessage {
  type: 'hello';
  protocol_version: number;
  service: string;
  timestamp_ms: number;
}
export interface StatusMessage {
  type: 'status';
  protocol_version: number;
  timestamp_ms: number;
  camera: CameraState;
  tracking: TrackingState;
  enabled: boolean;
  message: string | null;
}
export interface GestureMessage {
  type: 'gesture';
  protocol_version: number;
  seq: number;
  timestamp_ms: number;
  gesture: GestureKind;
  phase: GesturePhase;
  hand: HandLabel;
  confidence: number;
  position: { x: number; y: number };
  delta: { x: number; y: number };
  scale_delta: number | null;
}
export interface ErrorMessage {
  type: 'error';
  protocol_version: number;
  timestamp_ms: number;
  code: string;
  message: string;
  recoverable: boolean;
}
export interface AckMessage {
  type: 'ack';
  protocol_version: number;
  timestamp_ms: number;
  command: string;
  ok: boolean;
  message: string | null;
}
export interface PongMessage {
  type: 'pong';
  protocol_version: number;
  timestamp_ms: number;
  client_timestamp_ms: number | null;
}

export type ServerMessage =
  | HelloMessage
  | StatusMessage
  | GestureMessage
  | ErrorMessage
  | AckMessage
  | PongMessage;

export type ClientCommand =
  | { type: 'command'; protocol_version: 1; command: 'set_enabled'; enabled: boolean }
  | { type: 'command'; protocol_version: 1; command: 'set_sensitivity'; value: number }
  | { type: 'command'; protocol_version: 1; command: 'ping'; timestamp_ms: number };

const CAMERA_STATES: readonly string[] = ['starting', 'ready', 'error', 'stopped'];
const TRACKING_STATES: readonly string[] = ['searching', 'tracking', 'lost', 'disabled', 'error'];
const GESTURES: readonly string[] = ['rotate', 'zoom', 'pan', 'none'];
const PHASES: readonly string[] = ['start', 'update', 'end'];
const HANDS: readonly string[] = ['left', 'right', 'unknown'];

type Rec = Record<string, unknown>;

const isRec = (v: unknown): v is Rec => typeof v === 'object' && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const isStrOrNull = (v: unknown): v is string | null => v === null || typeof v === 'string';
const isXY = (v: unknown): v is { x: number; y: number } =>
  isRec(v) && isNum(v.x) && isNum(v.y);

/** Parse and validate a server frame. Returns null for anything malformed or unknown. */
export function parseServerMessage(raw: unknown): ServerMessage | null {
  let data: unknown = raw;
  if (typeof raw === 'string') {
    try {
      data = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (!isRec(data) || typeof data.type !== 'string') return null;
  if (!isNum(data.protocol_version) && data.type !== 'hello') return null;
  if (!isNum(data.timestamp_ms) && data.type !== 'gesture') return null;

  switch (data.type) {
    case 'hello':
      if (!isNum(data.protocol_version) || typeof data.service !== 'string' || !isNum(data.timestamp_ms)) {
        return null;
      }
      return data as unknown as HelloMessage;
    case 'status':
      if (
        typeof data.camera !== 'string' || !CAMERA_STATES.includes(data.camera) ||
        typeof data.tracking !== 'string' || !TRACKING_STATES.includes(data.tracking) ||
        typeof data.enabled !== 'boolean' || !isStrOrNull(data.message ?? null)
      ) {
        return null;
      }
      return { ...data, message: data.message ?? null } as unknown as StatusMessage;
    case 'gesture': {
      if (
        !isNum(data.seq) || !isNum(data.timestamp_ms) ||
        typeof data.gesture !== 'string' || !GESTURES.includes(data.gesture) ||
        typeof data.phase !== 'string' || !PHASES.includes(data.phase) ||
        typeof data.hand !== 'string' || !HANDS.includes(data.hand) ||
        !isNum(data.confidence) || !isXY(data.position) || !isXY(data.delta)
      ) {
        return null;
      }
      const scale = data.scale_delta;
      if (scale !== null && !isNum(scale)) return null;
      return { ...data, scale_delta: scale } as unknown as GestureMessage;
    }
    case 'error':
      if (typeof data.code !== 'string' || typeof data.message !== 'string' || typeof data.recoverable !== 'boolean') {
        return null;
      }
      return data as unknown as ErrorMessage;
    case 'ack':
      if (typeof data.command !== 'string' || typeof data.ok !== 'boolean' || !isStrOrNull(data.message ?? null)) {
        return null;
      }
      return { ...data, message: data.message ?? null } as unknown as AckMessage;
    case 'pong': {
      const c = data.client_timestamp_ms ?? null;
      if (c !== null && !isNum(c)) return null;
      return { ...data, client_timestamp_ms: c } as unknown as PongMessage;
    }
    default:
      return null;
  }
}

export const setEnabledCommand = (enabled: boolean): ClientCommand => ({
  type: 'command',
  protocol_version: PROTOCOL_VERSION,
  command: 'set_enabled',
  enabled,
});

export const setSensitivityCommand = (value: number): ClientCommand => ({
  type: 'command',
  protocol_version: PROTOCOL_VERSION,
  command: 'set_sensitivity',
  value: Math.min(SENSITIVITY_MAX, Math.max(SENSITIVITY_MIN, Number.isFinite(value) ? value : 1)),
});

export const pingCommand = (timestampMs: number): ClientCommand => ({
  type: 'command',
  protocol_version: PROTOCOL_VERSION,
  command: 'ping',
  timestamp_ms: timestampMs,
});
