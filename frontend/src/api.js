// Thin REST client for Contract C (contracts/API.md).
// All calls go through /api, which Vite proxies to the mock server (default,
// fixtures-driven) or to the real backend (VITE_PROXY_TARGET=http://localhost:8000).
const BASE = import.meta.env.VITE_API_BASE || "/api";

function qs(params = {}) {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

async function req(path, { method = "GET", body, form } = {}) {
  const opts = { method, headers: {} };
  if (form) {
    opts.body = form;
  } else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, opts);
  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch {
    // non-JSON body (should not happen with the frozen contracts)
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : `${res.status} ${res.statusText}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

export const api = {
  // repositories
  repos: () => req("/repos"),
  repo: (id) => req(`/repos/${id}`),
  status: (id) => req(`/repos/${id}/status`),
  clone: (url, name) =>
    req("/repos/clone", { method: "POST", body: { url, name: name || undefined } }),
  upload: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return req("/repos/upload", { method: "POST", form: fd });
  },
  remove: (id) => req(`/repos/${id}`, { method: "DELETE" }),

  // commits + metrics
  commits: (id, params) => req(`/repos/${id}/commits${qs(params)}`),
  metrics: (id, params) => req(`/repos/${id}/metrics${qs(params)}`),
  children: (id, params) => req(`/repos/${id}/children${qs(params)}`),
  series: (id, params) => req(`/repos/${id}/series${qs(params)}`),
  authors: (id, params) => req(`/repos/${id}/authors${qs(params)}`),

  // author merging (read-time overlay, reversible)
  mergeAuthors: (id, from, to) =>
    req(`/repos/${id}/authors/merge`, { method: "POST", body: { from, to } }),
  unmergeAuthor: (id, author) =>
    req(`/repos/${id}/authors/unmerge`, { method: "POST", body: { author } }),
  unmergeAll: (id) =>
    req(`/repos/${id}/authors/unmerge`, { method: "POST", body: { all: true } }),
  mailmap: (id) => req(`/repos/${id}/mailmap`),
  mailmapApply: (id) => req(`/repos/${id}/mailmap/apply`, { method: "POST" }),
};
