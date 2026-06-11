/** @vitest-environment jsdom */

import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

import { NavSearch } from "./NavSearch";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("NavSearch", () => {
  beforeEach(() => {
    push.mockReset();
  });

  it("debounces API calls and renders grouped results", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        query: "NVDA",
        news: [{ id: "n1", title: "NVDA 新聞", href: "/item/n1" }],
        earnings: [
          {
            ticker: "NVDA",
            company: "NVIDIA",
            quarter_label: "FY2026Q1",
            href: "/earnings/NVDA",
          },
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<NavSearch variant="rail" />);
    const input = screen.getByRole("combobox", { name: "搜尋新聞或財報" });
    fireEvent.change(input, { target: { value: "NVDA" } });
    fireEvent.focus(input);

    await waitFor(
      () => {
        expect(fetchMock).toHaveBeenCalledWith(
          "/api/v1/search?q=NVDA",
          expect.objectContaining({ signal: expect.any(AbortSignal) }),
        );
      },
      { timeout: 2000 },
    );

    await waitFor(() => {
      expect(screen.getByText("新聞")).toBeTruthy();
      expect(screen.getByText("財報")).toBeTruthy();
      expect(screen.getByText("NVDA 新聞")).toBeTruthy();
    });
  });

  it("navigates on Enter for active option", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          query: "NVDA",
          news: [{ id: "n1", title: "NVDA 新聞", href: "/item/n1" }],
          earnings: [],
        }),
      }),
    );

    render(<NavSearch variant="rail" />);
    const input = screen.getByRole("combobox", { name: "搜尋新聞或財報" });
    fireEvent.change(input, { target: { value: "NVDA" } });

    await waitFor(() => {
      expect(screen.getByText("NVDA 新聞")).toBeTruthy();
    });

    fireEvent.keyDown(input, { key: "Enter" });
    expect(push).toHaveBeenCalledWith("/item/n1");
  });

  it("shows empty-state message when no hits", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ query: "ZZZZ", news: [], earnings: [] }),
      }),
    );

    render(<NavSearch variant="rail" />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "ZZZZ" } });

    await waitFor(() => {
      expect(screen.getByText("找不到符合的新聞或財報")).toBeTruthy();
    });
  });
});
