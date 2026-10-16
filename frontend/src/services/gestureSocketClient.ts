import {
  PROTOCOL_VERSION,
  parseServerMessage,
  setEnabledCommand,
  setSensitivityCommand,
  type ClientCommand,
  type ServerMessage,
} from '../types/gestureProtocol';

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'unsupported';

/** Minimal slice of WebSocket used here (lets tests inject a fake). */
export interface SocketLike {
  readonly readyState: number;
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  onclose: ((ev: unknown) => void) | null;
  send(data: string): void;
  close(): void;
}

export interface GestureSocketOptions {
  url: string;
  onMessage: (msg: ServerMessage) => void;
  onConnectionChange: (state: ConnectionState) => void;
  createSocket?: (url: string) => SocketLike;
  baseDelayMs?: number;
  maxDelayMs?: number;
  /** Max accepted frame size in characters. */
  maxMessageChars?: number;
}

const OPEN = 1;

/**
 * Owns exactly one socket and at most one reconnect timer. Reconnects with bounded
 * exponential backoff (500 ms -> 5 s by default) until `disconnect()` is called.
 */
export class GestureSocketClient {
  private socket: SocketLike | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private wantConnected = false;
  private attempt = 0;
  private state: ConnectionState = 'disconnected';
  private readonly base: number;
  private readonly max: number;

  constructor(private readonly opts: GestureSocketOptions) {
    this.base = opts.baseDelayMs ?? 500;
    this.max = opts.maxDelayMs ?? 5000;
  }

  get connectionState(): ConnectionState {
    return this.state;
  }

  connect(): void {
    if (this.wantConnected) return; // already connecting/connected/reconnecting
    this.wantConnected = true;
    this.attempt = 0;
    this.open('connecting');
  }

  disconnect(): void {
    this.wantConnected = false;
    this.clearTimer();
    this.closeSocket();
    this.setState('disconnected');
  }

  send(cmd: ClientCommand): boolean {
    if (this.socket && this.socket.readyState === OPEN) {
      this.socket.send(JSON.stringify(cmd));
      return true;
    }
    return false;
  }

  setEnabled(enabled: boolean): boolean {
    return this.send(setEnabledCommand(enabled));
  }

  setSensitivity(value: number): boolean {
    return this.send(setSensitivityCommand(value));
  }

  // ------------------------------------------------------------------ internals

  private open(initial: ConnectionState): void {
    this.clearTimer();
    this.setState(initial);
    let sock: SocketLike;
    try {
      sock = (this.opts.createSocket ?? ((u) => new WebSocket(u) as unknown as SocketLike))(this.opts.url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = sock;
    sock.onopen = () => {
      if (this.socket !== sock) return;
      this.attempt = 0;
      this.setState('connected');
    };
    sock.onmessage = (ev) => {
      if (this.socket !== sock) return;
      if (typeof ev.data === 'string' && ev.data.length > (this.opts.maxMessageChars ?? 65536)) return;
      const msg = parseServerMessage(ev.data);
      if (!msg) return;
      if (msg.type === 'hello' && msg.protocol_version !== PROTOCOL_VERSION) {
        this.wantConnected = false;
        this.closeSocket();
        this.setState('unsupported');
        return;
      }
      this.opts.onMessage(msg);
    };
    sock.onerror = () => {
      /* close handler drives reconnect */
    };
    sock.onclose = () => {
      if (this.socket !== sock) return;
      this.socket = null;
      if (this.wantConnected) this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (!this.wantConnected || this.timer !== null) return;
    this.setState('reconnecting');
    const delay = Math.min(this.max, this.base * 2 ** this.attempt);
    this.attempt += 1;
    this.timer = setTimeout(() => {
      this.timer = null;
      if (this.wantConnected) this.open('reconnecting');
    }, delay);
  }

  private closeSocket(): void {
    const s = this.socket;
    this.socket = null; // detach first so late events are ignored
    if (s) {
      s.onopen = s.onmessage = s.onerror = s.onclose = null;
      try {
        s.close();
      } catch {
        /* already closed */
      }
    }
  }

  private clearTimer(): void {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  private setState(next: ConnectionState): void {
    if (this.state === next) return;
    this.state = next;
    this.opts.onConnectionChange(next);
  }
}
