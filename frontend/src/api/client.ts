import type { components } from '../types/api.generated';

export type ProfileSummary = components['schemas']['ProfileSummary'];
export type ProfileResetResponse = components['schemas']['ProfileResetResponse'];
export type CategorySummary = components['schemas']['CategorySummary'];
export type MerchantSummary = components['schemas']['MerchantSummary'];
export type RewardCurrencySummary = components['schemas']['RewardCurrencySummary'];
export type CurrencyValuationSummary = components['schemas']['CurrencyValuationSummary'];
export type CurrencyValuationUpdate = components['schemas']['CurrencyValuationUpdate'];
export type CardProductSummary = components['schemas']['CardProductSummary'];
export type EarningRuleSummary = components['schemas']['EarningRuleSummary'];
export type ProfileCardCreate = components['schemas']['ProfileCardCreate'];
export type ProfileCardSummary = components['schemas']['ProfileCardSummary'];
export type ProfileCardUpdate = components['schemas']['ProfileCardUpdate'];
export type RecommendationRequest = components['schemas']['RecommendationRequest'];
export type RecommendationResponse = components['schemas']['RecommendationResponse'];
export type CardRecommendationItem = components['schemas']['CardRecommendationItem'];
export type AppliedPortionSchema = components['schemas']['AppliedPortionSchema'];
export type BenefitStatusItem = components['schemas']['BenefitStatusItem'];
export type BenefitUsageCreate = components['schemas']['BenefitUsageCreate'];
export type BenefitUsageSummary = components['schemas']['BenefitUsageSummary'];
export type RewardsSummaryResponse = components['schemas']['RewardsSummaryResponse'];
export type TransactionCreate = components['schemas']['TransactionCreate'];
export type TransactionSummary = components['schemas']['TransactionSummary'];
export type TransactionRewardCalcSummary = components['schemas']['TransactionRewardCalcSummary'];

export interface TransactionFilters {
  profile_card_id?: number;
  category_code?: string;
  date_from?: string;
  date_to?: string;
}

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

export async function fetchProfileCards(
  profileKey: string,
  baseUrl?: string,
): Promise<ProfileCardSummary[]> {
  return apiRequest<ProfileCardSummary[]>(
    `/profiles/${encodeURIComponent(profileKey)}/cards`,
    { method: 'GET' },
    baseUrl,
  );
}

export async function fetchProfileBenefits(
  profileKey: string,
  baseUrl?: string,
): Promise<BenefitStatusItem[]> {
  return apiRequest<BenefitStatusItem[]>(
    `/profiles/${encodeURIComponent(profileKey)}/benefits`,
    { method: 'GET' },
    baseUrl,
  );
}

export async function fetchRewardsSummary(
  profileKey: string,
  baseUrl?: string,
): Promise<RewardsSummaryResponse> {
  return apiRequest<RewardsSummaryResponse>(
    `/profiles/${encodeURIComponent(profileKey)}/rewards/summary`,
    { method: 'GET' },
    baseUrl,
  );
}

export async function fetchCardProducts(baseUrl?: string): Promise<CardProductSummary[]> {
  return apiRequest<CardProductSummary[]>('/card-products', { method: 'GET' }, baseUrl);
}

export async function fetchCardProductRules(
  cardProductId: number,
  baseUrl?: string,
): Promise<EarningRuleSummary[]> {
  return apiRequest<EarningRuleSummary[]>(
    `/card-products/${encodeURIComponent(String(cardProductId))}/rules`,
    { method: 'GET' },
    baseUrl,
  );
}

export async function addProfileCard(
  profileKey: string,
  payload: ProfileCardCreate,
  baseUrl?: string,
): Promise<ProfileCardSummary> {
  return apiRequest<ProfileCardSummary>(
    `/profiles/${encodeURIComponent(profileKey)}/cards`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    baseUrl,
  );
}

export async function updateProfileCard(
  profileKey: string,
  cardId: number,
  payload: ProfileCardUpdate,
  baseUrl?: string,
): Promise<ProfileCardSummary> {
  return apiRequest<ProfileCardSummary>(
    `/profiles/${encodeURIComponent(profileKey)}/cards/${encodeURIComponent(String(cardId))}`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
    baseUrl,
  );
}

