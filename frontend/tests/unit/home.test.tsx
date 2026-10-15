import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "@/app/page";

describe("página inicial (esqueleto)", () => {
  it("mostra o nome do produto como título", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { level: 1, name: "image-to-text" })).toBeInTheDocument();
  });
});
