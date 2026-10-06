import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { useEffect, useRef, useState } from "react";
import { fmtCompact, fmtDate, authorName } from "../hooks";

export const PALETTE = [
  "#58a6ff", "#3fb950", "#d29922", "#bc8cff", "#f778ba",
  "#39c5cf", "#f85149", "#e3b341", "#7ee787", "#a5d6ff",
];

const TICK = { fill: "#8b949e", fontSize: 11 };
const AXIS_LINE = { stroke: "#30363d" };

function DarkTip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div
      style={{
        background: "#161b22",
        border: "1px solid #30363d",
        borderRadius: 8,
        padding: "8px 10px",
        fontSize: 12,
        maxWidth: 340,
      }}
    >
      {label !== undefined && label !== null ? (
        <div style={{ color: "#8b949e", marginBottom: 4 }}>{String(label)}</div>
      ) : null}
      {payload.map((p) => {
        const v = p.dataKey === "removedNeg" ? Math.abs(p.value) : p.value;
        return (
          <div key={p.dataKey} style={{ color: p.color || p.payload?.fill || "#e6edf3" }}>
            {p.name}: {Number(v).toLocaleString("en-US")}
          </div>
        );
      })}
    </div>
  );
}

// Diverging churn over time: added (positive) vs removed (negative), growth line.
export function ChurnArea({ data }) {
  const rows = (data || []).map((p) => ({
    label: fmtDate(p.t),
    added: Number(p.added) || 0,
    removedNeg: -(Number(p.removed) || 0),
    growth: Number(p.growth) || 0,
  }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 4 }} stackOffset="sign">
        <CartesianGrid stroke="#21262d" vertical={false} />
        <XAxis dataKey="label" tick={TICK} minTickGap={28} axisLine={AXIS_LINE} tickLine={false} />
        <YAxis tick={TICK} tickFormatter={fmtCompact} axisLine={false} tickLine={false} width={56} />
        <Tooltip content={<DarkTip />} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area type="monotone" dataKey="added" name="added" stackId="1" stroke="#3fb950" fill="#238636" fillOpacity={0.35} strokeWidth={1.5} />
        <Area type="monotone" dataKey="removedNeg" name="removed" stackId="1" stroke="#f85149" fill="#da3633" fillOpacity={0.35} strokeWidth={1.5} />
        <Line type="monotone" dataKey="growth" name="growth" stroke="#58a6ff" dot={false} strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Horizontal rank bars — used for top files and top authors.
export function RankBar({ rows, nameKey = "name", valueKey = "churn", color = "#58a6ff", wide = 170 }) {
  const data = (rows || []).map((r) => ({
    ...r,
    [nameKey]: r.name || authorName(r.author || ""),
  }));
  const height = Math.max(data.length * 28 + 24, 120);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 28, bottom: 4, left: 8 }}>
        <CartesianGrid stroke="#21262d" horizontal={false} />
        <XAxis type="number" tick={TICK} tickFormatter={fmtCompact} axisLine={AXIS_LINE} tickLine={false} />
        <YAxis
          type="category"
          dataKey={nameKey}
          width={wide}
          tick={{ fill: "#8b949e", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip content={<DarkTip />} cursor={{ fill: "rgba(139,148,158,0.08)" }} />
        <Bar dataKey={valueKey} fill={color} radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// Squarified layout: each item gets an area proportional to its value.
function squarify(items, x, y, w, h) {
  const sorted = items.slice().sort((a, b) => b.value - a.value);
  const total = sorted.reduce((s, i) => s + i.value, 0) || 1;
  const areas = sorted.map((i) => (i.value * w * h) / total);
  const worst = (slice, sum, side) => {
    const s2 = sum * sum;
    let m = 0;
    for (const a of slice) {
      const r = Math.max((side * side * a) / s2, s2 / (side * side * a));
      if (r > m) m = r;
    }
    return m;
  };
  const out = [];
  let rx = x;
  let ry = y;
  let rw = w;
  let rh = h;
  let i = 0;
  while (i < areas.length && rw > 0 && rh > 0) {
    const side = Math.max(1, Math.min(rw, rh));
    let j = i;
    let sum = 0;
    let best = Infinity;
    while (j < areas.length) {
      const nsum = sum + areas[j];
      const nworst = worst(areas.slice(i, j + 1), nsum, side);
      if (nworst > best) break;
      sum = nsum;
      best = nworst;
      j += 1;
    }
    if (j === i) {
      sum = areas[i];
      j = i + 1;
    }
    const row = sorted.slice(i, j).map((it, k) => ({ ...it, area: areas[i + k] }));
    if (rw >= rh) {
      const colW = sum / rh;
      let cy = ry;
      for (const it of row) {
        const cellH = it.area / colW;
        out.push({ ...it, x: rx, y: cy, w: colW, h: cellH });
        cy += cellH;
      }
      rx += colW;
      rw -= colW;
    } else {
      const rowH = sum / rw;
      let cx = rx;
      for (const it of row) {
        const cellW = it.area / rowH;
        out.push({ ...it, x: cx, y: ry, w: cellW, h: rowH });
        cx += cellW;
      }
      ry += rowH;
      rh -= rowH;
    }
    i = j;
  }
  return out;
}

// Root-children treemap sized by churn — hand-rolled squarified SVG so tiles
// and labels stay crisp at any panel width.
export function DirTreemap({ rows, height = 280 }) {
  const box = useRef(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    const measure = () => setWidth(Math.floor(el.getBoundingClientRect().width));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const items = (rows || [])
    .map((r) => ({
      name: String(r.name || r.path || "?"),
      value: Math.max(Number(r.churn) || 0, 1),
    }))
    .filter((i) => i.value > 0);
  const rects = width > 0 && items.length ? squarify(items, 0, 0, width, height) : [];
  return (
    <div ref={box} style={{ width: "100%" }}>
      {width > 0 && rects.length ? (
        <svg width={width} height={height} role="img" aria-label="Root children sized by churn">
          {rects.map((r, idx) => {
            const w = Math.max(0, r.w - 3);
            const h = Math.max(0, r.h - 3);
            const maxChars = Math.max(3, Math.floor(w / 7.2));
            const label = r.name.length > maxChars ? r.name.slice(0, maxChars - 1) + "…" : r.name;
            return (
              <g key={`${r.name}-${idx}`}>
                <title>{`${r.name} — churn ${fmtCompact(r.value)}`}</title>
                <rect
                  x={r.x + 1.5}
                  y={r.y + 1.5}
                  width={w}
                  height={h}
                  rx={3}
                  fill={PALETTE[idx % PALETTE.length]}
                  fillOpacity={0.25}
                  stroke="#0d1117"
                  strokeWidth={1.5}
                />
                {w > 56 && h > 26 ? (
                  <text x={r.x + 9} y={r.y + 20} fill="#e6edf3" fontSize={11}>
                    {label}
                  </text>
                ) : null}
                {w > 56 && h > 42 ? (
                  <text x={r.x + 9} y={r.y + 34} fill="#8b949e" fontSize={10}>
                    {fmtCompact(r.value)}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      ) : null}
    </div>
  );
}

// Ownership donut — share of churn per author (ownership == churn share per schema).
export function OwnershipDonut({ authors, max = 7 }) {
  const list = (authors || []).filter((a) => Number(a.churn) > 0);
  const top = list.slice(0, max);
  const rest = list.slice(max);
  const extra = rest.reduce((s, a) => s + (Number(a.churn) || 0), 0);
  const rows = top.map((a, i) => ({
    name: authorName(a.author),
    value: Number(a.churn) || 0,
    fill: PALETTE[i % PALETTE.length],
  }));
  if (extra > 0) rows.push({ name: "others", value: extra, fill: "#6e7681" });
  const total = rows.reduce((s, r) => s + r.value, 0) || 1;
  return (
    <div className="donut-wrap">
      <ResponsiveContainer width={210} height={210}>
        <PieChart>
          <Pie
            data={rows}
            dataKey="value"
            nameKey="name"
            innerRadius={54}
            outerRadius={88}
            strokeWidth={1}
            stroke="#0d1117"
          >
            {rows.map((r) => (
              <Cell key={r.name} fill={r.fill} />
            ))}
          </Pie>
          <Tooltip content={<DarkTip />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="legend">
        {rows.map((r) => (
          <div className="li" key={r.name}>
            <span className="dot" style={{ background: r.fill }} />
            <span className="nowrap" title={r.name}>
              {r.name.length > 22 ? r.name.slice(0, 21) + "…" : r.name}
            </span>
            <span className="val">{((r.value / total) * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Tiny pure-SVG sparkline (repo cards).
export function Sparkline({ points, width = 120, height = 32 }) {
  const pts = (points || []).map(Number).filter(Number.isFinite);
  if (pts.length < 2) return <div className="spark-empty" style={{ width, height }} />;
  const max = Math.max(...pts, 1);
  const step = width / (pts.length - 1);
  const d = pts
    .map((v, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${(height - (v / max) * (height - 4) - 2).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={width} height={height} className="spark" aria-hidden="true">
      <path d={d} fill="none" stroke="#58a6ff" strokeWidth="1.6" />
    </svg>
  );
}
