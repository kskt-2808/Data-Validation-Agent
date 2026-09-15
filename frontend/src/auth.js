import { useCallback, useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "./api.js";

// Launchpad opens the app with a one-time ?token=<sso>. It can only be exchanged
// once, so concurrent mounts share a single exchange per token.
const exchanges = new Map();

function exchangeOnce(sso) {
  if (!exchanges.has(sso)) exchanges.set(sso, api.exchangeSso(sso));
  return exchanges.get(sso);
}

export function useAuth() {
  const [state, setState] = useState({ status: "loading" });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sso = params.get("token");
    if (!sso) {
      setState({ status: getToken() ? "authenticated" : "signedOut" });
      return;
    }
    const stripToken = () => {
      params.delete("token");
      const query = params.toString();
      window.history.replaceState({}, "", window.location.pathname + (query ? `?${query}` : "") + window.location.hash);
    };
    let cancelled = false;
    exchangeOnce(sso)
      .then(({ token }) => {
        setToken(token);
        stripToken();
        if (!cancelled) setState({ status: "authenticated" });
      })
      .catch((err) => {
        stripToken();
        if (cancelled) return;
        setState(getToken() ? { status: "authenticated" } : { status: "signedOut", message: err.message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const signOut = useCallback((message) => {
    clearToken();
    setState({ status: "signedOut", message });
  }, []);

  const signInWithToken = useCallback((token) => {
    setToken(token.trim());
    setState({ status: "authenticated" });
  }, []);

  return { ...state, signOut, signInWithToken };
}
