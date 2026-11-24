const API_BASE = "/api/v1";

export function createApiClient(tokenStorageKey) {
  function getToken() {
    return window.localStorage.getItem(tokenStorageKey);
  }

  function setToken(token) {
    if (token) {
      window.localStorage.setItem(tokenStorageKey, token);
    } else {
      window.localStorage.removeItem(tokenStorageKey);
    }
  }

  async function request(path, { method = "GET", body = null } = {}) {
    const headers = { "Content-Type": "application/json" };
    const token = getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== null ? JSON.stringify(body) : null,
    });

    if (res.status === 204) {
      return null;
    }

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg =
        data.detail ||
        Object.values(data)
          .flat()
          .join(" ") ||
        `Request failed (${res.status})`;
      const err = new Error(msg);
      err.status = res.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  return { getToken, setToken, request };
}

export function formatDateTime(isoStr) {
  if (!isoStr) return "—";
  const dt = new Date(isoStr);
  return dt.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function defaultTomorrowDate() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}
