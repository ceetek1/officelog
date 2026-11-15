import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getMe, setCsrf, type Me } from "./api";

interface SessionState {
  me: Me | null;          // null while loading
  error: string | null;
  refresh: () => Promise<void>;
  setMe: (me: Me) => void;
}

const Ctx = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMeState] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  const setMe = useCallback((m: Me) => {
    setCsrf(m.csrf_token);
    setMeState(m);
  }, []);

  const refresh = useCallback(async () => {
    try {
      setMe(await getMe());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, [setMe]);

  useEffect(() => { void refresh(); }, [refresh]);

  return <Ctx.Provider value={{ me, error, refresh, setMe }}>{children}</Ctx.Provider>;
}

export function useSession(): SessionState {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSession outside SessionProvider");
  return s;
}
