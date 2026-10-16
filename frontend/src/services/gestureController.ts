import type { GestureKind, GestureMessage, StatusMessage } from '../types/gestureProtocol';

/** Accumulated gesture motion since the last render-loop consume(). */
export interface PendingMotion {
  rotateX: number;
  rotateY: number;
  panX: number;
  panY: number;
  /** Multiplicative zoom factor (>1 zooms in). */
  zoom: number;
}

export const MAX_ZOOM_STEP = 1.1;
const MAX_DELTA = 0.25;

const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v));
const emptyMotion = (): PendingMotion => ({ rotateX: 0, rotateY: 0, panX: 0, panY: 0, zoom: 1 });

/**
 * Interprets protocol gesture events. It keeps no React state: motion is accumulated and then
 * drained once per render frame, so socket rate and render rate stay independent.
 * Movement is only accepted from `update` events of the currently active gesture.
 */
export class GestureController {
  private lastSeq = -1;
  private active: GestureKind | null = null;
  private pending: PendingMotion = emptyMotion();
  private enabled = true;

  constructor(private readonly onActiveChange?: (gesture: GestureKind | null) => void) {}

  get activeGesture(): GestureKind | null {
    return this.active;
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled) this.endActive();
  }

  /** Forget all state (reconnect, disconnect, or new service session). */
  reset(): void {
    this.lastSeq = -1;
    this.endActive();
  }

  handleGesture(msg: GestureMessage): void {
    if (msg.seq <= this.lastSeq) return; // duplicate or stale
    this.lastSeq = msg.seq;
    if (!this.enabled) return;

    if (msg.gesture === 'none') {
      this.endActive();
      return;
    }
    switch (msg.phase) {
      case 'start':
        this.pending = emptyMotion();
        this.setActive(msg.gesture);
        return;
      case 'end':
        if (this.active === msg.gesture) this.endActive();
        return;
      case 'update':
        if (this.active === msg.gesture) this.accumulate(msg);
        return;
    }
  }

  handleStatus(msg: StatusMessage): void {
    if (msg.tracking !== 'tracking') this.endActive();
  }

  /** Drain accumulated motion (null if nothing to apply). */
  consume(): PendingMotion | null {
    const p = this.pending;
    if (p.rotateX === 0 && p.rotateY === 0 && p.panX === 0 && p.panY === 0 && p.zoom === 1) return null;
    this.pending = emptyMotion();
    return p;
  }

  private accumulate(msg: GestureMessage): void {
    const p = this.pending;
    if (msg.gesture === 'zoom') {
      const s = msg.scale_delta;
      if (s === null || !Number.isFinite(s) || s <= 0) return;
      p.zoom *= clamp(s, 1 / MAX_ZOOM_STEP, MAX_ZOOM_STEP);
      return;
    }
    const dx = clamp(msg.delta.x, -MAX_DELTA, MAX_DELTA);
    const dy = clamp(msg.delta.y, -MAX_DELTA, MAX_DELTA);
    if (msg.gesture === 'rotate') {
      p.rotateX += dx;
      p.rotateY += dy;
    } else if (msg.gesture === 'pan') {
      p.panX += dx;
      p.panY += dy;
    }
  }

  private endActive(): void {
    this.pending = emptyMotion();
    this.setActive(null);
  }

  private setActive(g: GestureKind | null): void {
    if (this.active === g) return;
    this.active = g;
    this.onActiveChange?.(g);
  }
}
