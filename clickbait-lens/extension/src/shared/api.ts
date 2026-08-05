import {
  type Analysis,
  type AuthorDetail,
  type Claim,
  DEFAULT_SETTINGS,
  type PageExtract,
  type Resolution,
  type Settings,
  type Verification,
} from "./types";

export async function getSettings(): Promise<Settings> {
  try {
    const stored = await chrome.storage.local.get(DEFAULT_SETTINGS);
    return { ...DEFAULT_SETTINGS, ...stored } as Settings;
  } catch {
    // Storage is unavailable in plain page contexts (e.g. unit tests).
    return DEFAULT_SETTINGS;
  }
}

export async function saveSettings(patch: Partial<Settings>): Promise<Settings> {
  const next = { ...(await getSettings()), ...patch };
  await chrome.storage.local.set(next);
  return next;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { apiBase } = await getSettings();
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (cause) {
    throw new ApiError(
      `Cannot reach the Clickbait Lens API at ${apiBase}. Is the backend running?`,
      0,
    );
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new ApiError(detail || `${response.status} ${response.statusText}`, response.status);
  }
  return (await response.json()) as T;
}

export function analyze(extract: PageExtract): Promise<Analysis> {
  const { isArticle: _isArticle, ...payload } = extract;
  return request<Analysis>("/api/v1/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAuthor(authorId: number): Promise<AuthorDetail> {
  return request<AuthorDetail>(`/api/v1/authors/${authorId}`);
}

export function verifyClaim(claimId: number, apply = false): Promise<Verification> {
  return request<Verification>(`/api/v1/claims/${claimId}/verify`, {
    method: "POST",
    body: JSON.stringify({ apply }),
  });
}

export function setResolution(
  claimId: number,
  resolution: Resolution,
  notes?: string,
): Promise<Claim> {
  return request<Claim>(`/api/v1/claims/${claimId}/resolution`, {
    method: "POST",
    body: JSON.stringify({ resolution, notes: notes ?? null }),
  });
}
