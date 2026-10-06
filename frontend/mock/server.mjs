#!/usr/bin/env node
/**
 * Mock API server for the WS4 frontend — fixtures-driven, zero dependencies.
 *
 * Serves the frozen Contract C shapes from fixtures/mock/*.json, with in-memory
 * state for author merges and simulated clone/upload scans. The Vite dev/preview
 * proxy targets this server by default; point it at the real backend instead
 * with VITE_PROXY_TARGET=http://localhost:8000.
 *
 * Approximations (UI development only — the real API is exact):
 *  - metrics/children for non-root paths are synthesised from the root-children
 *    fixture (author shares scaled from repository-level ownership, marked
 *    "synthesized": true in the response);
 *  - series honours from/to but ignores bucket; the metrics endpoints ignore
 *    from/to/commits (author filters the authors array);
 *  - .mailmap is reported as unavailable; merge/unmerge work in memory only.
 *
 * Usage: node mock/server.mjs        (MOCK_PORT=5175)
 */
import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIX = path.resolve(HERE, "../../fixtures/mock");
const PORT = Number(process.env.MOCK_PORT || 5175);

const state = {
  merges: {}, // repoId -> { rawAuthor: canonicalAuthor }
  deleted: new Set(),
  extra: [], // simulated clone/upload repositories
  seq: 0,
};

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,DELETE,OPTIONS",
  "access-control-allow-headers": "content-type",
};

function send(res, code, obj) {
  if (obj === undefined) {
    res.writeHead(code, CORS);
    res.end();
    return;
  }
  res.writeHead(code, { "content-type": "application/json", ...CORS });
  res.end(JSON.stringify(obj));
}

async function load(name, fallback) {
  try {
    return JSON.parse(await readFile(path.join(FIX, name), "utf-8"));
  } catch {
    return fallback;
  }
}

const send404 = (res, what = "not found") => send(res, 404, { detail: what });
const toInt = (v, d) => {
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) ? n : d;
};

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function normalizePath(p) {
  const s = String(p || "").replace(/^\/+|\/+$/g, "");
  return s || "/";
}

function slug(s) {
  return String(s || "repo")
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "") || "repo";
}

// ---------- author merge overlay (read-time, reversible) ----------
function applyMerges(id, rows) {
  const merges = state.merges[id] || {};
  if (!Object.keys(merges).length) return rows;
  const out = new Map();
  for (const r of rows) {
    const name = merges[r.author] || r.author;
    if (!out.has(name)) {
      out.set(name, { ...r, author: name });
    } else {
      const cur = out.get(name);
      for (const [k, v] of Object.entries(r)) {
        if (k === "author") continue;
        if (typeof v === "number" && typeof cur[k] === "number") cur[k] += v;
      }
    }
  }
  const merged = [...out.values()];
  const total = merged.reduce((s, r) => s + (Number(r.churn) || 0), 0);
  if (total > 0) {
    for (const r of merged) {
      if ("ownership" in r) r.ownership = (Number(r.churn) || 0) / total;
    }
  }
  return merged;
}

// ---------- synthesise sub-object metrics from the root children fixture ----------
function synthChildMetrics(child, base) {
  const churn = Number(child.churn) || 0;
  const authors = (base.authors || [])
    .slice(0, 5)
    .map((a) => {
      const share = Number(a.ownership) || 0;
      const c = Math.round(churn * share);
      const added = Math.round(c * ((Number(a.added) + 1) / (Number(a.added) + Number(a.removed) + 2)));
      const removed = Math.max(c - added, 0);
      const mods = Math.round((Number(child.modifications) || 0) * share);
      return {
        author: a.author,
        added,
        removed,
        growth: added - removed,
        churn: c,
        modifications: mods,
        modification_frequency: null,
        churn_rate: null,
        ownership: share,
        commit_count: mods,
      };
    })
    .filter((a) => a.churn > 0 || a.added > 0);
  return {
    object: {
      type: child.type === "directory" || child.type === "dir" ? "directory" : "file",
      path: child.path,
    },
    commit_set: {
      count: base.commit_set ? base.commit_set.count : null,
      from: null,
      to: null,
      commits: null,
    },
    all: {
      added: child.added,
      removed: child.removed,
      growth: child.growth,
      churn: child.churn,
      modifications: child.modifications,
      modification_frequency: child.modification_frequency ?? null,
      churn_rate: child.churn_rate ?? null,
      ownership: null,
    },
    authors,
    synthesized: true,
  };
}

