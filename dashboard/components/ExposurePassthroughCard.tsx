import type { IndirectExposure } from "@/lib/exposure-passthrough";

type Props = {
  exposures: IndirectExposure[];
};

export function ExposurePassthroughCard({ exposures }: Props) {
  if (!exposures.length) return null;

  return (
    <section className="mt-8 rounded border border-warn/40 bg-warn-bg p-4">
      <h2 className="font-sans text-meta uppercase tracking-widest text-warn">
        曝險穿透
      </h2>
      <ul className="mt-3 space-y-2">
        {exposures.map((e, i) => (
          <li
            key={`${e.kind}-${i}`}
            className={`font-sans text-body ${
              e.severity === "warn" ? "text-warn" : "text-ink-soft"
            }`}
          >
            {e.message_zh}
          </li>
        ))}
      </ul>
    </section>
  );
}
