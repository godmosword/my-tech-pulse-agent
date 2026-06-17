import { MaterialMoveRow } from "@/components/data/MaterialMoveRow";
import { MetricHint } from "@/components/MetricHint";
import { materialMoveFromBrief } from "@/lib/material-move";
import { type BriefItem, type InvestBrief } from "@/lib/invest-brief";

function pct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

export function MaterialMovesFromBrief({ items }: { items: BriefItem[] }) {
  return (
    <div>
      <ul>
        {items.map((it) => (
          <MaterialMoveRow key={it.id} view={materialMoveFromBrief(it)} />
        ))}
      </ul>
      <p className="mt-2 flex items-center gap-1 font-sans text-meta text-ink-faint">
        <span>依「對你持倉的衝擊」排序；分級為注意度，預設保守、非投資建議。</span>
        <MetricHint metric="posture" />
      </p>
    </div>
  );
}

export function PortfolioPulseSection({ brief }: { brief: InvestBrief | null }) {
  const pulse = brief?.portfolio_pulse;
  if (!pulse) {
    return (
      <p className="font-sans text-body text-ink-soft">
        尚無部位脈動快照。pipeline 後執行 build_invest_brief.py 後出現。
      </p>
    );
  }
  return (
    <div className="font-sans text-meta text-ink-soft">
      <p>
        最大持倉占比 <span className="font-mono text-ink">{pct(pulse.concentration_top_pct)}</span>
        {pulse.top_holdings.length > 0 && (
          <span className="text-ink-faint">
            {" "}
            · {pulse.top_holdings.map((h) => `${h.ticker} ${pct(h.weight)}`).join("、")}
          </span>
        )}
      </p>
      {pulse.risk_flags.length > 0 ? (
        <ul className="mt-2">
          {pulse.risk_flags.map((f, i) => (
            <li key={`${f.kind}-${i}`} className="text-warn">
              ⚠ {f.message_zh}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-ink-faint">未偵測到集中度／相關性風險旗標。</p>
      )}
    </div>
  );
}

export function CatalystWatchSection({ brief }: { brief: InvestBrief | null }) {
  const cats = brief?.catalyst_watch ?? [];
  if (cats.length === 0) {
    return (
      <p className="font-sans text-body text-ink-soft">未來兩週無已登錄的催化劑。</p>
    );
  }
  return (
    <ul className="font-sans text-meta text-ink-soft">
      {cats.map((c, i) => (
        <li key={`${c.ticker}-${c.date}-${i}`} className="py-0.5">
          <span className="font-mono text-ink">{c.date}</span>{" "}
          <span className="text-ink-faint">{c.ticker}</span> · {c.note || c.type}
        </li>
      ))}
    </ul>
  );
}

export function ThesisUpdatesSection({ brief }: { brief: InvestBrief | null }) {
  const updates = (brief?.thesis_updates ?? []).filter((t) => t.thesis);
  if (updates.length === 0) {
    return (
      <p className="font-sans text-body text-ink-soft">
        尚無持倉論點（在 config/portfolio.yaml 為持倉加上 thesis 後出現）。
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {updates.map((t) => (
        <div key={t.ticker}>
          <p className="font-sans text-body text-ink">
            <span className="font-mono">{t.ticker}</span> · {t.thesis}
          </p>
          {t.supporting.length > 0 && (
            <p className="font-sans text-meta text-pos">支持：{t.supporting.join("；")}</p>
          )}
          {t.contradicting.length > 0 && (
            <p className="font-sans text-meta text-neg">反駁：{t.contradicting.join("；")}</p>
          )}
          {t.upcoming.length > 0 && (
            <p className="font-sans text-meta text-ink-faint">催化劑：{t.upcoming.join("；")}</p>
          )}
          {t.supporting.length === 0 && t.contradicting.length === 0 && (
            <p className="font-sans text-meta text-ink-faint">尚無已結算的訊號證據。</p>
          )}
        </div>
      ))}
    </div>
  );
}
