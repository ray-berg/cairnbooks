import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  it("renders the CairnBooks heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /cairnbooks/i })).toBeDefined();
  });

  it("renders the tagline", () => {
    render(<App />);
    expect(screen.getByText(/open-source double-entry/i)).toBeDefined();
  });
});
