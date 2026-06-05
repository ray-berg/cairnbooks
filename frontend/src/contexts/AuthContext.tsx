"use client";

/**
 * AuthContext
 *
 * Provides authentication state to the entire app:
 *  - user:    decoded JWT payload (null when logged out)
 *  - login()  calls the API, stores tokens, updates state
 *  - logout() clears tokens and redirects to /login
 *
 * Bootstrapped once on mount by reading the stored access token.
 * Keeps the rest of the component tree simple — no component needs
 * to touch localStorage or the API client directly for auth.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { authApi, tokenStorage } from "@/api/client";

// ---------------------------------------------------------------------------
// JWT payload type (claims we care about)
// ---------------------------------------------------------------------------

export interface JwtPayload {
  sub: string;           // user id
  email: string;
  organization_id: string;
  exp: number;           // unix epoch seconds
  iat: number;
}

function decodeJwt(token: string): JwtPayload | null {
  try {
    const [, payload] = token.split(".");
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

export interface AuthContextValue {
  /** Decoded access-token payload, or null if not authenticated */
  user: JwtPayload | null;
  /** True while the initial token check is running */
  isLoading: boolean;
  /** Login with email + password. Throws ApiError on failure. */
  login: (email: string, password: string) => Promise<void>;
  /** Clear tokens and redirect to /login */
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<JwtPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount: restore user from stored access token
  useEffect(() => {
    const token = tokenStorage.getAccess();
    if (token) {
      const payload = decodeJwt(token);
      // Reject if already expired
      if (payload && payload.exp * 1000 > Date.now()) {
        setUser(payload);
      } else {
        tokenStorage.clear();
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await authApi.login({ email, password });
      tokenStorage.set(tokens.access_token, tokens.refresh_token);
      const payload = decodeJwt(tokens.access_token);
      setUser(payload);
      router.push("/dashboard");
    },
    [router]
  );

  const logout = useCallback(() => {
    // Best-effort server-side logout (ignore errors)
    authApi.logout().catch(() => {});
    tokenStorage.clear();
    setUser(null);
    router.push("/login");
  }, [router]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoading, login, logout }),
    [user, isLoading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within <AuthProvider>");
  }
  return ctx;
}
