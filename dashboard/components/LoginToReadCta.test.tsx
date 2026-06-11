/** @vitest-environment jsdom */

import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { LoginToReadCta } from "./LoginToReadCta";

afterEach(() => {
  cleanup();
});

describe("LoginToReadCta", () => {
  it("links to login with returnTo", () => {
    render(<LoginToReadCta returnToPath="/item/abc" />);
    const link = screen.getByRole("link", { name: "登入閱讀完整內容" });
    expect(link.getAttribute("href")).toBe(
      "/login?returnTo=%2Fitem%2Fabc",
    );
  });
});
