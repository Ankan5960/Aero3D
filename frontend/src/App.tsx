import { useCallback, useEffect, useMemo, useState } from 'react';
import { GestureStatus } from './components/GestureStatus';
import { ModelUploader } from './components/ModelUploader';
import { ModelViewer } from './components/ModelViewer';
import { ViewerToolbar } from './components/ViewerToolbar';
import { useGestureSocket } from './hooks/useGestureSocket';
import { GestureController } from './services/gestureController';
import { disposeObject, loadModelFile, type LoadedModel } from './services/modelLoader';
import type { GestureKind } from './types/gestureProtocol';

export default function App() {
  const [activeGesture, setActiveGesture] = useState<GestureKind | null>(null);
  const controller = useMemo(() => new GestureController(setActiveGesture), []);
  const socket = useGestureSocket(controller);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [model, setModel] = useState<LoadedModel | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetToken, setResetToken] = useState(0);
  const [fitToken, setFitToken] = useState(0);

  // Dispose GPU resources of a model once it is replaced or the app unmounts.
  useEffect(() => {
    return () => {
      if (model) disposeObject(model.object);
    };
  }, [model]);

  const handleFile = useCallback(async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await loadModelFile(file);
      setModel(loaded);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load the model.');
    } finally {
      setLoading(false);
    }
  }, []);

  const trackingActive = socket.connection === 'connected' && socket.status?.tracking === 'tracking';

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
            <defs>
              <linearGradient id="brand-grad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#39e1ff" />
                <stop offset="1" stopColor="#8b5cf6" />
              </linearGradient>
            </defs>
            <path d="M16 3l11 6.500v13L16 29 5 22.500v-13z" fill="none" stroke="url(#brand-grad)" strokeWidth="2.400" strokeLinejoin="round" />
            <path d="M5 9.500 16 16l11-6.500M16 16v13" fill="none" stroke="url(#brand-grad)" strokeWidth="1.600" strokeLinejoin="round" opacity="0.7" />
          </svg>
          <h1>Aero<span>3D</span></h1>
        </div>
        <p className="tagline">Inspect 3D models with your hands — or your mouse.</p>
        <div className="header-controls">
          <label className="switch" htmlFor="sidebar-switch" title={sidebarOpen ? 'Hide sidebar (Full screen viewer)' : 'Show sidebar'}>
            <span className="switch-label">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect width="18" height="18" x="3" y="3" rx="2" />
                <path d="M9 3v18" />
              </svg>
              <span>Sidebar</span>
            </span>
            <input
              id="sidebar-switch"
              type="checkbox"
              role="switch"
              checked={sidebarOpen}
              onChange={(e) => setSidebarOpen(e.target.checked)}
              aria-controls="sidebar"
            />
            <span className="switch-track" aria-hidden="true">
              <span className="switch-thumb" />
            </span>
          </label>
        </div>
      </header>

      <main className={`app-main${sidebarOpen ? '' : ' is-fullscreen'}`}>
        <aside className="sidebar" id="sidebar" aria-hidden={!sidebarOpen}>
          <ModelUploader
            onFile={handleFile}
            loading={loading}
            error={error}
            warnings={model?.warnings ?? []}
            fileName={model?.name ?? null}
          />
          <GestureStatus socket={socket} activeGesture={activeGesture} />
        </aside>

        <section className="viewer" aria-label="Viewer">
          <ModelViewer model={model} controller={controller} resetToken={resetToken} fitToken={fitToken} />

          {!model && !loading && (
            <div className="empty-state" id="empty-state">
              <p className="empty-title">No model loaded</p>
              <p>Showing a demo shape. Choose or drop an STL, OBJ, GLB or glTF file to begin.</p>
            </div>
          )}
          {loading && (
            <div className="loading-overlay" role="status" aria-live="polite">
              <span className="spinner" /> Loading model…
            </div>
          )}
          {activeGesture && (
            <div className="gesture-hud" id="gesture-hud" aria-live="polite">
              <span className="pulse is-live" /> {activeGesture}
            </div>
          )}

          <ViewerToolbar
            sidebarOpen={sidebarOpen}
            onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
            trackingRequested={socket.trackingRequested}
            trackingActive={trackingActive}
            onToggleTracking={socket.setTrackingRequested}
            onReset={() => setResetToken((n) => n + 1)}
            onFit={() => setFitToken((n) => n + 1)}
          />
        </section>
      </main>
    </div>
  );
}