// ---------- simulated scans ----------
const summaryOf = (e) => {
  const { message, ...rest } = e;
  return rest;
};

function startScan(id, source) {
  state.extra = state.extra.filter((e) => e.id !== id);
  const entry = {
    id,
    name: id,
    source,
    ref_sha: null,
    commit_count: 0,
    status: "scanning",
    progress: 0,
    authors_count: 0,
    files_count: 0,
    dirs_count: 0,
    error: null,
    message: "cloning…",
  };
  state.extra.unshift(entry);
  const t = setInterval(() => {
    entry.progress = Math.min(1, entry.progress + 0.2);
    if (entry.progress >= 1) {
      entry.status = "ready";
      entry.ref_sha = "mock-" + id + "-0000000000000000000000000000000000000000";
      entry.commit_count = 120 + ((id.length * 37 + id.charCodeAt(0) * 11) % 5000);
      entry.authors_count = 8;
      entry.files_count = 120;
      entry.dirs_count = 14;
      entry.message = "";
      clearInterval(t);
    } else {
      entry.message = `scanning… ${Math.round(entry.progress * 100)}%`;
    }
  }, 700);
  return { id, status: "scanning" };
}

// ---------- router ----------
const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "OPTIONS") return send(res, 204);
    const u = new URL(req.url, `http://localhost:${PORT}`);
    const parts = u.pathname.split("/").filter(Boolean);
    if (parts[0] !== "api") return send404(res);

    // GET /api/repos — list
    if (req.method === "GET" && parts.length === 2 && parts[1] === "repos") {
      const fixtures = await load("repos.json", []);
      const list = fixtures
        .filter((r) => !state.deleted.has(r.id))
        .map((r) => {
          const live = state.extra.find((e) => e.id === r.id);
          return live ? { ...r, ...summaryOf(live) } : r;
        });
      const simulated = state.extra
        .filter((e) => !fixtures.some((r) => r.id === e.id))
        .map(summaryOf);
      return send(res, 200, [...simulated, ...list]);
    }

    // POST /api/repos/clone + /api/repos/upload
    if (req.method === "POST" && parts.length === 3 && parts[1] === "repos" && parts[2] === "clone") {
      const body = JSON.parse((await readBody(req)).toString() || "{}");
      if (!body.url || !String(body.url).trim()) return send(res, 400, { detail: "url is required" });
      const base = String(body.name || "").trim() || String(body.url).replace(/\.git$/i, "").split("/").pop();
      return send(res, 201, startScan(slug(base), String(body.url)));
    }
    if (req.method === "POST" && parts.length === 3 && parts[1] === "repos" && parts[2] === "upload") {
      const buf = await readBody(req);
      if (buf.length < 256) return send(res, 400, { detail: "empty or invalid zip upload" });
      return send(res, 201, startScan(`upload-${++state.seq}`, "zip upload"));
    }

    if (parts[1] !== "repos" || !parts[2]) return send404(res);
    const id = parts[2];
    if (state.deleted.has(id)) return send404(res, "repository not found");
    const extra = state.extra.find((e) => e.id === id);
    const detail = extra ? null : await load(`repo_${id}.json`, null);
    if (!extra && !detail) return send404(res, "repository not found");
    const rest = parts.slice(3);

    // GET /api/repos/:id
    if (req.method === "GET" && rest.length === 0) {
      return send(res, 200, extra ? summaryOf(extra) : detail);
    }

    // DELETE /api/repos/:id
    if (req.method === "DELETE" && rest.length === 0) {
      if (extra) state.extra = state.extra.filter((e) => e.id !== id);
      else state.deleted.add(id);
      return send(res, 204);
    }

    // GET /api/repos/:id/status
    if (req.method === "GET" && rest[0] === "status") {
      if (extra) return send(res, 200, { status: extra.status, progress: extra.progress, message: extra.message || "" });
      return send(res, 200, { status: "ready", progress: 1, message: "fixtures" });
    }

    // GET /api/repos/:id/commits
    if (req.method === "GET" && rest[0] === "commits") {
      let rows = await load(`commits_${id}.json`, []);
      const q = (u.searchParams.get("q") || "").trim().toLowerCase();
      const from = toInt(u.searchParams.get("from"), null);
      const to = toInt(u.searchParams.get("to"), null);
      if (q) rows = rows.filter((c) => (c.author + " " + c.subject).toLowerCase().includes(q));
      if (from !== null) rows = rows.filter((c) => c.ct >= from);
      if (to !== null) rows = rows.filter((c) => c.ct < to);
      const limit = Math.max(0, toInt(u.searchParams.get("limit"), 100));
      const offset = Math.max(0, toInt(u.searchParams.get("offset"), 0));
      return send(res, 200, rows.slice(offset, offset + limit));
    }

    // GET /api/repos/:id/metrics
    if (req.method === "GET" && rest[0] === "metrics") {
      const p = normalizePath(u.searchParams.get("path"));
      const base = await load(`metrics_repository_${id}.json`, null);
      if (!base) return send404(res, "metrics not available for this repository");
      if (p === "/") {
        const out = { ...base };
        out.authors = applyMerges(id, base.authors || []);
        const author = u.searchParams.get("author");
        if (author) out.authors = out.authors.filter((a) => a.author === author);
        return send(res, 200, out);
      }
      const child = (await load(`children_root_${id}.json`, [])).find((c) => c.path === p);
      if (!child) return send404(res, "object not found");
      return send(res, 200, synthChildMetrics(child, base));
    }

    // GET /api/repos/:id/children
    if (req.method === "GET" && rest[0] === "children") {
      const dir = normalizePath(u.searchParams.get("dir"));
      if (dir !== "/") return send(res, 200, []); // only root fixtures are shipped
      const rows = await load(`children_root_${id}.json`, []);
      rows.sort((a, b) => (Number(b.churn) || 0) - (Number(a.churn) || 0));
      return send(res, 200, rows);
    }

    // GET /api/repos/:id/series
    if (req.method === "GET" && rest[0] === "series") {
      const p = normalizePath(u.searchParams.get("path"));
      let rows = p === "/" ? await load(`series_repository_${id}.json`, []) : [];
      const from = toInt(u.searchParams.get("from"), null);
      const to = toInt(u.searchParams.get("to"), null);
      if (from !== null) rows = rows.filter((s) => s.t >= from);
      if (to !== null) rows = rows.filter((s) => s.t < to);
      return send(res, 200, rows);
    }

    // GET /api/repos/:id/authors
    if (req.method === "GET" && rest[0] === "authors" && rest.length === 1) {
      const base = await load(`metrics_repository_${id}.json`, null);
      if (!base) return send404(res, "metrics not available for this repository");
      let rows = applyMerges(id, base.authors || []);
      const author = u.searchParams.get("author");
      if (author) rows = rows.filter((a) => a.author === author);
      return send(res, 200, rows);
    }

    // POST /api/repos/:id/authors/merge
    if (req.method === "POST" && rest[0] === "authors" && rest[1] === "merge") {
      const body = JSON.parse((await readBody(req)).toString() || "{}");
      const from = Array.isArray(body.from) ? body.from : [];
      const to = body.to;
      if (!from.length || !to) return send(res, 400, { detail: "from[] and to are required" });
      const cur = { ...(state.merges[id] || {}) };
      for (const f of from) if (f !== to) cur[f] = to;
      state.merges[id] = cur;
      return send(res, 200, { merges: cur });
    }

    // POST /api/repos/:id/authors/unmerge
    if (req.method === "POST" && rest[0] === "authors" && rest[1] === "unmerge") {
      const body = JSON.parse((await readBody(req)).toString() || "{}");
      if (body.all) state.merges[id] = {};
      else if (body.author) {
        const cur = { ...(state.merges[id] || {}) };
        delete cur[body.author];
        state.merges[id] = cur;
      }
      return send(res, 200, { merges: state.merges[id] || {} });
    }

    // GET /api/repos/:id/mailmap
    if (req.method === "GET" && rest[0] === "mailmap") {
      return send(res, 200, { available: false, entries: [] });
    }

    // POST /api/repos/:id/mailmap/apply
    if (req.method === "POST" && rest[0] === "mailmap" && rest[1] === "apply") {
      return send(res, 200, { merges: state.merges[id] || {}, applied: 0 });
    }

    return send404(res);
  } catch (e) {
    send(res, 500, { detail: String((e && e.message) || e) });
  }
});

server.listen(PORT, () => {
  console.log(`RAT mock API on http://localhost:${PORT} — fixtures: ${FIX}`);
});
