import type { GestureKind } from '../types/gestureProtocol';
import type { GestureSocketApi } from '../hooks/useGestureSocket';
import { SENSITIVITY_MAX, SENSITIVITY_MIN } from '../types/gestureProtocol';

interface Props {
  socket: GestureSocketApi;
  activeGesture: GestureKind | null;
}

const GESTURES: { id: GestureKind; icon: string; label: string; action: string }[] = [
  { id: 'rotate', icon: '🖐', label: 'Open palm', action: 'Rotate' },
  { id: 'zoom', icon: '🤏', label: 'Pinch', action: 'Zoom' },
  { id: 'pan', icon: '✊', label: 'Closed fist', action: 'Pan' },
];

const CONNECTION_LABEL = {
  disconnected: 'Off',
  connecting: 'Connecting…',
  connected: 'Connected',
  reconnecting: 'Reconnecting…',
  unsupported: 'Unsupported service version',
} as const;

function tone(ok: boolean, warn = false): string {
  return ok ? 'dot-ok' : warn ? 'dot-warn' : 'dot-off';
}

export function GestureStatus({ socket, activeGesture }: Props) {
  const { connection, status, error, trackingRequested } = socket;
  const connected = connection === 'connected';
  const camera = status?.camera ?? null;
  const tracking = status?.tracking ?? null;

  return (
    <section className="panel" aria-labelledby="gesture-heading">
      <h2 id="gesture-heading" className="panel-title">Hand tracking</h2>

      <ul className="status-list" aria-live="polite" id="gesture-status">
        <li>
          <span className={`dot ${tone(connected, connection === 'connecting' || connection === 'reconnecting')}`} />
          <span className="status-key">Service</span>
          <span className="status-val" id="status-connection">{CONNECTION_LABEL[connection]}</span>
        </li>
        <li>
          <span className={`dot ${tone(camera === 'ready', camera === 'starting')}`} />
          <span className="status-key">Camera</span>
          <span className="status-val" id="status-camera">{camera ?? '—'}</span>
        </li>
        <li>
          <span className={`dot ${tone(tracking === 'tracking', tracking === 'searching' || tracking === 'lost')}`} />
          <span className="status-key">Hand</span>
          <span className="status-val" id="status-tracking">{tracking ?? '—'}</span>
        </li>
      </ul>

      {status?.message && <p className="notice notice-warn">{status.message}</p>}
      {error && (
        <p className="notice notice-error" role="alert" id="gesture-error">
          {error.message}
        </p>
      )}
      {trackingRequested && connection === 'reconnecting' && (
        <p className="notice notice-info">
          Can’t reach the gesture service at 127.0.0.1:8000. Mouse and touch controls still work.
        </p>
      )}

      <ul className="gesture-legend" aria-label="Gesture mapping">
        {GESTURES.map((g) => (
          <li key={g.id} className={activeGesture === g.id ? 'is-active' : ''} id={`gesture-${g.id}`}>
            <span className="gesture-emoji" aria-hidden="true">{g.icon}</span>
            <span className="gesture-name">{g.label}</span>
            <span className="gesture-action">{g.action}</span>
          </li>
        ))}
      </ul>

      <label className="slider" htmlFor="sensitivity-slider">
        <span className="slider-head">
          <span>Sensitivity</span>
          <output id="sensitivity-value">{socket.sensitivity.toFixed(2)}×</output>
        </span>
        <input
          id="sensitivity-slider"
          type="range"
          min={SENSITIVITY_MIN}
          max={SENSITIVITY_MAX}
          step={0.05}
          value={socket.sensitivity}
          onChange={(e) => socket.setSensitivity(Number(e.target.value))}
        />
      </label>
    </section>
  );
}
