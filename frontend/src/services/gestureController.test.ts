import { describe, expect, it } from 'vitest';
import { GestureController, MAX_ZOOM_STEP } from './gestureController';
import type { GestureMessage, StatusMessage } from '../types/gestureProtocol';

let seq = 0;
const g = (over: Partial<GestureMessage>): GestureMessage => ({
  type: 'gesture', protocol_version: 1, seq: ++seq, timestamp_ms: 0, gesture: 'rotate', phase: 'update',
  hand: 'right', confidence: 1, position: { x: 0.5, y: 0.5 }, delta: { x: 0.01, y: 0.02 }, scale_delta: null,
  ...over,
});
const status = (tracking: StatusMessage['tracking']): StatusMessage => ({
  type: 'status', protocol_version: 1, timestamp_ms: 0, camera: 'ready', tracking, enabled: true, message: null,
});

describe('GestureController', () => {
  it('ignores updates before start and accumulates after start', () => {
    const c = new GestureController();
    c.handleGesture(g({}));
    expect(c.consume()).toBeNull();
    c.handleGesture(g({ phase: 'start', delta: { x: 0, y: 0 } }));
    c.handleGesture(g({}));
    c.handleGesture(g({}));
    const m = c.consume()!;
    expect(m.rotateX).toBeCloseTo(0.02);
    expect(m.rotateY).toBeCloseTo(0.04);
    expect(c.consume()).toBeNull();
  });

  it('applies no movement from start/end events and none after end', () => {
    const c = new GestureController();
    c.handleGesture(g({ phase: 'start', delta: { x: 0.2, y: 0.2 } }));
    expect(c.consume()).toBeNull();
    c.handleGesture(g({}));
    c.handleGesture(g({ phase: 'end' }));
    expect(c.consume()).toBeNull(); // pending cleared on end
    c.handleGesture(g({}));
    expect(c.consume()).toBeNull();
    expect(c.activeGesture).toBeNull();
  });

  it('drops stale and duplicate sequence numbers', () => {
    const c = new GestureController();
    c.handleGesture(g({ phase: 'start', seq: 100 }));
    c.handleGesture(g({ seq: 101 }));
    c.handleGesture(g({ seq: 101 }));
    c.handleGesture(g({ seq: 50 }));
    expect(c.consume()!.rotateX).toBeCloseTo(0.01);
  });

  it('only applies updates matching the active gesture', () => {
    const c = new GestureController();
    c.handleGesture(g({ phase: 'start', gesture: 'pan' }));
    c.handleGesture(g({ gesture: 'rotate' }));
    expect(c.consume()).toBeNull();
    c.handleGesture(g({ gesture: 'pan' }));
    expect(c.consume()).toMatchObject({ panX: 0.01, panY: 0.02, rotateX: 0 });
  });

  it('clamps extreme zoom and ignores non-finite or invalid scale', () => {
    const c = new GestureController();
    c.handleGesture(g({ phase: 'start', gesture: 'zoom' }));
    c.handleGesture(g({ gesture: 'zoom', scale_delta: 50, delta: { x: 0, y: 0 } }));
    expect(c.consume()!.zoom).toBeCloseTo(MAX_ZOOM_STEP);
    c.handleGesture(g({ gesture: 'zoom', scale_delta: 0.0001 }));
    expect(c.consume()!.zoom).toBeCloseTo(1 / MAX_ZOOM_STEP);
    c.handleGesture(g({ gesture: 'zoom', scale_delta: Number.NaN }));
    c.handleGesture(g({ gesture: 'zoom', scale_delta: -2 }));
    c.handleGesture(g({ gesture: 'zoom', scale_delta: null }));
    expect(c.consume()).toBeNull();
  });

  it('stops on tracking loss and when disabled', () => {
    const c = new GestureController();
    c.handleGesture(g({ phase: 'start' }));
    c.handleGesture(g({}));
    c.handleStatus(status('lost'));
    expect(c.consume()).toBeNull();
    expect(c.activeGesture).toBeNull();
    c.handleGesture(g({ phase: 'start' }));
    c.setEnabled(false);
    c.handleGesture(g({}));
    expect(c.consume()).toBeNull();
  });

  it('reset clears the sequence baseline so a restarted service works', () => {
    const c = new GestureController();
    c.handleGesture(g({ phase: 'start', seq: 500 }));
    c.reset();
    c.handleGesture(g({ phase: 'start', seq: 1 }));
    c.handleGesture(g({ seq: 2 }));
    expect(c.consume()).not.toBeNull();
  });

  it('notifies active gesture changes', () => {
    const seen: unknown[] = [];
    const c = new GestureController((x) => seen.push(x));
    c.handleGesture(g({ phase: 'start', gesture: 'pan' }));
    c.handleGesture(g({ phase: 'end', gesture: 'pan' }));
    expect(seen).toEqual(['pan', null]);
  });
});
