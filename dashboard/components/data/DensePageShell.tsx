import type { ReactNode } from "react";

import { BackLink } from "@/components/BackLink";
import { Breadcrumb, type Crumb } from "@/components/Breadcrumb";
import { Kicker } from "@/components/Kicker";
import { SourceTag } from "./SourceTag";

type Props = {
  kicker: string;
  title: string;
  description?: ReactNode;
  source?: string;
  asOf?: string;
  manual?: boolean;
  degraded?: boolean;
  breadcrumb?: Crumb[];
  backHref?: string;
  backLabel?: string;
  children: ReactNode;
};

/** Wrapper for dense data pages — does not affect editorial routes. */
export function DensePageShell({
  kicker,
  title,
  description,
  source,
  asOf,
  manual,
  degraded,
  breadcrumb,
  backHref,
  backLabel,
  children,
}: Props) {
  return (
    <div className="dense dense-grid">
      {backHref && <BackLink href={backHref} label={backLabel ?? "返回"} />}
      {breadcrumb && breadcrumb.length > 0 && <Breadcrumb items={breadcrumb} />}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Kicker tone="accent">{kicker}</Kicker>
          <h1 className="mt-2 font-sans text-3xl font-semibold tracking-tight text-ink">{title}</h1>
        </div>
        {(source || asOf) && (
          <SourceTag source={source} asOf={asOf} manual={manual} degraded={degraded} className="mt-1" />
        )}
      </div>
      {description && (
        <p className="mt-3 max-w-prose font-sans text-body text-ink-soft">{description}</p>
      )}
      <div className="mt-8">{children}</div>
    </div>
  );
}
