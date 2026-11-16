import React, { useEffect, useState } from 'react';

type ConnectionState = 'loading' | 'connected' | 'disconnected';

interface HealthResponse {
  status: string;
  version?: string;
  environment?: string;
}

export function getHealthUrl(
  apiBaseUrl: string | undefined = import.meta.env.VITE_API_BASE_URL,
): string {
  const trimmed = apiBaseUrl?.trim();
  if (!trimmed) {
    return '/healthz';
  }
  const baseRoot = trimmed.replace(/\/api\/v1\/?$/, '').replace(/\/+$/, '');
  return `${baseRoot}/healthz`;
}

export const BackendStatus: React.FC = () => {
  const [state, setState] = useState<ConnectionState>('loading');
  const [details, setDetails] = useState<string>('Checking backend connection...');

  const checkHealth = async (): Promise<void> => {
    setState('loading');
    setDetails('Checking backend connection...');
    try {
      const res = await fetch(getHealthUrl());
      if (res.ok) {
        const data = (await res.json()) as HealthResponse;
        setState('connected');
        setDetails(`API connected (${data.status})`);
      } else {
        setState('disconnected');
        setDetails(`API returned HTTP ${res.status}`);
      }
    } catch {
      setState('disconnected');
      setDetails('Backend API offline or unreachable');
    }
  };

  useEffect(() => {
    void checkHealth();
  }, []);

  return (
    <div
      className={`backend-status backend-status--${state}`}
      role="status"
      aria-live="polite"
      title={details}
    >
      <span className="backend-status-dot" aria-hidden="true" />
      <span className="backend-status-label">
        {state === 'loading' && 'API Connecting...'}
        {state === 'connected' && 'API Connected'}
        {state === 'disconnected' && 'API Offline'}
      </span>
      <button
        type="button"
        className="backend-status-retry"
        onClick={() => void checkHealth()}
        aria-label="Retry backend connection check"
        title="Retry connection check"
      >
        ↻
      </button>
    </div>
  );
};
