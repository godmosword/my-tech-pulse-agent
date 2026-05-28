type Props = {
  title: string;
  children: React.ReactNode;
  note?: string;
};

export function BackfillHint({ title, children, note }: Props) {
  return (
    <div className="section-band font-sans text-body text-ink-soft">
      <p className="font-semibold text-ink">{title}</p>
      <div className="mt-2 space-y-2 text-meta leading-relaxed">{children}</div>
      {note && <p className="mt-3 text-meta text-ink-faint">{note}</p>}
    </div>
  );
}

export function BackfillCode({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded border border-rule bg-paper px-3 py-2 font-mono text-[12px] leading-relaxed text-ink">
      {children}
    </pre>
  );
}
