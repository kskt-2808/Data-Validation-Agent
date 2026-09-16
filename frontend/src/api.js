const TOKEN_KEY = "newton_token";
let memoryToken = null; // used when the Launchpad iframe blocks localStorage

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? memoryToken;
  } catch {
    return memoryToken;
  }
}

export function setToken(token) {
  memoryToken = token;
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage blocked: the token lives for this page only */
  }
}

export function clearToken() {
  memoryToken = null;
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing stored */
  }
}

export class AuthError extends Error {}

async function readError(res) {
  try {
    return (await res.json()).error;
  } catch {
    return null;
  }
}

async function request(path, { method = "GET", body, raw = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = token;
  const res = await fetch(`api/${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401) {
    clearToken();
    throw new AuthError((await readError(res)) || "Your session has expired.");
  }
  if (!res.ok) throw new Error((await readError(res)) || `Request failed (${res.status})`);
  return raw ? res : res.json();
}

export const api = {
  exchangeSso: (token) => request("auth/sso", { method: "POST", body: { token } }),
  devices: () => request("devices"),
  recipes: () => request("recipes"),
  validate: (body) => request("validate", { method: "POST", body }),
  exportExcel: (result) => request("export", { method: "POST", body: result, raw: true }),
  feedback: (body) => request("feedback", { method: "POST", body }),
};
