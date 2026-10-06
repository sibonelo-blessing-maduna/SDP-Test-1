import { fmtInt, fmtFloat } from "../hooks";

// KPI row for the repository overview (or any metrics object).
export default function StatCards({ metrics }) {
  if (!metrics) return null;
  const all = metrics.all || {};
  const count = metrics.commit_set ? metrics.commit_set.count : null;
  const cards = [
    { label: "Commits (H)", value: fmtInt(count), sub: "selected commit set" },
    { label: "Added", value: fmtInt(all.added), cls: "pos" },
    { label: "Removed", value: fmtInt(all.removed), cls: "neg" },
    {
      label: "Growth",
      value: fmtInt(all.growth),
      cls: (Number(all.growth) || 0) >= 0 ? "pos" : "neg",
      sub: "added − removed",
    },
    { label: "Churn", value: fmtInt(all.churn), sub: "added + removed" },
    { label: "Modifications", value: fmtInt(all.modifications), sub: "commits touching this object" },
    { label: "Mod. frequency", value: fmtFloat(all.modification_frequency, 4), sub: "λ>0 / |H|" },
    { label: "Churn rate", value: fmtFloat(all.churn_rate, 2), sub: "churn / |H|" },
  ];
  return (
    <div className="kpi-grid">
      {cards.map((c) => (
        <div className="kpi" key={c.label}>
          <div className="k-label">{c.label}</div>
          <div className={"k-value " + (c.cls || "")}>{c.value}</div>
          {c.sub ? <div className="k-sub">{c.sub}</div> : null}
        </div>
      ))}
    </div>
  );
}
