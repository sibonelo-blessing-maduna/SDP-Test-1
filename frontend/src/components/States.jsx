export function EmptyState({ title, hint, children }) {
  return (
    <div className="state">
      <div className="state-title">{title || "Nothing here yet"}</div>
      {hint ? <div className="state-hint">{hint}</div> : null}
      {children}
    </div>
  );
}

export function ErrorState({ error, onRetry, hint }) {
  return (
    <div className="state state-error">
      <div className="state-title">Request failed</div>
      <div className="state-hint">{hint || "The API call did not succeed."}</div>
      <div className="state-hint mono">{String((error && error.message) || error || "unknown error")}</div>
      {onRetry ? (
        <button className="btn btn-sm" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function Skeleton({ lines = 3, height = 12 }) {
  return (
    <div>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skel skel-line"
          style={{ height, width: i === lines - 1 && lines > 1 ? "60%" : "100%" }}
        />
      ))}
    </div>
  );
}

export function ProgressBar({ value }) {
  const pct = Math.max(0, Math.min(1, Number(value) || 0)) * 100;
  return (
    <div className="pbar">
      <span style={{ width: pct.toFixed(1) + "%" }} />
    </div>
  );
}

export function StatusBadge({ status, progress }) {
  const cls =
    status === "ready" ? "badge-ready" : status === "error" ? "badge-error" : "badge-scanning";
  let label = status || "unknown";
  if (status === "scanning" && typeof progress === "number") {
    label = `scanning ${(progress * 100).toFixed(0)}%`;
  }
  return <span className={"badge " + cls}>{label}</span>;
}

// Standard wrapper for a single chart widget: skeleton / error / empty / chart.
export function ChartBox({ loading, error, empty, onRetry, hint, children }) {
  if (loading) return <Skeleton lines={5} height={16} />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (empty)
    return (
      <div className="chart-empty">
        {hint || "No data for this selection — widen the time range or clear filters."}
      </div>
    );
  return children;
}
