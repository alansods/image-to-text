// Geometria da folha na tela: as mesmas regras do Word (backend app/export/docx_export.py).
import type { Block, Document, Page } from "@/lib/types/document";

const DEFAULT_PT = 11;
// Bloco com ao menos isto da largura do conteúdo atravessa as colunas.
const FULL_WIDTH = 0.6;

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

/** Corpo do texto em pontos: altura das palavras dos parágrafos (≈ corpo da fonte, D16). */
export function bodyFontPt(doc: Document): number {
  const measured = doc.pages.flatMap((page) =>
    page.blocks.filter((b) => b.type === "paragraph" && b.font_pt).map((b) => b.font_pt as number),
  );
  if (measured.length > 0) return median(measured);
  const heights = doc.pages.flatMap((page) =>
    page.blocks
      .filter((b) => b.type === "paragraph")
      .flatMap((b) =>
        b.words
          .filter((w) => w.text && w.text !== "[ilegível]")
          .map((w) => (w.bbox.h * page.page_size.w_pt) / page.width / b.rel_size),
      ),
  );
  if (heights.length === 0) return DEFAULT_PT;
  return Math.min(Math.max(median(heights), 6), 40);
}

export interface BodyGroup {
  columns: number;
  /** Uma lista de blocos por coluna (1 quando o grupo atravessa a página). */
  lanes: Block[][];
}

/** Separa cabeçalho, rodapé e corpo; o corpo vira grupos de largura total ou em colunas. */
export function pageLayout(page: Page): { header: Block[]; footer: Block[]; body: BodyGroup[] } {
  const ordered = [...page.blocks].sort((a, b) => a.order - b.order);
  const header = ordered.filter((b) => b.type === "header");
  const footer = ordered.filter((b) => b.type === "footer");
  const body = ordered.filter((b) => b.type !== "header" && b.type !== "footer");
  if (body.length === 0) return { header, footer, body: [] };
  const left = Math.min(...body.map((b) => b.bbox.x));
  const width = Math.max(...body.map((b) => b.bbox.x + b.bbox.w)) - left;
  const groups: BodyGroup[] = [];
  for (const block of body) {
    const spans = page.columns === 1 || block.bbox.w >= FULL_WIDTH * width;
    const columns = spans ? 1 : page.columns;
    let group = groups[groups.length - 1];
    if (!group || group.columns !== columns) {
      group = { columns, lanes: Array.from({ length: columns }, () => []) };
      groups.push(group);
    }
    group.lanes[spans ? 0 : Math.min(block.column, columns - 1)].push(block);
  }
  return { header, footer, body: groups };
}

/** Margens da folha (% da largura) pela posição do conteúdo no original, como no Word. */
export function pageMargins(page: Page): { x: number; top: number; bottom: number } {
  const body = page.blocks.filter((b) => b.type !== "header" && b.type !== "footer");
  if (body.length === 0) return { x: 12, top: 12, bottom: 12 };
  const k = 100 / page.width;
  const clamp = (v: number) => Math.min(Math.max(v, 4), 15);
  return {
    x: clamp(Math.min(...body.map((b) => b.bbox.x)) * k),
    top: clamp(Math.min(...body.map((b) => b.bbox.y)) * k),
    bottom: clamp((page.height - Math.max(...body.map((b) => b.bbox.y + b.bbox.h))) * k),
  };
}

/** Vão vertical do original entre dois blocos, menos a folga que a linha já ocupa (como no
 * Word: backend app/export/docx_export.py). */
export function gapCqw(previous: Block, block: Block, page: Page, base: number): string {
  const gapPt = ((block.bbox.y - (previous.bbox.y + previous.bbox.h)) * page.page_size.w_pt) / page.width;
  const pt = Math.min(Math.max(gapPt - 0.3 * base, 0), 0.6 * page.page_size.h_pt);
  return `${((pt / page.page_size.w_pt) * 100).toFixed(3)}cqw`;
}

/** Cabeçalho/rodapé curto (número da página) alinha pela posição na página. */
export function edgeAlign(page: Page, block: Block): Block["align"] {
  if (block.bbox.w >= 0.3 * page.width) return block.align;
  const center = (block.bbox.x + block.bbox.w / 2) / page.width;
  return center > 0.6 ? "right" : center < 0.4 ? "left" : "center";
}

