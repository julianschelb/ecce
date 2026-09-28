import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, getToken, setToken } from "@/lib/api";

interface AuthState {
  token: string | null;
  isAdmin: boolean;
  checking: boolean;
  login: (password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [isAdmin, setIsAdmin] = useState(false);
  const [checking, setChecking] = useState(Boolean(getToken()));

  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setIsAdmin(false);
      setChecking(false);
      return;
    }
    setChecking(true);
    api<{ role: string }>("/api/auth/me")
      .then((me) => {
        if (!cancelled) setIsAdmin(me.role === "admin");
      })
      .catch(() => {
        if (!cancelled) {
          setToken(null);
          setTokenState(null);
          setIsAdmin(false);
        }
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const login = useCallback(async (password: string) => {
    try {
      const result = await api<{ access_token: string }>("/api/auth/login", { method: "POST", body: { password } });
      setToken(result.access_token);
      setTokenState(result.access_token);
      setIsAdmin(true);
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(0, "Network error");
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setTokenState(null);
    setIsAdmin(false);
  }, []);

  const value = useMemo(() => ({ token, isAdmin, checking, login, logout }), [token, isAdmin, checking, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
