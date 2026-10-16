interface Props {
  trackingRequested: boolean;
  trackingActive: boolean;
  onToggleTracking: (on: boolean) => void;
  onReset: () => void;
  onFit: () => void;
}

export function ViewerToolbar({ trackingRequested, trackingActive, onToggleTracking, onReset, onFit }: Props) {
  return (
    <div className="toolbar" role="toolbar" aria-label="Viewer controls">
      <button id="reset-view-button" type="button" className="btn btn-ghost" onClick={onReset}>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 12a9 9 0 1 0 3-6.700L3 8" />
          <path d="M3 3v5h5" />
        </svg>
        Reset view
      </button>
      <button id="fit-model-button" type="button" className="btn btn-ghost" onClick={onFit}>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
        </svg>
        Fit model
      </button>
      <span className="toolbar-sep" aria-hidden="true" />
      <button
        id="toggle-tracking-button"
        type="button"
        className={`btn ${trackingRequested ? 'btn-live' : 'btn-primary'}`}
        aria-pressed={trackingRequested}
        onClick={() => onToggleTracking(!trackingRequested)}
      >
        <span className={`pulse${trackingActive ? ' is-live' : ''}`} aria-hidden="true" />
        {trackingRequested ? 'Disable gestures' : 'Enable gestures'}
      </button>
    </div>
  );
}
