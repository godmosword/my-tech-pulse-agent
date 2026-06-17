import { MaterialMoveRow } from "@/components/data/MaterialMoveRow";
import { MaterialMovesFromBrief } from "@/components/InvestBriefSections";
import { listLatestItems } from "@/lib/firestore";
import { loadInvestBrief } from "@/lib/invest-brief";
import { materialMoveFromItem } from "@/lib/material-move";
import { rankItemsByImpact } from "@/lib/portfolio-brief";

const LOOKBACK_DAYS = 3;
const BRIEF_LIMIT = 6;

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
          <MaterialMoveRow key={item.id} view={materialMoveFromItem(item)} />
        ))}
      </ul>
      <p className="mt-2 font-sans text-meta text-ink-faint">
        依「對你持倉的衝擊」排序；分級為注意度（需要注意／需要複核），預設保守，非投資建議。
      </p>
    </div>
  );
}
