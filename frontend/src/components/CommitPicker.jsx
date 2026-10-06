import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { fmtInt, fmtDateTime, fmtSha } from "../hooks";
import Modal from "./Modal";
import { EmptyState, ErrorState } from "./States";

const PAGE = 200; // commits fetched per API page
const ROW_H = 44; // fixed row height for manual windowing
const VIEW_H = 380; // list viewport height
const MAX_SHAS = 1500; // cap written into the shareable URL

/**
 * Commit picker modal: search + manual virtualised selection.
 * Fluid on 100k-commit repositories — only the visible window is rendered and
 * pages are appended on scroll (no full-list load).
 */
export default function CommitPicker({ repoId, initial = [], onApply, onClose }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const [selected, setSelected] = useState(() => new Set(initial));
  const [scrollTop, setScrollTop] = useState(0);
  const lastClicked = useRef(-1);
  const listRef = useRef(null);
  const seq = useRef(0);
  const loadingRef = useRef(false);

  const loadPage = async (query, offset, reset) => {
    const my = ++seq.current;
    loadingRef.current = true;
    setLoading(true);
    setError(null);
    try {
      const page = await api.commits(repoId, { q: query || undefined, limit: PAGE, offset });
      if (seq.current !== my) return;
      setItems((prev) => (reset ? page : [...prev, ...page]));
      setDone(page.length < PAGE);
    } catch (e) {
      if (seq.current === my) setError(e);
    } finally {
      if (seq.current === my) {
        setLoading(false);
        loadingRef.current = false;
      }
    }
  };

  useEffect(() => {
    const t = setTimeout(
      () => {
        lastClicked.current = -1;
        if (listRef.current) listRef.current.scrollTop = 0;
        setScrollTop(0);
        loadPage(q.trim(), 0, true);
      },
      q ? 250 : 0
    );
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, repoId]);

  const onScroll = (e) => {
    const el = e.target;
    setScrollTop(el.scrollTop);
    if (!done && !loadingRef.current && el.scrollTop + el.clientHeight > el.scrollHeight - ROW_H * 10) {
      loadPage(q.trim(), items.length, false);
    }
  };

  const toggle = (idx, shiftKey) => {
    const sha = items[idx].sha;
    setSelected((prev) => {
      const next = new Set(prev);
      if (shiftKey && lastClicked.current >= 0) {
        const a = Math.min(lastClicked.current, idx);
        const b = Math.max(lastClicked.current, idx);
        const turnOn = !next.has(sha);
        for (let i = a; i <= b; i++) {
          if (turnOn) next.add(items[i].sha);
          else next.delete(items[i].sha);
        }
      } else if (next.has(sha)) {
        next.delete(sha);
      } else {
        next.add(sha);
      }
      return next;
    });
    lastClicked.current = idx;
  };

  const selectLoaded = () =>
    setSelected((prev) => {
      const n = new Set(prev);
      items.forEach((c) => n.add(c.sha));
      return n;
    });

  const apply = () => {
    const shas = [...selected];
    if (shas.length > MAX_SHAS) shas.length = MAX_SHAS;
    onApply(shas);
  };

  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - 5);
  const end = Math.min(items.length, Math.ceil((scrollTop + VIEW_H) / ROW_H) + 5);
  const slice = items.slice(start, end);

  return (
    <Modal
      title="Select commits"
      onClose={onClose}
      wide
      footer={
        <>
          <span className="small muted" style={{ marginRight: "auto" }}>
            {fmtInt(selected.size)} selected
            {selected.size > MAX_SHAS ? ` · URL keeps first ${fmtInt(MAX_SHAS)}` : ""}
          </span>
          <button className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={apply}>
            Apply selection
          </button>
        </>
      }
    >
      <div className="row mb16">
        <input
          style={{ flex: 1 }}
          placeholder="Search author or subject…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
        <button className="btn btn-sm" onClick={selectLoaded} disabled={!items.length}>
          Select loaded ({fmtInt(items.length)})
        </button>
        <button className="btn btn-sm" onClick={() => setSelected(new Set())} disabled={!selected.size}>
          Clear
        </button>
      </div>

      <div className="vlist" ref={listRef} onScroll={onScroll} style={{ height: VIEW_H }}>
        {error && !items.length ? (
          <ErrorState error={error} onRetry={() => loadPage(q.trim(), 0, true)} />
        ) : !items.length && !loading ? (
          <EmptyState title="No commits match" hint="Try another search term or clear the search." />
        ) : (
          <div style={{ height: items.length * ROW_H, position: "relative" }}>
            {slice.map((c, i) => {
              const idx = start + i;
              const sel = selected.has(c.sha);
              return (
                <div
                  key={c.sha}
                  className={"vrow" + (sel ? " sel" : "")}
                  style={{ top: idx * ROW_H }}
                  onClick={(e) => toggle(idx, e.shiftKey)}
                >
                  <span
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: 4,
                      border: "1px solid " + (sel ? "#58a6ff" : "#30363d"),
                      background: sel ? "#1f6feb" : "transparent",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 11,
                      color: "#fff",
                      flex: "none",
                    }}
                  >
                    {sel ? "✓" : ""}
                  </span>
                  <span className="vsha">{fmtSha(c.sha)}</span>
                  <span className="vmeta">
                    <span className="nowrap" style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {c.author}
                    </span>
                    <span className="vsub">{c.subject}</span>
                  </span>
                  <span className="vdate">{fmtDateTime(c.ct)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="vlist-foot">
        <span>
          {fmtInt(items.length)} loaded{done ? "" : "+"} (newest first)
        </span>
        <span className="spacer" />
        {loading ? <span>loading…</span> : null}
      </div>
    </Modal>
  );
}
