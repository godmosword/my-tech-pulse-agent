/** @vitest-environment jsdom */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Reveal } from "./Reveal";

type ObserverCb = (entries: { isIntersecting: boolean }[]) => void;
let lastCb: ObserverCb | null = null;

class MockObserver {
  constructor(cb: ObserverCb) {
    lastCb = cb;
  }
  observe() {}
  disconnect() {}
}

beforeEach(() => {
  lastCb = null;
  vi.stubGlobal("IntersectionObserver", MockObserver);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Reveal", () => {
  it("reveals its children once they intersect", async () => {
    render(
      <Reveal>
        <p>內容</p>
      </Reveal>,
    );
    const wrapper = screen.getByText("內容").parentElement!;
    expect(wrapper).not.toHaveAttribute("data-revealed");

    lastCb?.([{ isIntersecting: true }]);
    await waitFor(() => {
      expect(wrapper).toHaveAttribute("data-revealed", "true");
    });
  });
});
