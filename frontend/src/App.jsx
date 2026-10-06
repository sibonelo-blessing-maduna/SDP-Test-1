import { useCallback } from "react";
import { useHashRoute, navigate, useApi } from "./hooks";
import { api } from "./api";
import Repos from "./pages/Repos";
import Dashboard from "./pages/Dashboard";
import Browser from "./pages/Browser";
import Authors from "./pages/Authors";
import { EmptyState } from "./components/States";

export default function App() {
  const route = useHashRoute();
  const seg0 = route.segments[0];
  const repoId = route.segments[1];
  const page = route.segments[2];

  const repos = useApi(() => api.repos(), []);
  const repoList = repos.data || [];

  const setQuery = useCallback(
    (patch) => {
      const q = new URLSearchParams(route.query);
      for (const [k, v] of Object.entries(patch)) {
        if (v === null || v === undefined || v === "") q.delete(k);
        else q.set(k, String(v));
      }
      navigate(route.segments, q, { replace: true });
    },
    [route]
  );

  let content;
  if (!seg0) {
    content = <Repos />;
  } else if (seg0 === "repos" && repoId) {
    const props = { repoId, query: route.query, setQuery };
    if (!page || page === "dashboard") content = <Dashboard {...props} />;
    else if (page === "browser") content = <Browser {...props} />;
    else if (page === "authors") content = <Authors {...props} />;
    else
      content = (
        <div className="page">
          <EmptyState title="Page not found" hint={`Unknown route: ${page}`} />
        </div>
      );
  } else {
    content = (
      <div className="page">
        <EmptyState title="Page not found" hint="The URL does not match any route.">
          <button className="btn mt16" onClick={() => navigate([])}>
            Back to repositories
          </button>
        </EmptyState>
      </div>
    );
  }

  const tab = (label, targetPage, active) => (
    <a
      className={"navtab" + (active ? " active" : "")}
      href={`#/repos/${repoId}${targetPage ? "/" + targetPage : ""}`}
      onClick={(e) => {
        e.preventDefault();
        navigate(
          targetPage ? ["repos", repoId, targetPage] : ["repos", repoId],
          route.query
        );
      }}
    >
      {label}
    </a>
  );

  return (
    <>
      <header className="topbar">
        <a className="brand" href="#/">
          <span className="brandmark">RAT</span>
          <span>Repo Analysis Tool</span>
        </a>
        {repoId ? (
          <>
            <nav className="navtabs">
              {tab("Dashboard", null, !page || page === "dashboard")}
              {tab("Browser", "browser", page === "browser")}
              {tab("Authors", "authors", page === "authors")}
            </nav>
            <span className="spacer" />
            {repoList.length ? (
              <select
                className="repo-switch"
                value={repoId}
                onChange={(e) => navigate(["repos", e.target.value], route.query)}
                title="Switch repository"
              >
                {repoList.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            ) : null}
          </>
        ) : (
          <span className="spacer" />
        )}
      </header>
      {content}
      <footer className="foot">
        Repo Analysis Tool · reference-exact engine (cJSON · redis · git) · Contract C API
      </footer>
    </>
  );
}
