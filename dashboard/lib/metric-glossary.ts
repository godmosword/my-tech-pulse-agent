/**
 * Central plain-language glossary for the dashboard's quant metrics. Each entry
 * says what the metric is and which direction is "good", so the UI never relies
 * on color alone. Keep all metric explanations here (single source) rather than
 * scattering tooltips across components.
 */

export type MetricKey =
  | "ic"
  | "hit_rate"
  | "quantile_spread"
  | "posture"
  | "conviction";

export interface MetricInfo {
  label_zh: string;
  hint_zh: string;
}

export const METRIC_GLOSSARY: Record<MetricKey, MetricInfo> = {
  ic: {
    label_zh: "IC（Spearman）",
    hint_zh:
      "訊號分數與後續報酬的等級相關性。越接近 +1 越有預測力，0 代表無關，負值代表方向相反。",
  },
  hit_rate: {
    label_zh: "命中率",
    hint_zh: "方向判斷正確的比例。越高越好，50% 等於擲銅板。",
  },
  quantile_spread: {
    label_zh: "分位價差",
    hint_zh:
      "高分組與低分組的報酬差。正值且越大，代表分數越能區分強弱；接近 0 代表分數沒有鑑別力。",
  },
  posture: {
    label_zh: "注意度分級",
    hint_zh:
      "對你部位的關注程度（無需動作／需要注意／需要複核／風險升高），是提醒強度，非買賣建議。",
  },
  conviction: {
    label_zh: "資料完整度",
    hint_zh:
      "此訊號背後輸入資料的齊全程度，越高代表依據越完整；不等於看多／看空的強度。",
  },
};

export function metricHint(key: MetricKey): MetricInfo {
  return METRIC_GLOSSARY[key];
}
