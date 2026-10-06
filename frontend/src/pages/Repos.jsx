import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useApi, navigate, fmtInt, fmtSha } from "../hooks";
import { EmptyState, ErrorState, Skeleton, StatusBadge, ProgressBar } from "../components/States";
import Modal from "../components/Modal";
import { Sparkline } from "../components/Charts";

function RepoCard({ repo, onOpen, onDeleted }) {
  const series = useApi(
    repo.status === "ready" ? () => api.series(repo.id, { path: "/", bucket: "week" }) : null,
    [repo.id, repo.status]
  );
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);

  const doDelete = async () => {
    setBusy(true);
    try {
      await api.remove(repo.id);
      onDeleted();
    } catch {
      setBusy(false);
    }
  };

  const points = (series.data || []).map((p) => p.churn).slice(-26);

  return (
    <div className="card repo-card">
      <div className="rc-head">
        <span className="rc-name" onClick={onOpen}>
          {repo.name}
        </span>
        <StatusBadge status={repo.status} progress={repo.progress} />
        <span className="spacer" />
        <span className="badge">{fmtInt(repo.commit_count)} commits</span>
      </div>

      <div className="rc-meta">
        <span className="mono small" title={repo.source || repo.id}>
          {(repo.source || repo.id).length > 60 ? (repo.source || repo.id).slice(0, 59) + "…" : repo.source || repo.id}
        </span>
        <span className="small" title={repo.ref_sha || ""}>
          HEAD <span className="mono">{fmtSha(repo.ref_sha)}</span>
        </span>
        {repo.error ? <span className="small neg">{repo.error}</span> : null}
      </div>

      {repo.status === "scanning" ? (
        <div className="stack">
          <ProgressBar value={repo.progress || 0} />
          <span className="small muted">scanning — this page refreshes automatically</span>
        </div>
      ) : (
        <div className="rc-foot">
          <Sparkline points={points} />
          <span className="small muted">weekly churn</span>
          <span className="spacer" />
          {!confirm ? (
            <>
              <button className="btn btn-sm" onClick={onOpen}>
                Open
              </button>
              <button className="btn btn-sm btn-danger" onClick={() => setConfirm(true)}>
                Delete
              </button>
            </>
          ) : (
            <>
              <span className="small neg">Delete {repo.name}?</span>
              <button className="btn btn-sm btn-danger" disabled={busy} onClick={doDelete}>
                Yes, delete
              </button>
              <button className="btn btn-sm" onClick={() => setConfirm(false)}>
                Cancel
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function AddRepoModal({ onClose, onAdded }) {
  const [tab, setTab] = useState("clone");
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [file, setFile] = useState(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const fileInput = useRef(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (tab === "clone") {
        if (!url.trim()) throw new Error("Repository URL is required");
        await api.clone(url.trim(), name.trim());
      } else {
        if (!file) throw new Error("Pick a repository zip (it must contain the .git directory)");
        await api.upload(file);
      }
      onAdded();
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  };

  return (
    <Modal
      title="Add repository"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={busy} onClick={submit}>
            {busy ? "Starting…" : "Start scan"}
          </button>
        </>
      }
    >
      <div className="tabs">
        <button className={"tab" + (tab === "clone" ? " active" : "")} onClick={() => setTab("clone")}>
          Clone URL
        </button>
        <button className={"tab" + (tab === "upload" ? " active" : "")} onClick={() => setTab("upload")}>
          Zip upload
        </button>
      </div>

      {tab === "clone" ? (
        <>
          <div className="field">
            <label className="lbl">Git repository URL</label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repo.git"
              autoFocus
            />
          </div>
          <div className="field">
            <label className="lbl">Name (optional — defaults to the repo name)</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="my-repo" />
          </div>
        </>
      ) : (
        <div
          className={"drop" + (over ? " over" : "")}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            const f = e.dataTransfer.files && e.dataTransfer.files[0];
            if (f) setFile(f);
          }}
          onClick={() => fileInput.current && fileInput.current.click()}
        >
          <div className="drop-title">{file ? file.name : "Drag & drop a repository zip here"}</div>
          <div className="small">
            {file
              ? `${(file.size / 1024 / 1024).toFixed(1)} MB — click to choose a different file`
              : "or click to browse · the zip must contain the .git directory"}
          </div>
          <input
            ref={fileInput}
            type="file"
            accept=".zip"
            style={{ display: "none" }}
            onChange={(e) => setFile(e.target.files[0] || null)}
          />
        </div>
      )}

      {error ? <div className="form-error">{String(error.message || error)}</div> : null}
    </Modal>
  );
}

export default function Repos() {
  const repos = useApi(() => api.repos(), []);
  const [adding, setAdding] = useState(false);
  const scanning = ((repos.data || []).some((r) => r.status === "scanning"));

  useEffect(() => {
    if (!scanning) return undefined;
    const t = setInterval(() => repos.reload(), 1500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanning, repos.reload]);

  const list = repos.data;

  return (
    <div className="page">
      <div className="page-head">
        <h1>Repositories</h1>
        <span className="sub">{list ? `${list.length} analyzed` : ""}</span>
        <span className="spacer" />
        <button className="btn btn-primary" onClick={() => setAdding(true)}>
          Add repository
        </button>
      </div>

      {repos.loading && !list ? (
        <div className="grid-cards">
          {[0, 1, 2].map((i) => (
            <div className="card" key={i}>
              <Skeleton lines={4} height={14} />
            </div>
          ))}
        </div>
      ) : repos.error && !list ? (
        <ErrorState error={repos.error} onRetry={repos.reload} />
      ) : list && list.length === 0 ? (
        <EmptyState
          title="No repositories yet"
          hint="Add one by cloning a git URL or uploading a zipped repository (with .git)."
        >
          <button className="btn btn-primary mt16" onClick={() => setAdding(true)}>
            Add repository
          </button>
        </EmptyState>
      ) : (
        <div className="grid-cards">
          {(list || []).map((r) => (
            <RepoCard
              key={r.id}
              repo={r}
              onOpen={() => navigate(["repos", r.id])}
              onDeleted={repos.reload}
            />
          ))}
        </div>
      )}

      {adding ? (
        <AddRepoModal
          onClose={() => setAdding(false)}
          onAdded={() => {
            setAdding(false);
            repos.reload();
          }}
        />
      ) : null}
    </div>
  );
}
