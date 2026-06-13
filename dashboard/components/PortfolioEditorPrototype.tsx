"use client";

import { useCallback, useMemo, useState } from "react";

export interface EditablePosition {
  ticker: string;
  shares: number;
  avg_cost: number | null;
}

interface PortfolioEditorPrototypeProps {
  initialPositions: EditablePosition[];
  asOf: string;
  baseCurrency: string;
}

function toYaml(
  positions: EditablePosition[],
  asOf: string,
  baseCurrency: string,
): string {
  const lines = [
    "# Exported from dashboard preview — review before replacing config/portfolio.yaml",
    `base_currency: ${baseCurrency}`,
    `as_of: "${asOf}"`,
    "positions:",
  ];
  for (const p of positions) {
    const cost =
      p.avg_cost != null && Number.isFinite(p.avg_cost) ? p.avg_cost.toFixed(2) : "null";
    lines.push(`  - { ticker: ${p.ticker.toUpperCase()}, shares: ${p.shares}, avg_cost: ${cost} }`);
  }
  lines.push(
    "target_allocation:",
    "  ai_silicon: 0.40",
    "  semiconductor: 0.25",
    "  memory: 0.15",
    "  equipment: 0.10",
    "  cloud_software: 0.10",
  );
  return lines.join("\n") + "\n";
}

export function PortfolioEditorPrototype({
  initialPositions,
  asOf,
  baseCurrency,
}: PortfolioEditorPrototypeProps) {
  const [rows, setRows] = useState<EditablePosition[]>(() =>
    initialPositions.map((p) => ({ ...p })),
  );

  const updateRow = useCallback(
    (index: number, patch: Partial<EditablePosition>) => {
      setRows((prev) =>
        prev.map((row, i) => (i === index ? { ...row, ...patch } : row)),
      );
    },
    [],
  );

  const addRow = useCallback(() => {
    setRows((prev) => [...prev, { ticker: "", shares: 0, avg_cost: null }]);
  }, []);

  const removeRow = useCallback((index: number) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const exportYaml = useCallback(() => {
    const yaml = toYaml(rows, asOf, baseCurrency);
    const blob = new Blob([yaml], { type: "text/yaml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `portfolio-preview-${asOf || "export"}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  }, [rows, asOf, baseCurrency]);

  const validCount = useMemo(
    () => rows.filter((r) => r.ticker.trim() && r.shares > 0).length,
    [rows],
  );

  return (
    <section className="section-band mt-8">
      <div className="mb-4 rounded border border-warn/40 bg-warn-bg px-3 py-2 font-sans text-meta text-ink">
        預覽模式 — 變更尚未保存。調整後可匯出 YAML，再手動更新{" "}
        <code className="font-mono">config/portfolio.yaml</code> 或執行 IBKR 匯入腳本。
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2
          id="portfolio-editor-heading"
          className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft"
        >
          持倉編輯（原型）
        </h2>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={addRow}
            className="min-h-[44px] rounded border border-rule px-3 font-sans text-meta text-ink hover:border-accent hover:text-accent"
          >
            新增列
          </button>
          <button
            type="button"
            onClick={exportYaml}
            disabled={validCount === 0}
            className="min-h-[44px] rounded border border-accent/40 bg-accent/10 px-3 font-sans text-meta text-accent disabled:opacity-40"
          >
            匯出 YAML
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table
          className="data-table w-full min-w-[480px]"
          aria-labelledby="portfolio-editor-heading"
        >
          <thead>
            <tr>
              <th scope="col" className="text-left">代號</th>
              <th scope="col" className="text-right">股數</th>
              <th scope="col" className="text-right">成本</th>
              <th scope="col" className="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={`${row.ticker}-${i}`}>
                <td>
                  <input
                    type="text"
                    value={row.ticker}
                    onChange={(e) =>
                      updateRow(i, { ticker: e.target.value.toUpperCase() })
                    }
                    placeholder="NVDA"
                    className="w-full min-w-[5rem] rounded border border-rule bg-paper px-2 py-1.5 font-mono text-body text-ink"
                    aria-label={`代號 ${i + 1}`}
                  />
                </td>
                <td className="text-right">
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={row.shares || ""}
                    onChange={(e) =>
                      updateRow(i, { shares: Number(e.target.value) || 0 })
                    }
                    className="w-24 rounded border border-rule bg-paper px-2 py-1.5 text-right font-mono text-body text-ink"
                    aria-label={`股數 ${i + 1}`}
                  />
                </td>
                <td className="text-right">
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={row.avg_cost ?? ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      updateRow(i, {
                        avg_cost: v === "" ? null : Number(v),
                      });
                    }}
                    placeholder="—"
                    className="w-28 rounded border border-rule bg-paper px-2 py-1.5 text-right font-mono text-body text-ink"
                    aria-label={`成本 ${i + 1}`}
                  />
                </td>
                <td className="text-right">
                  <button
                    type="button"
                    onClick={() => removeRow(i)}
                    className="min-h-[44px] px-2 font-sans text-meta text-ink-soft hover:text-neg"
                  >
                    刪除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && (
        <p className="mt-3 font-sans text-body text-ink-faint">尚無列；按「新增列」開始。</p>
      )}
    </section>
  );
}
