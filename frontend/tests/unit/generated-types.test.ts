import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import type { Document } from "@/lib/types/document";
import { renderTypes, TYPE_NAMES } from "../../scripts/render-types.mjs";

const typesDir = join(__dirname, "..", "..", "lib", "types");

describe("tipos gerados do formato interno", () => {
  it.each(TYPE_NAMES)("lib/types/%s.ts corresponde ao schema exportado (não foi editado à mão)", async (name) => {
    const schema = JSON.parse(readFileSync(join(typesDir, "schema", `${name}.schema.json`), "utf8"));
    const committed = readFileSync(join(typesDir, `${name}.ts`), "utf8");

    expect(await renderTypes(schema)).toBe(committed);
  });

  it("descreve um documento com palavra em dúvida e alternativas", () => {
    const document: Document = {
      id: "d1",
      source_file: "contrato.pdf",
      pages: [
        {
          index: 0,
          width: 2480,
          height: 3508,
          page_size: { w_pt: 595.3, h_pt: 841.9 },
          columns: 1,
          image_ref: "pages/0.png",
          blank: false,
          blocks: [
            {
              id: "b1",
              type: "paragraph",
              bbox: { x: 0, y: 0, w: 500, h: 100 },
              order: 0,
              column: 0,
              align: "justify",
              rel_size: 1,
              words: [
                {
                  id: "w1",
                  text: "SlLVA",
                  bbox: { x: 10, y: 10, w: 80, h: 20 },
                  confidence: 0.64,
                  bold: true,
                  italic: false,
                  alternatives: [
                    { text: "SILVA", confidence: 0.82, source: "paddle" },
                    { text: "SlLVA", confidence: 0.64, source: "doctr" },
                  ],
                  status: "uncertain",
                  resolved_by: null,
                },
              ],
              cells: [],
              image_ref: null,
              confidence: 0.9,
            },
          ],
        },
      ],
    };

    expect(document.pages[0].blocks[0].words[0].alternatives).toHaveLength(2);
  });
});