export async function deleteProfileCard(
  profileKey: string,
  cardId: number,
  baseUrl?: string,
): Promise<void> {
  return apiRequest<void>(
    `/profiles/${encodeURIComponent(profileKey)}/cards/${encodeURIComponent(String(cardId))}`,
    { method: 'DELETE' },
    baseUrl,
  );
}

export async function fetchCategories(baseUrl?: string): Promise<CategorySummary[]> {
  return apiRequest<CategorySummary[]>('/categories', { method: 'GET' }, baseUrl);
}

export async function fetchMerchants(baseUrl?: string): Promise<MerchantSummary[]> {
  return apiRequest<MerchantSummary[]>('/merchants', { method: 'GET' }, baseUrl);
}

export async function recommendCards(
  profileKey: string,
  payload: RecommendationRequest,
  baseUrl?: string,
): Promise<RecommendationResponse> {
  return apiRequest<RecommendationResponse>(
    `/profiles/${encodeURIComponent(profileKey)}/recommendations`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    baseUrl,
  );
}

export async function fetchRewardCurrencies(baseUrl?: string): Promise<RewardCurrencySummary[]> {
  return apiRequest<RewardCurrencySummary[]>('/reward-currencies', { method: 'GET' }, baseUrl);
}

export async function fetchProfileValuations(
  profileKey: string,
  baseUrl?: string,
): Promise<CurrencyValuationSummary[]> {
  return apiRequest<CurrencyValuationSummary[]>(
    `/profiles/${encodeURIComponent(profileKey)}/valuations`,
    { method: 'GET' },
    baseUrl,
  );
}

export async function upsertProfileValuation(
  profileKey: string,
  currencyKey: string,
  payload: CurrencyValuationUpdate,
  baseUrl?: string,
): Promise<CurrencyValuationSummary> {
  return apiRequest<CurrencyValuationSummary>(
    `/profiles/${encodeURIComponent(profileKey)}/valuations/${encodeURIComponent(currencyKey)}`,
    {
      method: 'PUT',
      body: JSON.stringify({ cents_per_unit: String(payload.cents_per_unit) }),
    },
    baseUrl,
  );
}

export async function fetchProfileTransactions(
  profileKey: string,
  filters?: TransactionFilters,
  baseUrl?: string,
): Promise<TransactionSummary[]> {
  const params = new URLSearchParams();
  if (filters?.profile_card_id !== undefined) {
    params.set('profile_card_id', String(filters.profile_card_id));
  }
  if (filters?.category_code) {
    params.set('category_code', filters.category_code);
  }
  if (filters?.date_from) {
    params.set('date_from', filters.date_from);
  }
  if (filters?.date_to) {
    params.set('date_to', filters.date_to);
  }
  const qs = params.toString();
  const path = `/profiles/${encodeURIComponent(profileKey)}/transactions${qs ? `?${qs}` : ''}`;
  return apiRequest<TransactionSummary[]>(path, { method: 'GET' }, baseUrl);
}

export async function createProfileTransaction(
  profileKey: string,
  payload: TransactionCreate,
  baseUrl?: string,
): Promise<TransactionSummary> {
  return apiRequest<TransactionSummary>(
    `/profiles/${encodeURIComponent(profileKey)}/transactions`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    baseUrl,
  );
}

export async function deleteProfileTransaction(
  profileKey: string,
  transactionId: number,
  baseUrl?: string,
): Promise<void> {
  return apiRequest<void>(
    `/profiles/${encodeURIComponent(profileKey)}/transactions/${encodeURIComponent(String(transactionId))}`,
    { method: 'DELETE' },
    baseUrl,
  );
}

export async function logBenefitUsage(
  profileKey: string,
  benefitId: number,
  payload: BenefitUsageCreate,
  baseUrl?: string,
): Promise<BenefitUsageSummary> {
  return apiRequest<BenefitUsageSummary>(
    `/profiles/${encodeURIComponent(profileKey)}/benefits/${encodeURIComponent(String(benefitId))}/usages`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    baseUrl,
  );
}

export async function deleteBenefitUsage(
  profileKey: string,
  benefitId: number,
  usageId: number,
  baseUrl?: string,
): Promise<void> {
  return apiRequest<void>(
    `/profiles/${encodeURIComponent(profileKey)}/benefits/${encodeURIComponent(String(benefitId))}/usages/${encodeURIComponent(String(usageId))}`,
    { method: 'DELETE' },
    baseUrl,
  );
}
