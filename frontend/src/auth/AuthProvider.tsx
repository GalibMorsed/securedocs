import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getCurrentUser,
  login as loginRequest,
  register as registerRequest,
  type AuthResponse,
  type AuthUser,
  type RegisterPayload,
} from "../api/auth";

type AuthState = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: AuthUser | null;
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
}

const TOKEN_KEY = "securedocs.accessToken";
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [state, setState] = useState<AuthState>(() =>
    window.sessionStorage.getItem(TOKEN_KEY) ? "loading" : "anonymous",
  );

  useEffect(() => {
    if (!window.sessionStorage.getItem(TOKEN_KEY)) {
      setState("anonymous");
      return;
    }

    let active = true;
    void getCurrentUser()
      .then((currentUser) => {
        if (active) {
          setUser(currentUser);
          setState("authenticated");
        }
      })
      .catch(() => {
        if (active) {
          window.sessionStorage.removeItem(TOKEN_KEY);
          setUser(null);
          setState("anonymous");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const acceptAuth = useCallback((result: AuthResponse) => {
    window.sessionStorage.setItem(TOKEN_KEY, result.access_token);
    setUser(result.user);
    setState("authenticated");
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      acceptAuth(await loginRequest(email, password));
    },
    [acceptAuth],
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      acceptAuth(await registerRequest(payload));
    },
    [acceptAuth],
  );

  const logout = useCallback(() => {
    window.sessionStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setState("anonymous");
  }, []);

  const value = useMemo(
    () => ({ user, state, login, register, logout }),
    [user, state, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
