/** @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { RenderableItem } from "@/lib/types";

import { InstantCard } from "./InstantCard";

afterEach(() => {
  cleanup();
});

function item(overrides: Partial<RenderableItem> = {}): RenderableItem {
  return {
    id: "item-1",
    title: "Nvidia launches new chip architecture",
    zh_title: "輝達發表新一代資料中心晶片架構",
    summary: "Nvidia announced a new GPU architecture for data centers.",
    zh_summary: "輝達宣布新一代資料中心 GPU 架構。",
    zh_body: "",
    source_url: "https://example.com/story",
    source_name: "Source",
    entity: "Nvidia",
    category: "ai",
    kind: "instant_summary",
    score: 7,
    score_status: "ok",
    hook: "",
    tickers: ["ACME"],
    what_happened: "",
    why_it_matters: "",
    takeaway: null,
    portfolio_impact: null,
    published_at_iso: "2026-08-16T10:00:00.000Z",
    delivered_at_iso: "2026-08-16T10:00:00.000Z",
    themes: [],
    ...overrides,
  };
}

describe("InstantCard", () => {
  it("shows bilingual compare without zh_body when authenticated", () => {
    render(
      <InstantCard
        item={item()}
        authenticated
        returnToPath="/item/item-1"
        variant="full"
      />,
    );
    expect(screen.getByRole("heading", { name: "輝達發表新一代資料中心晶片架構" })).toBeInTheDocument();
    expect(screen.getByText("輝達宣布新一代資料中心 GPU 架構。")).toBeInTheDocument();
    expect(screen.getByText("中英對照")).toBeInTheDocument();
    expect(
      screen.getByText("Nvidia announced a new GPU architecture for data centers."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Nvidia launches new chip architecture"),
    ).toBeInTheDocument();
  });

  it("does not show bilingual compare on list variant", () => {
    render(
      <InstantCard
        item={item()}
        authenticated
        returnToPath="/item/item-1"
        variant="list"
      />,
    );
    expect(screen.queryByText("中英對照")).not.toBeInTheDocument();
  });

  it("links tickers to the earnings ticker page", () => {
    render(
      <InstantCard
        item={item()}
        authenticated
        returnToPath="/item/item-1"
        variant="full"
      />,
    );
    const link = screen.getByRole("link", { name: /ACME/ });
    expect(link.getAttribute("href")).toBe("/earnings/ACME");
  });
});
