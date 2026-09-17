import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  /** Store the token and user from any endpoint that returns them. Changing
      the password and signing out other devices both issue a new token — if
      it isn't stored, this tab's next request fails with the session it just
      ended. */
  const applyAuthResult = useCallback((result) => {
    setToken(result.access_token);
    setUser(result.user);
  }, []);

  async function login(email, password) {
    applyAuthResult(await api.login({ email, password }));
  }

  async function register(email, password, fullName) {
    applyAuthResult(
      await api.register({ email, password, full_name: fullName || undefined }),
    );
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, logout, applyAuthResult }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
