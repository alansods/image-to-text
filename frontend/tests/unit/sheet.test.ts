import { describe, expect, it } from "vitest";

import { pageLayout } from "@/lib/sheet";
import type { Block, Page } from "@/lib/types/document";

function block(id: string, order: number, x: number, w: number, extra: Partial<Block> = {}): Block {
  return {
    id, type: "paragraph", bbox: { x, y: order * 100, w, h: 50 }, order, column: 0, align: "left",
    rel_size: 1, font_pt: null, words: [], cells: [], items: [], image_ref: null, confidence: 1, ...extra,
  };
}

function page(blocks: Block[], columns = 1): Page {
  return {
    index: 0, width: 2480, height: 3508, page_size: { w_pt: 595, h_pt: 842 }, columns,
    image_ref: "pages/0.png", blank: false, quality_issues: [], blocks,
    counts: { accepted: 0, resolved: 0, uncertain: 0, edited: 0 },
  };
}

describe("layout da folha", () => {
  it("título largo atravessa; o resto vai para as colunas; cabeçalho e rodapé à parte", () => {
    const layout = pageLayout(
      page(
        [
          block("h", 0, 300, 1800, { type: "header" }),
          block("t", 1, 300, 1880, { type: "heading" }),
          block("l", 2, 300, 850, { column: 0 }),
          block("r", 3, 1300, 850, { column: 1 }),
          block("f", 4, 300, 400, { type: "footer" }),
        ],
        2,
      ),
    );

    expect(layout.header.map((b) => b.id)).toEqual(["h"]);
    expect(layout.footer.map((b) => b.id)).toEqual(["f"]);
    expect(layout.body.map((g) => g.lanes.map((lane) => lane.map((b) => b.id)))).toEqual([
      [["t"]],
      [["l"], ["r"]],
    ]);
  });
});
