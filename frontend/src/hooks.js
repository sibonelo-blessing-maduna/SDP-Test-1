import { useCallback, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------- hash routing
// Shareable URLs: #/repos/<id>/<page>?from=&to=&author=&commits=&path=
export function parseHash(hash) {
  const raw = String(hash || "").replace(/^#/, "");
  const [pathPart, queryPart] = raw.split("?");
  return {
    segments: pathPart.split("/").filter(Boolean),
    query: new URLSearchParams(queryPart || ""),
  };
}

export function buildHash(segments, query) {
  const path = "#/" + (segments || []).join("/");
  const s =
    query instanceof URLSearchParams
      ? query.toString()
      : new URLSearchParams(query || {}).toString();
  return s ? `${path}?${s}` : path;
}

export function navigate(segments, query, { replace = false } = {}) {
  const h = buildHash(segments, query);
  if (replace && window.location.hash) {
    window.history.replaceState(null, "", h);
    // replaceState does not fire hashchange; notify the router manually
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  } else {
    window.location.hash = h;
  }
}

export function useHashRoute() {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

// ---------------------------------------------------------------- data fetching
// useApi(fn, deps): fn = null disables fetching (useful for conditional panels).
export function useApi(fn, deps = []) {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(fn != null);
  const seq = useRef(0);

  const reload = useCallback(() => {
    if (fnRef.current == null) return;
    const my = ++seq.current;
    setLoading(true);
    setError(null);
    Promise.resolve()
      .then(() => fnRef.current())
      .then((d) => {
        if (seq.current === my) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (seq.current === my) {
          setError(e);
          setLoading(false);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (fnRef.current == null) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reload]);

  return { data, error, loading, reload, setData };
}

// ---------------------------------------------------------------- formatting
export const fmtInt = (n) =>
  n === null || n === undefined || n === "" ? "—" : Number(n).toLocaleString("en-US");

export const fmtFloat = (n, d = 2) =>
  n === null || n === undefined || n === "" ? "—" : Number(n).toFixed(d);

export const fmtPct = (n) =>
  n === null || n === undefined || n === "" ? "—" : (Number(n) * 100).toFixed(2) + "%";

export const fmtSha = (s) => (s ? String(s).slice(0, 8) : "—");

export const fmtDate = (t) =>
  t ? new Date(Number(t) * 1000).toISOString().slice(0, 10) : "—";

export const fmtDateTime = (t) =>
  t ? new Date(Number(t) * 1000).toISOString().replace("T", " ").slice(0, 16) + "Z" : "—";

const _compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
export const fmtCompact = (v) => _compact.format(Number(v) || 0);

// Rows carry full-precision numbers; display integers plain, ratios 4dp, rates 2dp.
export function fmtSmart(v) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  if (Number.isInteger(n)) return n.toLocaleString("en-US");
  return Math.abs(n) < 1 ? n.toFixed(4) : n.toFixed(2);
}

export const authorName = (a) => String(a || "").replace(/\s*<[^>]*>\s*$/, "");

// ---------------------------------------------------------------- filters
export const PRESETS = [
  { id: "all", label: "All time", days: null },
  { id: "30d", label: "30 days", days: 30 },
  { id: "90d", label: "90 days", days: 90 },
  { id: "365d", label: "1 year", days: 365 },
];

export function presetToFilter(id) {
  const p = PRESETS.find((x) => x.id === id);
  if (!p || p.days == null) return { from: null, to: null };
  const now = Math.floor(Date.now() / 1000);
  return { from: now - p.days * 86400, to: null };
}

const PRESET_TOLERANCE = 3 * 86400; // tolerate clock drift for preset highlighting
export function matchPreset(from, to) {
  if (!from && !to) return "all";
  for (const p of PRESETS) {
    if (p.days == null) continue;
    const f = presetToFilter(p.id);
    if (from && Math.abs(Number(from) - f.from) < PRESET_TOLERANCE) return p.id;
  }
  return "custom";
}

export function readFilters(query) {
  const commitsRaw = query.get("commits") || "";
  return {
    from: query.get("from") || null,
    to: query.get("to") || null,
    author: query.get("author") || null,
    commits: commitsRaw ? commitsRaw.split(",").filter(Boolean) : null,
  };
}

export function filtersToParams(f) {
  return {
    from: f.from || undefined,
    to: f.to || undefined,
    author: f.author || undefined,
    commits: f.commits && f.commits.length ? f.commits.join(",") : undefined,
  };
}

export const filtersKey = (params) => JSON.stringify(params || {});

// date input <-> unix ts helpers (UTC day granularity)
export function dateToTs(s, endExclusive = false) {
  if (!s) return null;
  const [y, m, d] = s.split("-").map(Number);
  const base = Date.UTC(y, m - 1, d) / 1000;
  return endExclusive ? base + 86400 : base;
}
export const tsToDateInput = (t) => (t ? new Date(Number(t) * 1000).toISOString().slice(0, 10) : "");
