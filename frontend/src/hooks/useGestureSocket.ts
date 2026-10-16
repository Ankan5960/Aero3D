import { useCallback, useEffect, useRef, useState } from 'react';
import type { GestureController } from '../services/gestureController';
import {
  GestureSocketClient,
  type ConnectionState,
} from '../services/gestureSocketClient';
import type { ErrorMessage, StatusMessage } from '../types/gestureProtocol';

export const DEFAULT_WS_URL = 'ws://127.0.0.1:8000/ws/gestures';

export function getGestureSocketUrl(): string {
  const env = import.meta.env.VITE_GESTURE_WS_URL as string | undefined;
  return env && env.trim() ? env.trim() : DEFAULT_WS_URL;
}

export interface GestureSocketApi {
  connection: ConnectionState;
  status: StatusMessage | null;
  error: ErrorMessage | null;
  /** Whether the user has asked for hand tracking (camera is only opened while true). */
  trackingRequested: boolean;
  setTrackingRequested: (on: boolean) => void;
  sensitivity: number;
  setSensitivity: (value: number) => void;
}

/** React wrapper around {@link GestureSocketClient}. Connects only on user request. */
export function useGestureSocket(controller: GestureController, url: string = getGestureSocketUrl()): GestureSocketApi {
  const [connection, setConnection] = useState<ConnectionState>('disconnected');
  const [status, setStatus] = useState<StatusMessage | null>(null);
  const [error, setError] = useState<ErrorMessage | null>(null);
  const [trackingRequested, setRequested] = useState(false);
  const [sensitivity, setSensitivityState] = useState(1);
  const clientRef = useRef<GestureSocketClient | null>(null);
  const sensitivityRef = useRef(sensitivity);
  sensitivityRef.current = sensitivity;

  useEffect(() => {
    const client = new GestureSocketClient({
      url,
      onConnectionChange: (state) => {
        setConnection(state);
        if (state === 'connected') {
          setError(null);
          client.setSensitivity(sensitivityRef.current);
        } else {
          controller.reset();
          setStatus(null);
        }
      },
      onMessage: (msg) => {
        switch (msg.type) {
          case 'hello':
            controller.reset(); // new service session: sequence numbers restart
            break;
          case 'status':
            setStatus(msg);
            controller.handleStatus(msg);
            break;
          case 'gesture':
            controller.handleGesture(msg);
            break;
          case 'error':
            setError(msg);
            break;
          default:
            break;
        }
      },
    });
    clientRef.current = client;
    return () => {
      client.disconnect();
      clientRef.current = null;
    };
  }, [controller, url]);

  const setTrackingRequested = useCallback((on: boolean) => {
    setRequested(on);
    if (on) {
      setError(null);
      clientRef.current?.connect();
    } else {
      clientRef.current?.disconnect();
    }
  }, []);

  const setSensitivity = useCallback((value: number) => {
    setSensitivityState(value);
    clientRef.current?.setSensitivity(value);
  }, []);

  return { connection, status, error, trackingRequested, setTrackingRequested, sensitivity, setSensitivity };
}
