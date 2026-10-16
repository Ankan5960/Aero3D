import { describe, expect, it } from 'vitest';
import { parseServerMessage, setSensitivityCommand } from './gestureProtocol';

const base = { protocol_version: 1, timestamp_ms: 1 };
const gesture = {
  ...base, type: 'gesture', seq: 1, gesture: 'rotate', phase: 'update', hand: 'right',
  confidence: 0.9, position: { x: 0.5, y: 0.5 }, delta: { x: 0.01, y: 0 }, scale_delta: null,
};

describe('parseServerMessage', () => {
  it('accepts every valid message type', () => {
    const msgs = [
      { ...base, type: 'hello', service: 'gesture-3d-viewer' },
      { ...base, type: 'status', camera: 'ready', tracking: 'tracking', enabled: true, message: null },
      gesture,
      { ...base, type: 'error', code: 'X', message: 'm', recoverable: true },
      { ...base, type: 'ack', command: 'ping', ok: true, message: null },
      { ...base, type: 'pong', client_timestamp_ms: null },
    ];
    for (const m of msgs) expect(parseServerMessage(JSON.stringify(m))?.type).toBe(m.type);
  });

  it('rejects malformed JSON, non-objects and unknown types', () => {
    expect(parseServerMessage('{nope')).toBeNull();
    expect(parseServerMessage('[]')).toBeNull();
    expect(parseServerMessage(42)).toBeNull();
    expect(parseServerMessage({ ...base, type: 'surprise' })).toBeNull();
  });

  it('rejects bad field types and out-of-set enums', () => {
    expect(parseServerMessage({ ...gesture, seq: '1' })).toBeNull();
    expect(parseServerMessage({ ...gesture, gesture: 'fly' })).toBeNull();
    expect(parseServerMessage({ ...gesture, phase: 'middle' })).toBeNull();
    expect(parseServerMessage({ ...gesture, delta: { x: 'a', y: 0 } })).toBeNull();
    expect(parseServerMessage({ ...gesture, position: null })).toBeNull();
    expect(parseServerMessage({ ...gesture, scale_delta: 'big' })).toBeNull();
    expect(parseServerMessage({ ...base, type: 'status', camera: 'ready', tracking: 'dancing', enabled: true })).toBeNull();
  });

  it('rejects missing required fields and non-finite numbers', () => {
    const { confidence: _c, ...missing } = gesture;
    expect(parseServerMessage(missing)).toBeNull();
    expect(parseServerMessage({ ...gesture, confidence: Number.NaN })).toBeNull();
    expect(parseServerMessage({ ...gesture, delta: { x: Infinity, y: 0 } })).toBeNull();
    expect(parseServerMessage({ type: 'status', camera: 'ready' })).toBeNull();
  });
});

describe('commands', () => {
  it('clamps and sanitizes sensitivity', () => {
    expect(setSensitivityCommand(9)).toMatchObject({ value: 2 });
    expect(setSensitivityCommand(0)).toMatchObject({ value: 0.25 });
    expect(setSensitivityCommand(Number.NaN)).toMatchObject({ value: 1 });
  });
});
