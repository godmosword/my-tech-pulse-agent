import type { ReactNode } from "react";

export type DataColumn<T> = {
  key: string;
  header: string;
  align?: "left" | "right";
  numeric?: boolean;
  mobileLabel?: string;
  render?: (row: T) => ReactNode;
};

type Props<T> = {
  columns: DataColumn<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  /** Optional class on desktop table rows */
  rowClassName?: (row: T) => string | undefined;
};

function cellContent<T>(row: T, col: DataColumn<T>): ReactNode {
  if (col.render) return col.render(row);
  const val = (row as Record<string, unknown>)[col.key];
  if (val == null) return "—";
  return String(val);
}

export function DataTable<T>({ columns, rows, rowKey, rowClassName }: Props<T>) {
  return (
    <>
      {/* Mobile: card stack */}
      <div className="data-table-cards sm:hidden">
        {rows.map((row, idx) => (
          <div key={rowKey(row, idx)} className="data-table-card">
            {columns.map((col) => (
              <div key={col.key} className="data-table-card-row">
                <span className="data-table-card-label shrink-0">
                  {col.mobileLabel ?? col.header}
                </span>
                <span
                  className={`min-w-0 break-words text-right ${col.numeric ? "data-num" : ""} ${
                    col.align === "right" ? "text-ink" : ""
                  }`}
                >
                  {cellContent(row, col)}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Desktop: table */}
      <div className="hidden sm:block">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={col.align === "left" || col.key === columns[0]?.key ? "" : "text-right"}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={rowKey(row, idx)} className={rowClassName?.(row)}>
                {columns.map((col, colIdx) => (
                  <td
                    key={col.key}
                    className={`${col.numeric || col.align === "right" || colIdx > 0 ? "text-right" : ""} ${
                      col.numeric ? "data-num" : ""
                    }`}
                  >
                    {cellContent(row, col)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
