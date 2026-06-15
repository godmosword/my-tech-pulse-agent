import Link from "next/link";

import { MaterialMovesFromBrief } from "@/components/InvestBriefSections";
import { listLatestItems } from "@/lib/firestore";
import { loadInvestBrief } from "@/lib/invest-brief";
import {
  IMPACT_POSTURE_CLASS,
  IMPACT_POSTURE_LABEL,
  impactPosture,
  impactScore,
  rankItemsByImpact,
} from "@/lib/portfolio-brief";
import { displayTitle, type RenderableItem } from "@/lib/types";

const LOOKBACK_DAYS = 3;
const BRIEF_LIMIT = 6;

function BriefRow({ item }: { item: RenderableItem }) {
  const impact = item.portfolio_impact;
  const posture = impactPosture(impactScore(item));
  const affected = (impact?.affected_positions ?? []).map((a) => a.ticker);
  return (
    <li className="border-b border-rule py-2 last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <Link
          href={`/item/${encodeURIComponent(item.id)}`}
          className="font-sans text-body text-ink hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {displayTitle(item)}
        </Link>
        <span
          className={`shrink-0 font-sans text-meta font-semibold ${IMPACT_POSTURE_CLASS[posture]}`}
        >
          {IMPACT_POSTURE_LABEL[posture]}
        </span>
      </div>
      <p className="mt-1 font-sans text-meta text-ink-soft">
        {impact?.rationale_zh}
        {affected.length > 0 && (
          <span className="text-ink-faint">
            {" "}
            · 影響 {affected.join("、")}
          </span>
        )}
      </p>
    </li>
  );
}

export async function DecisionBriefSection() {
  // Prefer the artifact: it carries authoritative posture (evidence + cooldown).
  const brief = loadInvestBrief();
  if (brief && brief.material_items.length > 0) {
    return <MaterialMovesFromBrief items={brief.material_items} />;
  }

  // Fallback: live ranking with the band-only label when no artifact exists yet.
  const since = new Date(Date.now() - LOOKBACK_DAYS * 24 * 60 * 60 * 1000);
  const items = await listLatestItems({ limit: 150, since });
  const ranked = rankItemsByImpact(items, BRIEF_LIMIT);

  if (ranked.length === 0) {
    return (
      <p className="font-sans text-body text-ink-soft">
        近三日尚無對你部位有實質影響的新聞。新內容會在每日 pipeline 完成後自動出現。
        <span className="block text-meta text-ink-faint">
          分級為注意度（無需動作／需要注意／需要複核），非投資建議。
        </span>
      </p>
    );
  }

  return (
    <div>
      <ul>
        {ranked.map((item) => (
          <BriefRow key={item.id} item={item} />
        ))}
      </ul>
      <p className="mt-2 font-sans text-meta text-ink-faint">
        依「對你持倉的衝擊」排序；分級為注意度（需要注意／需要複核），預設保守，非投資建議。
      </p>
    </div>
  );
}
