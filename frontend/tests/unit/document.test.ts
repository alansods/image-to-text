import { describe, expect, it } from "vitest";

import {
  applyEdit,
  charDiff,
  documentText,
  lowQualityPages,
  nextUncertain,
  uncertainWords,
} from "@/lib/document";
import type { Block, Document, Page, Word } from "@/lib/types/document";

function word(id: string, text: string, status: Word["status"] = "accepted", alts: string[] = []): Word {
  return {
    id,
    text,
    bbox: { x: 0, y: 0, w: 10, h: 10 },
    confidence: 0.9,
    bold: false,
    italic: false,
    alternatives: alts.map((t, i) => ({ text: t, confidence: 0.9 - i * 0.1, source: "paddle" })),
    status,
    resolved_by: null,
  };
}

function block(id: string, order: number, words: Word[], extra: Partial<Block> = {}): Block {
  return {
    id,
    type: "paragraph",
    bbox: { x: 0, y: 0, w: 100, h: 10 },
    order,
    column: 0,
    align: "left",
    rel_size: 1,
    words,
    cells: [],
    items: [],
    image_ref: null,
    confidence: 0.9,
    ...extra,
  };
}

function page(index: number, blocks: Block[], quality: Page["quality_issues"] = []): Page {
  return {
    index,
    width: 2480,
    height: 3508,
    page_size: { w_pt: 595, h_pt: 842 },
    columns: 1,
    image_ref: `pages/${index}.png`,
    blank: false,
    quality_issues: quality,
    blocks,
    counts: { accepted: 0, resolved: 0, uncertain: 0, edited: 0 },
  };
}

function doc(pages: Page[]): Document {
  return {
    id: "d",
    source_file: "contrato.pdf",
    pages,
    counts: { accepted: 0, resolved: 0, uncertain: 0, edited: 0 },
  };
}

const sample = doc([
  page(0, [
    block("b1", 1, [word("w3", "segundo"), word("w4", "SlLVA", "uncertain", ["SILVA", "SlLVA"])]),
    block("b0", 0, [word("w1", "Primeiro", "uncertain", ["Primeiro", "Prirneiro"]), word("w2", "bloco")]),
  ]),
  page(1, [
    block("t", 0, [], {
      type: "table",
      cells: [
        { row: 0, col: 0, row_span: 1, col_span: 1, bbox: null, words: [word("c1", "Item")] },
        { row: 0, col: 1, row_span: 1, col_span: 1, bbox: null, words: [word("c2", "1.234,56", "uncertain", ["1.234,56", "1.234.56"])] },
        { row: 1, col: 0, row_span: 1, col_span: 2, bbox: null, words: [word("c3", "Total")] },
      ],
    }),
  ]),
]);

describe("palavras em dúvida", () => {
  it("vêm na ordem de leitura, atravessando páginas e células", () => {
    expect(uncertainWords(sample).map((w) => w.id)).toEqual(["w1", "w4", "c2"]);
  });

  it("a próxima depois da atual segue a ordem e volta ao começo", () => {
    expect(nextUncertain(sample, "w1")?.id).toBe("w4");
    expect(nextUncertain(sample, "c2")?.id).toBe("w1");
    expect(nextUncertain(sample, null)?.id).toBe("w1");
  });

  it("conferir uma palavra a torna editada com o novo texto", () => {
    const edited = applyEdit(sample, "w4", "SILVA");
    const found = edited.pages[0].blocks[0].words[1];

    expect([found.text, found.status]).toEqual(["SILVA", "edited"]);
    expect(uncertainWords(edited).map((w) => w.id)).toEqual(["w1", "c2"]);
    expect(sample.pages[0].blocks[0].words[1].text).toBe("SlLVA"); // imutável
  });
});

describe("texto para copiar", () => {
  it("segue a ordem de leitura, com linha em branco entre blocos e tabulação entre células", () => {
    expect(documentText(sample)).toBe(
      "Primeiro bloco\n\nsegundo SlLVA\n\nItem\t1.234,56\nTotal",
    );
  });

  it("palavra removida na conferência não deixa espaço duplo", () => {
    const removed = applyEdit(sample, "w2", "");
    expect(documentText(removed).split("\n\n")[0]).toBe("Primeiro");
  });
});

describe("diferença entre alternativas", () => {
  it("destaca só o caractere que muda", () => {
    expect(charDiff(["SILVA", "SlLVA"])).toEqual([
      [
        { c: "S", diff: false },
        { c: "I", diff: true },
        { c: "L", diff: false },
        { c: "V", diff: false },
        { c: "A", diff: false },
      ],
      [
        { c: "S", diff: false },
        { c: "l", diff: true },
        { c: "L", diff: false },
        { c: "V", diff: false },
        { c: "A", diff: false },
      ],
    ]);
  });

  it("caractere a mais também aparece destacado", () => {
    const [shorter, longer] = charDiff(["R$17", "R$ 17"]);
    expect(shorter.every((c) => !c.diff)).toBe(true);
    expect(longer.filter((c) => c.diff).map((c) => c.c)).toEqual([" "]);
  });
});

describe("qualidade", () => {
  it("lista as páginas (a partir de 1) com baixa qualidade", () => {
    const pages = doc([page(0, []), page(1, [], ["blur"]), page(2, [], ["resolution", "contrast"])]);
    expect(lowQualityPages(pages)).toEqual([2, 3]);
  });
});
