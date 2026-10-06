import { useMemo, useState } from "react";

/**
 * Generic sortable table.
 * columns: [{ key, label, align?, sortable?, fmt?, render? }]
 * rows carry full-precision metric numbers; formatting is per column.
 */
export default function Table({
  columns,
  rows,
  rowKey,
  onRowClick,
  isRowSelected,
  initialSort,
  empty,
}) {
  const [sort, setSort] = useState(initialSort || null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const { key, dir } = sort;
    return [...rows].sort((a, b) => {
      const va = a[key];
      const vb = b[key];
      if (va === vb) return 0;
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      const bothNum = typeof va === "number" && typeof vb === "number";
      return (bothNum ? va - vb : String(va).localeCompare(String(vb))) * dir;
    });
  }, [rows, sort]);

  const headerClick = (c) => {
    if (c.sortable === false) return;
    setSort((s) =>
      s && s.key === c.key ? { key: c.key, dir: -s.dir } : { key: c.key, dir: -1 }
    );
  };

  if (!rows.length && empty) return empty;

  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={
                  (c.align === "right" ? "num " : "") + (c.sortable === false ? "no-sort" : "")
                }
                onClick={() => headerClick(c)}
              >
                {c.label}
                {sort && sort.key === c.key ? (
                  <span className="sort-ind">{sort.dir === 1 ? "▲" : "▼"}</span>
                ) : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr
              key={rowKey ? rowKey(r) : i}
              className={
                (onRowClick ? "clickable" : "") +
                (isRowSelected && isRowSelected(r) ? " selected" : "")
              }
              onClick={onRowClick ? () => onRowClick(r) : undefined}
            >
              {columns.map((c) => (
                <td key={c.key} className={c.align === "right" ? "num" : ""}>
                  {c.render ? c.render(r) : c.fmt ? c.fmt(r[c.key]) : String(r[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
