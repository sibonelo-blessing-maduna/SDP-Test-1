import { api } from "../api";
import {
  useApi,
  readFilters,
  filtersToParams,
  filtersKey,
  fmtInt,
  authorName,
} from "../hooks";
import { ChartBox, ErrorState, Skeleton } from "../components/States";
import { ChurnArea, RankBar, DirTreemap, OwnershipDonut } from "../components/Charts";
import FilterBar from "../components/FilterBar";
import StatCards from "../components/StatCards";

const isDir = (t) => t === "directory" || t === "dir";

export default function Dashboard({ repoId, query, setQuery }) {
  const filters = readFilters(query);
  const params = filtersToParams(filters);
  const key = filtersKey(params);

  const repo = useApi(() => api.repo(repoId), [repoId]);
  const metrics = useApi(() => api.metrics(repoId, { path: "/", ...params }), [repoId, key]);
  const series = useApi(
    () => api.series(repoId, { path: "/", bucket: "week", ...params }),
    [repoId, key]
  );
  const children = useApi(() => api.children(repoId, { dir: "/", ...params }), [repoId, key]);
  const authors = useApi(() => api.authors(repoId, params), [repoId, key]);

  const refreshAll = () => {
    repo.reload();
    metrics.reload();
    series.reload();
    children.reload();
    authors.reload();
  };

  const kids = children.data || [];
  const topFiles = kids
    .filter((c) => !isDir(c.type))
    .sort((a, b) => Number(b.churn) - Number(a.churn))
    .slice(0, 10);
  const treemapRows = kids.slice().sort((a, b) => Number(b.churn) - Number(a.churn));
  const topAuthors = (authors.data || [])
    .slice(0, 10)
    .map((a) => ({ name: authorName(a.author), churn: a.churn }));

  return (
    <div className="page">
      <div className="page-head">
        <h1>{repo.data ? repo.data.name : repoId}</h1>
        {repo.data ? <span className="badge">{repo.data.status}</span> : null}
        {filters.author ? (
          <span className="chip blue">
            author: {authorName(filters.author)}
            <button onClick={() => setQuery({ author: null })} aria-label="Clear author filter">
              ×
            </button>
          </span>
        ) : null}
        <span className="spacer" />
        {repo.data ? (
          <span className="sub">
            {fmtInt(repo.data.authors_count)} authors · {fmtInt(repo.data.files_count)} files ·{" "}
            {fmtInt(repo.data.dirs_count)} directories
          </span>
        ) : null}
      </div>

      <FilterBar repoId={repoId} query={query} setQuery={setQuery} onChanged={refreshAll} />

      {metrics.loading && !metrics.data ? (
        <div className="card mb16">
          <Skeleton lines={3} height={18} />
        </div>
      ) : metrics.error ? (
        <ErrorState error={metrics.error} onRetry={metrics.reload} />
      ) : (
        <StatCards metrics={metrics.data} />
      )}

      <div className="grid-2">
        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <h3 className="card-title">Churn over time — weekly buckets</h3>
          <ChartBox
            loading={series.loading && !series.data}
            error={series.error}
            empty={!!series.data && series.data.length === 0}
            onRetry={series.reload}
          >
            <ChurnArea data={series.data || []} />
          </ChartBox>
        </div>

        <div className="card">
          <h3 className="card-title">Top files by churn (top 10)</h3>
          <ChartBox
            loading={children.loading && !children.data}
            error={children.error}
            empty={!!children.data && !topFiles.length}
            onRetry={children.reload}
          >
            <RankBar rows={topFiles.map((f) => ({ name: f.name, churn: f.churn }))} />
          </ChartBox>
        </div>

        <div className="card">
          <h3 className="card-title">Ownership — share of churn</h3>
          <ChartBox
            loading={authors.loading && !authors.data}
            error={authors.error}
            empty={!!authors.data && !authors.data.length}
            onRetry={authors.reload}
          >
            <OwnershipDonut authors={authors.data || []} />
          </ChartBox>
        </div>

        <div className="card">
          <h3 className="card-title">Root children treemap — sized by churn</h3>
          <ChartBox
            loading={children.loading && !children.data}
            error={children.error}
            empty={!!children.data && !treemapRows.length}
            onRetry={children.reload}
          >
            <DirTreemap rows={treemapRows} />
          </ChartBox>
        </div>

        <div className="card">
          <h3 className="card-title">Top authors by churn (top 10)</h3>
          <ChartBox
            loading={authors.loading && !authors.data}
            error={authors.error}
            empty={!!authors.data && !authors.data.length}
            onRetry={authors.reload}
          >
            <RankBar rows={topAuthors} color="#bc8cff" />
          </ChartBox>
        </div>
      </div>
    </div>
  );
}
