import type { components } from '../types/api.generated';

export type ProfileSummary = components['schemas']['ProfileSummary'];
export type ProfileResetResponse = components['schemas']['ProfileResetResponse'];

export interface ValidationErrorDetail {
  loc: string[];
  msg: string;
  type: string;
}

export interface ProblemDetailsPayload {
  type?: string;
  title?: string;
  status?: number;
  detail?: string | null;
  instance?: string | null;
  errors?: ValidationErrorDetail[] | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly title: string;
  readonly detail: string | null;
  readonly type: string;
  readonly instance: string | null;
  readonly errors: ValidationErrorDetail[] | null;

  constructor(status: number, problem?: ProblemDetailsPayload) {
    const title = problem?.title ?? `HTTP ${status}`;
    const detail = problem?.detail ?? null;
    super(detail ? `${title}: ${detail}` : title);
    this.name = 'ApiError';
    this.status = problem?.status ?? status;
    this.title = title;
    this.detail = detail;
    this.type = problem?.type ?? 'about:blank';
    this.instance = problem?.instance ?? null;
    this.errors = problem?.errors ?? null;
  }
}

export function getApiBaseUrl(
  configuredBaseUrl: string | undefined = import.meta.env.VITE_API_BASE_URL,
): string {
  const trimmed = configuredBaseUrl?.trim();
  if (!trimmed) {
    return '/api/v1';
  }
  const normalized = trimmed.replace(/\/+$/, '');
  return normalized.endsWith('/api/v1') ? normalized : `${normalized}/api/v1`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function parseValidationErrors(raw: unknown): ValidationErrorDetail[] | null {
  if (!Array.isArray(raw)) {
    return null;
  }
  const parsed: ValidationErrorDetail[] = [];
  for (const item of raw) {
    if (!isRecord(item)) {
      continue;
    }
    const loc = Array.isArray(item.loc) ? item.loc.map((part) => String(part)) : [];
    const msg = typeof item.msg === 'string' ? item.msg : '';
    const type = typeof item.type === 'string' ? item.type : '';
    parsed.push({ loc, msg, type });
  }
  return parsed;
}

function parseProblemDetails(raw: unknown): ProblemDetailsPayload | undefined {
  if (!isRecord(raw)) {
    return undefined;
  }
  return {
    type: typeof raw.type === 'string' ? raw.type : undefined,
    title: typeof raw.title === 'string' ? raw.title : undefined,
    status: typeof raw.status === 'number' ? raw.status : undefined,
    detail: typeof raw.detail === 'string' ? raw.detail : null,
    instance: typeof raw.instance === 'string' ? raw.instance : null,
    errors: parseValidationErrors(raw.errors),
  };
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  baseUrl?: string,
): Promise<T> {
  const url = `${getApiBaseUrl(baseUrl)}${path}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let problem: ProblemDetailsPayload | undefined;
    try {
      const payload: unknown = await response.json();
      problem = parseProblemDetails(payload);
    } catch {
      problem = undefined;
    }
    throw new ApiError(response.status, problem);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function fetchProfiles(baseUrl?: string): Promise<ProfileSummary[]> {
  return apiRequest<ProfileSummary[]>('/profiles', { method: 'GET' }, baseUrl);
}

export async function resetProfile(
  profileKey: string,
  baseUrl?: string,
): Promise<ProfileResetResponse> {
  return apiRequest<ProfileResetResponse>(
    `/profiles/${encodeURIComponent(profileKey)}/reset`,
    { method: 'POST' },
    baseUrl,
  );
}
