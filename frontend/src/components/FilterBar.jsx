import { useState } from "react";
import { api } from "../api";
import {
  useApi,
  PRESETS,
  presetToFilter,
  matchPreset,
  readFilters,
  dateToTs,
  tsToDateInput,
  fmtInt,
} from "../hooks";
import CommitPicker from "./CommitPicker";

/**
 * Shared filter bar: time window (presets + custom range), author, manual
 * commit list. All state lives in the shareable URL query (setQuery).
 */
export default function FilterBar({ repoId, query, setQuery, onChanged }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const filters = readFilters(query);
  const active = matchPreset(filters.from, filters.to);
  const [showCustom, setShowCustom] = useState(active === "custom");

  const authorsApi = useApi(() => api.authors(repoId, {}), [repoId]);
  const authors = authorsApi.data || [];

  const setPreset = (id) => {
    if (id === "custom") {
      setShowCustom(true);
      return;
    }
    setShowCustom(false);
    const f = presetToFilter(id);
    setQuery({ from: f.from, to: f.to, commits: null });
  };

  const applyCustom = (which, val) => {
    if (which === "from") setQuery({ from: val ? dateToTs(val, false) : null, commits: null });
    else setQuery({ to: val ? dateToTs(val, true) : null, commits: null });
  };

  return (
    <div className="filterbar">
      <span className="small muted">Time</span>
      <div className="seg">
        {PRESETS.map((p) => (
          <button
            key={p.id}
            className={active === p.id && !filters.commits ? "active" : ""}
            onClick={() => setPreset(p.id)}
          >
            {p.label}
          </button>
        ))}
        <button className={active === "custom" ? "active" : ""} onClick={() => setPreset("custom")}>
          Custom
        </button>
      </div>

      {(showCustom || active === "custom") && (
        <>
          <input
            type="date"
            value={tsToDateInput(filters.from)}
            onChange={(e) => applyCustom("from", e.target.value)}
            disabled={!!filters.commits}
            title="from (inclusive)"
          />
          <span className="muted">→</span>
          <input
            type="date"
            value={tsToDateInput(filters.to ? Number(filters.to) - 86400 : null)}
            onChange={(e) => applyCustom("to", e.target.value)}
            disabled={!!filters.commits}
            title="to (inclusive)"
          />
        </>
      )}

      <span className="small muted">Author</span>
      <select
        value={filters.author || ""}
        onChange={(e) => setQuery({ author: e.target.value || null })}
      >
        <option value="">All authors</option>
        {authors.map((a) => (
          <option key={a.author} value={a.author}>
            {a.author}
          </option>
        ))}
      </select>

      <button className="btn btn-sm" onClick={() => setPickerOpen(true)}>
        Pick commits{filters.commits ? ` (${fmtInt(filters.commits.length)})` : ""}
      </button>
      {filters.commits ? (
        <>
          <span className="chip blue">
            {fmtInt(filters.commits.length)} commits
            <button onClick={() => setQuery({ commits: null })} aria-label="Clear commit selection">
              ×
            </button>
          </span>
          <span className="filter-note">manual commit list overrides the time window</span>
        </>
      ) : null}

      <span className="spacer" />
      {onChanged ? (
        <button className="btn btn-sm" onClick={onChanged} title="Reload with current filters">
          Refresh
        </button>
      ) : null}

      {pickerOpen ? (
        <CommitPicker
          repoId={repoId}
          initial={filters.commits || []}
          onClose={() => setPickerOpen(false)}
          onApply={(shas) => {
            setQuery({ commits: shas.length ? shas.join(",") : null });
            setPickerOpen(false);
          }}
        />
      ) : null}
    </div>
  );
}
