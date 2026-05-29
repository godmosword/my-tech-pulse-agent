import type { IndirectExposure } from "@/lib/exposure-passthrough";

type Props = {
  exposures: IndirectExposure[];
};

export function ExposurePassthroughCard({ exposures }: Props) {
  if (!exposures.length) return null;

  return (
    <section className="mt-8 rounded border border-amber-500/40 bg-amber-500/5 p-4">
      <h2 className="font-sans text-meta uppercase tracking-widest text-amber-700 dark:text-amber-400">
        曝險穿透
      </h2>
      <ul className="mt-3 space-y-2">
        {exposures.map((e, i) => (
          <li
            key={`${e.kind}-${i}`}
            className={`font-sans text-body ${
              e.severity === "warn" ? "text-amber-800 dark:text-amber-300" : "text-ink-soft"
            }`}
          >
            {e.message_zh}
          </li>
        ))}
      </ul>
    </section>
  );
}
