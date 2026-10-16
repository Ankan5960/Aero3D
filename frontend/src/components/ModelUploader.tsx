import { useRef, useState } from 'react';
import { SUPPORTED_EXTENSIONS } from '../services/modelLoader';

interface Props {
  onFile: (file: File) => void;
  loading: boolean;
  error: string | null;
  warnings: string[];
  fileName: string | null;
}

export function ModelUploader({ onFile, loading, error, warnings, fileName }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pick = (files: FileList | null) => {
    const f = files?.[0];
    if (f) onFile(f);
    if (inputRef.current) inputRef.current.value = ''; // allow re-selecting the same file
  };

  return (
    <section className="panel" aria-labelledby="model-heading">
      <h2 id="model-heading" className="panel-title">Model</h2>
      <div
        id="model-dropzone"
        className={`dropzone${dragging ? ' is-dragging' : ''}${loading ? ' is-loading' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pick(e.dataTransfer.files);
        }}
      >
        <div className="dropzone-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3 4 7.5v9L12 21l8-4.500v-9z" />
            <path d="m4 7.500 8 4.500 8-4.500M12 12v9" />
          </svg>
        </div>
        <p className="dropzone-text">
          {loading ? 'Loading model…' : 'Drop a 3D model here'}
        </p>
        <p className="dropzone-sub">{SUPPORTED_EXTENSIONS.map((e) => e.toUpperCase()).join(' · ')}</p>
        <button
          id="choose-model-button"
          type="button"
          className="btn btn-primary"
          onClick={() => inputRef.current?.click()}
          disabled={loading}
        >
          Choose file
        </button>
        <input
          ref={inputRef}
          id="model-file-input"
          type="file"
          hidden
          accept={SUPPORTED_EXTENSIONS.map((e) => `.${e}`).join(',')}
          onChange={(e) => pick(e.target.files)}
        />
      </div>
      <p className="hint">Files stay in your browser — nothing is uploaded.</p>
      {fileName && !error && (
        <p className="file-chip" id="loaded-file-name" title={fileName}>
          <span className="dot dot-ok" /> {fileName}
        </p>
      )}
      {error && (
        <p className="notice notice-error" role="alert" id="model-error">
          {error}
        </p>
      )}
      {warnings.map((w) => (
        <p key={w} className="notice notice-info">
          {w}
        </p>
      ))}
    </section>
  );
}
