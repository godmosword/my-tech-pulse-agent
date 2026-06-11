/** @vitest-environment jsdom */

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoadMoreButton } from "./LoadMoreButton";

afterEach(() => {
  cleanup();
});

describe("LoadMoreButton", () => {
  it("renders load more and disables while loading", async () => {
    let resolveLoad: (() => void) | undefined;
    const onLoadMore = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveLoad = resolve;
        }),
    );

    render(<LoadMoreButton hasMore onLoadMore={onLoadMore} />);
    fireEvent.click(screen.getByRole("button", { name: "載入更多" }));
    expect(screen.getByRole("button", { name: "載入中…" })).toBeDisabled();

    resolveLoad?.();
    await waitFor(() => {
      expect(onLoadMore).toHaveBeenCalledTimes(1);
    });
  });

  it("shows error and retry on failure", async () => {
    const onLoadMore = vi.fn().mockRejectedValue(new Error("network"));
    render(<LoadMoreButton hasMore onLoadMore={onLoadMore} />);
    fireEvent.click(screen.getByRole("button", { name: "載入更多" }));

    await waitFor(() => {
      expect(screen.getByText("載入失敗，請稍後再試。")).toBeTruthy();
    });
    expect(screen.getByRole("button", { name: "重試" })).toBeTruthy();
  });

  it("renders nothing when no more data and no error", () => {
    const { container } = render(
      <LoadMoreButton hasMore={false} onLoadMore={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
