import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((path: string) => Promise.resolve({
      ok: true,
      json: async () => path.includes("entries") ? { items: [] } : [],
    })));
  });
  it("shows scan controls", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "文件浏览与扫描" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始扫描" })).toBeInTheDocument();
  });
});
