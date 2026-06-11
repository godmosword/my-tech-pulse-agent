"use client";

import { useCallback, useState } from "react";

type Props = {
  hasMore: boolean;
  onLoadMore: () => Promise<void>;
  className?: string;
};

export function LoadMoreButton({ hasMore, onLoadMore, className = "" }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await onLoadMore();
    } catch {
      setError("載入失敗，請稍後再試。");
    } finally {
      setLoading(false);
    }
  }, [onLoadMore]);

  if (!hasMore && !error) return null;

  return (
    <div className={`mt-8 space-y-3 text-center ${className}`.trim()}>
      {error ? (
        <div className="space-y-2">
          <p className="font-sans text-body text-neg">{error}</p>
          <button
            type="button"
            onClick={() => void handleLoad()}
            disabled={loading}
            className="rounded border border-rule px-4 py-2 font-sans text-meta uppercase tracking-[0.08em] text-ink hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            重試
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => void handleLoad()}
          disabled={loading}
          className="rounded border border-rule px-4 py-2 font-sans text-meta uppercase tracking-[0.08em] text-ink-soft hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "載入中…" : "載入更多"}
        </button>
      )}
    </div>
  );
}
