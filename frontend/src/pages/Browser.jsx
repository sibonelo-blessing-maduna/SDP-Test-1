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
import StatCards from "../components/StatCards";

const isDir = (t) => t === "directory" || t === "dir";
const num = (key, label) => ({ key, label, align: "right", fmt: fmtSmart });

export default function Browser({ repoId, query, setQuery }) {
  const filters = readFilters(query);
  const params = filtersToParams(filters);
  const key = filtersKey(params);
  const path = query.get("path") || "/";
  const [openFile, setOpenFile] = useState(null);

  const children = useApi(
    () => api.children(repoId, { dir: path, sort: "churn", order: "desc", ...params }),
    [repoId, path, key]
  );
  const fileMetrics = useApi(
    openFile ? () => api.metrics(repoId, { path: openFile, ...params }) : null,
    [repoId, openFile, key]
  );

  const crumbs = path === "/" ? [] : path.split("/");
  const parent = crumbs.length > 1 ? crumbs.slice(0, -1).join("/") : "/";

  const columns = [
    {
      key: "name",
      label: "Name",
      render: (r) => (
        <span className="row">
          <span className={"badge " + (isDir(r.type) ? "badge-dir" : "")}>
            {isDir(r.type) ? "dir" : "file"}
          </span>
          <span>{r.name}</span>
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
    num("modification_frequency", "Mod. freq"),
    num("churn_rate", "Churn rate"),
    { key: "ownership", label: "Ownership", align: "right", fmt: fmtPct },
  ];

  const onRowClick = (r) => {
    if (isDir(r.type)) {
      setOpenFile(null);
      setQuery({ path: r.path });
    } else {
      setOpenFile(r.path);
    }
  };

  const panelRows = fileMetrics.data
    ? [
        { author: "— ALL authors —", ...(fileMetrics.data.all || {}) },
        ...(fileMetrics.data.authors || []),
      ]
    : [];

  const panelColumns = [
    {
      key: "author",
      label: "Author",
      render: (r) => (
        <span className="nowrap" title={r.author}>
          {r.author && r.author.length > 28 ? r.author.slice(0, 27) + "…" : r.author}
        </span>
      ),
    },
    num("added", "Added"),
    num("removed", "Removed"),
    num("churn", "Churn"),
    num("modifications", "Mods"),
    { key: "ownership", label: "Ownership", align: "right", fmt: fmtPct },
  ];

  const goTo = (p) => {
    setOpenFile(null);
    setQuery({ path: p === "/" ? null : p });
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>Browser</h1>
        <span className="spacer" />
        <div className="crumbs">
          <button onClick={() => goTo("/")}>/</button>
          {crumbs.map((seg, i) => {
            const p = crumbs.slice(0, i + 1).join("/");
            return (
              <span key={p} className="row" style={{ gap: 2 }}>
                <span className="sep">/</span>
                <button onClick={() => goTo(p)}>{seg}</button>
              </span>
            );
          })}
        </div>
        {crumbs.length ? (
          <button className="btn btn-sm" onClick={() => goTo(parent)}>
            Up
          </button>
        ) : null}
      </div>

      <FilterBar
        repoId={repoId}
        query={query}
        setQuery={setQuery}
        onChanged={() => {
          children.reload();
          if (openFile) fileMetrics.reload();
        }}
      />

      <div className="split">
        <div className="card">
          <div className="row mb16">
            <h3 className="card-title" style={{ margin: 0 }}>
              {path === "/" ? "Repository root" : path}
            </h3>
            <span className="spacer" />
            <span className="small muted">{(children.data || []).length} entries</span>
          </div>

          {children.loading && !children.data ? (
            <Skeleton lines={8} height={14} />
          ) : children.error ? (
            <ErrorState error={children.error} onRetry={children.reload} />
          ) : (
            <>
              <Table
                columns={columns}
                rows={children.data || []}
                rowKey={(r) => r.path}
                onRowClick={onRowClick}
                initialSort={{ key: "churn", dir: -1 }}
                empty={
                  <EmptyState
                    title="Nothing here"
                    hint="This directory has no tracked files or subdirectories in the selected commits."
                  />
                }
              />
              <div className="small muted mt16">
                Click a directory to drill in · click a file for its per-author breakdown.
              </div>
            </>
          )}
        </div>

        {openFile ? (
          <div className="card">
            <div className="row mb16">
              <h3
                className="card-title"
                style={{ margin: 0, overflow: "hidden", textOverflow: "ellipsis" }}
                title={openFile}
              >
                {openFile}
              </h3>
              <span className="spacer" />
              <button className="icon-btn" onClick={() => setOpenFile(null)} aria-label="Close panel">
                ×
              </button>
            </div>

            {fileMetrics.loading && !fileMetrics.data ? (
              <Skeleton lines={6} height={14} />
            ) : fileMetrics.error ? (
              <ErrorState error={fileMetrics.error} onRetry={fileMetrics.reload} />
            ) : (
              <>
                <div className="mb16">
                  <StatCards metrics={fileMetrics.data} />
                </div>
                <Table
                  columns={panelColumns}
                  rows={panelRows}
                  rowKey={(r) => r.author}
                  initialSort={{ key: "churn", dir: -1 }}
                />
              </>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
