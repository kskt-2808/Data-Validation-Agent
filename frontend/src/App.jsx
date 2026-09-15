import { useState } from "react";
import { useAuth } from "./auth.js";
import Newton from "./Newton.jsx";

export default function App() {
  const auth = useAuth();
  if (auth.status === "loading") return <div className="splash">Signing in…</div>;
  if (auth.status === "signedOut") return <SignedOut auth={auth} />;
  return <Newton onAuthLost={auth.signOut} />;
}

function SignedOut({ auth }) {
  const [token, setToken] = useState("");
  return (
    <div className="splash">
      <div className="card signed-out">
        <h1>Newton</h1>
        <p>{auth.message || "Open Newton from iosense Launchpad to sign in."}</p>
        {import.meta.env.DEV && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (token.trim()) auth.signInWithToken(token);
            }}
          >
            <label className="field">
              <span className="label">Local development only: paste a bearer token</span>
              <input type="password" value={token} onChange={(e) => setToken(e.target.value)} />
            </label>
            <button className="btn primary" type="submit">
              Use token
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
