import Link from "next/link";

import { loginReturnHref } from "@/lib/login-path";

type Props = {
  returnToPath: string;
  className?: string;
};

/** Prominent login CTA for gated reader content (public-read mode). */
export function LoginToReadCta({ returnToPath, className = "" }: Props) {
  return (
    <Link
      href={loginReturnHref(returnToPath)}
      className={`inline-flex items-center rounded border border-accent px-4 py-2 font-sans text-meta font-semibold uppercase tracking-[0.08em] text-accent hover:bg-accent/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${className}`.trim()}
    >
      登入閱讀完整內容
    </Link>
  );
}
