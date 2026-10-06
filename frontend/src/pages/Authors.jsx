import { useState } from "react";
import { api } from "../api";
import {
  useApi,
  readFilters,
  filtersToParams,
  filtersKey,
  fmtSmart,
  fmtPct,
} from "../hooks";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import Table from "../components/Table";
import FilterBar from "../components/FilterBar";

const num = (key, label) => ({ key, label, align: "right", fmt: fmtSmart });

export default function Authors({ repoId, query, setQuery }) {
  const filters = readFilters(query);
  const params = filtersToParams(filters);
  const key = filtersKey(params);

  const authors = useApi(() => api.authors(repoId, params), [repoId, key]);
  const mailmap = useApi(() => api.mailmap(repoId), [repoId]);

  const [selected, setSelected] = useState(() => new Set());
  const [target, setTarget] = useState("");
  const [merges, setMerges] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const rows = authors.data || [];
  const mergeCount = merges ? Object.keys(merges).length : 0;

  const toggle = (name) =>
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(name)) n.delete(name);
      else n.add(name);
      return n;
    });

  const doMerge = async () => {
    if (!selected.size || !target) return;
    setBusy(true);
    setError(null);
    try {
      const from = [...selected].filter((a) => a !== target);
      const res = await api.mergeAuthors(repoId, from, target);
      setMerges(res.merges);
      setSelected(new Set());
      authors.reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const doUnmerge = async (author) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.unmergeAuthor(repoId, author);
      setMerges(res.merges);
      authors.reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const doUnmergeAll = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.unmergeAll(repoId);
      setMerges(res.merges);
      authors.reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const applyMailmap = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.mailmapApply(repoId);
      setMerges(res.merges);
      authors.reload();
      mailmap.reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    {
      key: "sel",
      label: "",
      sortable: false,
      render: (r) => (
        <span
          style={{
            width: 16,
            height: 16,
            borderRadius: 4,
            border: "1px solid " + (selected.has(r.author) ? "#58a6ff" : "#30363d"),
            background: selected.has(r.author) ? "#1f6feb" : "transparent",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 11,
            color: "#fff",
          }}
        >
          {selected.has(r.author) ? "✓" : ""}
        </span>
      ),
    },
    {
      key: "author",
      label: "Author",
      render: (r) => (
        <span className="nowrap" title={r.author}>
          {r.author.length > 34 ? r.author.slice(0, 33) + "…" : r.author}
        </span>
      ),
    },
    num("added", "Added"),
    num("removed", "Removed"),
    {
      ...num("growth", "Growth"),
      render: (r) => (
        <span className={(Number(r.growth) || 0) >= 0 ? "pos" : "neg"}>{fmtSmart(r.growth)}</span>
      ),
    },
    num("churn", "Churn"),
    num("modifications", "Mods"),
    num("commit_count", "Commits"),
    { key: "ownership", label: "Ownership", align: "right", fmt: fmtPct },
  ];

  return (
    <div className="page">
      <div className="page-head">
        <h1>Authors</h1>
        <span className="sub">
          {rows.length ? `${rows.length} authors (merged view)` : ""}
        </span>
      </div>

      <FilterBar
        repoId={repoId}
        query={query}
        setQuery={setQuery}
        onChanged={() => authors.reload()}
      />

      <div className="card mb16">
        <div className="row wrap">
          <span className="small muted">{selected.size} selected</span>
          <span className="small muted">merge into</span>
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">— target author —</option>
            {rows.map((r) => (
              <option key={r.author} value={r.author}>
                {r.author}
              </option>
            ))}
          </select>
          <button
            className="btn btn-primary btn-sm"
            disabled={!selected.size || !target || busy}
            onClick={doMerge}
          >
            Merge
          </button>
          <button
            className="btn btn-sm"
            disabled={!selected.size}
            onClick={() => setSelected(new Set())}
          >
            Clear selection
          </button>
          <span className="spacer" />
          {mergeCount ? (
            <button className="btn btn-sm" disabled={busy} onClick={doUnmergeAll}>
              Unmerge all ({mergeCount})
            </button>
          ) : null}
        </div>

        {merges && mergeCount ? (
          <div className="row wrap mt16">
            {Object.entries(merges).map(([raw, canon]) => (
              <span className="chip" key={raw}>
                {raw} → {canon}
                <button disabled={busy} onClick={() => doUnmerge(raw)} title="Unmerge this author">
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}

        {error ? <div className="form-error">{String(error.message || error)}</div> : null}
      </div>

      <div className="card mb16">
        <div className="row mb16" style={{ marginBottom: 8 }}>
          <h3 className="card-title" style={{ margin: 0 }}>
            .mailmap
          </h3>
          <span className="spacer" />
          {mailmap.data && mailmap.data.available ? (
            <button className="btn btn-sm btn-primary" disabled={busy} onClick={applyMailmap}>
              Apply .mailmap ({mailmap.data.entries.length})
            </button>
          ) : null}
        </div>
        {mailmap.loading ? (
          <Skeleton lines={2} />
        ) : mailmap.error ? (
          <ErrorState error={mailmap.error} onRetry={mailmap.reload} />
        ) : !mailmap.data || !mailmap.data.available ? (
          <div className="state">
            <div className="state-title">No .mailmap found in this repository</div>
            <div className="state-hint">
              Automatic author consolidation is not available — use manual merges above.
            </div>
          </div>
        ) : mailmap.data.entries.length === 0 ? (
          <EmptyState title=".mailmap exists but has no entries" />
        ) : (
          <Table
            columns={[
              { key: "raw", label: "Raw author" },
              { key: "canonical", label: "Canonical author" },
            ]}
            rows={mailmap.data.entries}
            rowKey={(r) => r.raw}
          />
        )}
      </div>

      <div className="card">
        <h3 className="card-title">Repository-level metrics per author</h3>
        {authors.loading && !authors.data ? (
          <Skeleton lines={8} height={14} />
        ) : authors.error ? (
          <ErrorState error={authors.error} onRetry={authors.reload} />
        ) : !rows.length ? (
          <EmptyState
            title="No authors for this selection"
            hint="Widen the time range or clear the author / commit filters."
          />
        ) : (
          <Table
            columns={columns}
            rows={rows}
            rowKey={(r) => r.author}
            initialSort={{ key: "churn", dir: -1 }}
            onRowClick={(r) => toggle(r.author)}
            isRowSelected={(r) => selected.has(r.author)}
          />
        )}
      </div>
    </div>
  );
}
