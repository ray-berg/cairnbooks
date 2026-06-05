/**
 * CairnBooks API client
 *
 * Thin fetch wrapper that:
 *  - Prefixes all requests with NEXT_PUBLIC_API_URL (defaults to http://localhost:8000/api/v1)
 *  - Attaches the JWT access token from localStorage
 *  - Returns typed responses using the { data, meta } envelope from the server
 *  - Surfaces RFC 9457 problem-detail errors as ApiError instances
 *  - Handles 401 responses by clearing the stored tokens (refresh is a TODO for the auth slice)
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ApiEnvelope<T> {
  data: T;
  meta?: {
    pagination?: {
      page: number;
      page_size: number;
      total: number;
    };
  };
}

export interface ProblemDetail {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
}

export class ApiError extends Error {
  status: number;
  problem: ProblemDetail;

  constructor(status: number, problem: ProblemDetail) {
    super(problem.detail ?? problem.title ?? `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
  }
}

// ---------------------------------------------------------------------------
// Token storage helpers
// ---------------------------------------------------------------------------

const ACCESS_TOKEN_KEY = "cairn_access";
const REFRESH_TOKEN_KEY = "cairn_refresh";

export const tokenStorage = {
  getAccess: (): string | null =>
    typeof window !== "undefined" ? localStorage.getItem(ACCESS_TOKEN_KEY) : null,

  getRefresh: (): string | null =>
    typeof window !== "undefined" ? localStorage.getItem(REFRESH_TOKEN_KEY) : null,

  set: (access: string, refresh: string): void => {
    if (typeof window === "undefined") return;
    localStorage.setItem(ACCESS_TOKEN_KEY, access);
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  },

  clear: (): void => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

// ---------------------------------------------------------------------------
// Core fetch helper
// ---------------------------------------------------------------------------

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions {
  method?: HttpMethod;
  body?: unknown;
  /** Override or append extra headers */
  headers?: Record<string, string>;
  /** Skip attaching the Authorization header (e.g. for /auth/login) */
  unauthenticated?: boolean;
}

async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, headers = {}, unauthenticated = false } = options;

  const init: RequestInit = {
    method,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...headers,
    },
  };

  if (!unauthenticated) {
    const token = tokenStorage.getAccess();
    if (token) {
      (init.headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
    }
  }

  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;
  const response = await fetch(url, init);

  if (!response.ok) {
    if (response.status === 401) {
      // Access token expired or invalid — clear storage so AuthContext can redirect
      tokenStorage.clear();
    }

    let problem: ProblemDetail = { status: response.status };
    try {
      problem = await response.json();
    } catch {
      // response body wasn't valid JSON; use the minimal problem above
    }

    throw new ApiError(response.status, problem);
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Typed convenience methods
// ---------------------------------------------------------------------------

export const apiClient = {
  get: <T>(path: string, opts?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...opts, method: "GET" }),

  post: <T>(path: string, body?: unknown, opts?: Omit<RequestOptions, "method">) =>
    request<T>(path, { ...opts, method: "POST", body }),

  put: <T>(path: string, body?: unknown, opts?: Omit<RequestOptions, "method">) =>
    request<T>(path, { ...opts, method: "PUT", body }),

  patch: <T>(path: string, body?: unknown, opts?: Omit<RequestOptions, "method">) =>
    request<T>(path, { ...opts, method: "PATCH", body }),

  delete: <T>(path: string, opts?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...opts, method: "DELETE" }),
};

// ---------------------------------------------------------------------------
// Auth-specific endpoints (unauthenticated)
// ---------------------------------------------------------------------------

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

export const authApi = {
  login: (credentials: LoginRequest) =>
    apiClient.post<TokenPair>("/auth/login", credentials, { unauthenticated: true }),

  refresh: (refreshToken: string) =>
    apiClient.post<TokenPair>(
      "/auth/refresh",
      { refresh_token: refreshToken },
      { unauthenticated: true }
    ),

  logout: () => apiClient.post<void>("/auth/logout"),
};
