import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GestureSocketClient, type ConnectionState, type SocketLike } from './gestureSocketClient';
import type { ServerMessage } from '../types/gestureProtocol';

class FakeSocket implements SocketLike {
  static instances: FakeSocket[] = [];
  readyState = 0;
  onopen: SocketLike['onopen'] = null;
  onmessage: SocketLike['onmessage'] = null;
  onerror: SocketLike['onerror'] = null;
  onclose: SocketLike['onclose'] = null;
  sent: string[] = [];
  closed = false;
  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }
  send(d: string) { this.sent.push(d); }
  close() { this.closed = true; this.readyState = 3; }
  open() { this.readyState = 1; this.onopen?.({}); }
  recv(data: unknown) { this.onmessage?.({ data: typeof data === 'string' ? data : JSON.stringify(data) }); }
  drop() { this.readyState = 3; this.onclose?.({}); }
}

function setup() {
  const states: ConnectionState[] = [];
  const msgs: ServerMessage[] = [];
  const client = new GestureSocketClient({
    url: 'ws://test',
    onConnectionChange: (s) => states.push(s),
    onMessage: (m) => msgs.push(m),
    createSocket: (u) => new FakeSocket(u),
  });
  return { client, states, msgs };
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.instances = [];
});
afterEach(() => vi.useRealTimers());

describe('GestureSocketClient', () => {
  it('connects once even if connect() is called repeatedly', () => {
    const { client } = setup();
    client.connect();
    client.connect();
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it('reports connected and forwards valid messages, ignoring invalid ones', () => {
    const { client, states, msgs } = setup();
    client.connect();
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].recv({ type: 'hello', protocol_version: 1, service: 's', timestamp_ms: 1 });
    FakeSocket.instances[0].recv('garbage');
    FakeSocket.instances[0].recv({ type: 'unknown', protocol_version: 1, timestamp_ms: 1 });
    expect(states).toEqual(['connecting', 'connected']);
    expect(msgs.map((m) => m.type)).toEqual(['hello']);
  });

  it('reconnects with bounded exponential backoff and a single timer', () => {
    const { client, states } = setup();
    client.connect();
    const delays: number[] = [];
    for (let i = 0; i < 7; i++) {
      const sock = FakeSocket.instances[FakeSocket.instances.length - 1];
      sock.drop();
      sock.drop(); // duplicate close must not create a second timer/socket
      expect(vi.getTimerCount()).toBe(1);
      const before = FakeSocket.instances.length;
      let waited = 0;
      while (FakeSocket.instances.length === before) {
        vi.advanceTimersByTime(100);
        waited += 100;
      }
      delays.push(waited);
      expect(FakeSocket.instances.length).toBe(before + 1);
    }
    expect(delays).toEqual([500, 1000, 2000, 4000, 5000, 5000, 5000]);
    expect(states).toContain('reconnecting');
  });

  it('resets backoff after a successful connection', () => {
    const { client } = setup();
    client.connect();
    FakeSocket.instances[0].drop();
    vi.advanceTimersByTime(500);
    FakeSocket.instances[1].open();
    FakeSocket.instances[1].drop();
    vi.advanceTimersByTime(499);
    expect(FakeSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.instances).toHaveLength(3);
  });

  it('disconnect closes the socket, cancels reconnect and ignores late events', () => {
    const { client, states } = setup();
    client.connect();
    const s = FakeSocket.instances[0];
    s.open();
    client.disconnect();
    expect(s.closed).toBe(true);
    s.drop();
    vi.advanceTimersByTime(60000);
    expect(FakeSocket.instances).toHaveLength(1);
    expect(vi.getTimerCount()).toBe(0);
    expect(states[states.length - 1]).toBe('disconnected');
  });

  it('closes and does not retry on unsupported protocol version', () => {
    const { client, states } = setup();
    client.connect();
    const s = FakeSocket.instances[0];
    s.open();
    s.recv({ type: 'hello', protocol_version: 2, service: 's', timestamp_ms: 1 });
    expect(s.closed).toBe(true);
    expect(states[states.length - 1]).toBe('unsupported');
    vi.advanceTimersByTime(60000);
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it('sends commands only while open', () => {
    const { client } = setup();
    client.connect();
    expect(client.setSensitivity(1.5)).toBe(false);
    FakeSocket.instances[0].open();
    expect(client.setSensitivity(1.5)).toBe(true);
    expect(client.setEnabled(false)).toBe(true);
    const sent = FakeSocket.instances[0].sent.map((x) => JSON.parse(x));
    expect(sent[0]).toMatchObject({ command: 'set_sensitivity', value: 1.5, protocol_version: 1 });
    expect(sent[1]).toMatchObject({ command: 'set_enabled', enabled: false });
  });

  it('survives a throwing socket constructor by retrying', () => {
    let calls = 0;
    const client = new GestureSocketClient({
      url: 'ws://x',
      onConnectionChange: () => {},
      onMessage: () => {},
      createSocket: (u) => {
        calls += 1;
        if (calls === 1) throw new Error('bad url');
        return new FakeSocket(u);
      },
    });
    client.connect();
    vi.advanceTimersByTime(500);
    expect(calls).toBe(2);
  });
});
