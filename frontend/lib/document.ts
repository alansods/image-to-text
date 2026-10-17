// Funções puras sobre o Document (formato interno gerado do backend).
import type { Block, Document, Word } from "@/lib/types/document";

/** Palavras de um bloco: texto corrido ou células da tabela, linha a linha. */
export function blockWords(block: Block): Word[] {
  if (block.cells.length === 0) return block.words;
  const cells = [...block.cells].sort((a, b) => a.row - b.row || a.col - b.col);
  return [...block.words, ...cells.flatMap((c) => c.words)];
}

function blocksInOrder(doc: Document): Block[] {
  return doc.pages.flatMap((p) => [...p.blocks].sort((a, b) => a.order - b.order));
}

export function wordsInReadingOrder(doc: Document): Word[] {
  return blocksInOrder(doc).flatMap(blockWords);
}

export function uncertainWords(doc: Document): Word[] {
  return wordsInReadingOrder(doc).filter((w) => w.status === "uncertain");
}

/** Próxima dúvida depois de `currentId` na ordem de leitura; volta ao começo se preciso. */
export function nextUncertain(doc: Document, currentId: string | null): Word | null {
  const all = wordsInReadingOrder(doc);
  const start = currentId ? all.findIndex((w) => w.id === currentId) + 1 : 0;
  const ordered = [...all.slice(start), ...all.slice(0, start)];
  return ordered.find((w) => w.status === "uncertain" && w.id !== currentId) ?? null;
}

/** Escolha feita na conferência: sempre um texto (vazio = "não há palavra aqui"). */
export type Choice = { text: string };

/** Documento com a palavra conferida (status "editada"). */
export function applyEdit(doc: Document, wordId: string, choice: Choice): Document {
  const edit = (w: Word): Word =>
    w.id === wordId ? { ...w, text: choice.text, status: "edited", resolved_by: null } : w;
  return {
    ...doc,
    pages: doc.pages.map((p) => ({
      ...p,
      blocks: p.blocks.map((b) => ({
        ...b,
        words: b.words.map(edit),
        cells: b.cells.map((c) => ({ ...c, words: c.words.map(edit) })),
      })),
    })),
  };
}

function joinWords(words: Word[]): string {
  return words
    .map((w) => w.text)
    .filter(Boolean)
    .join(" ");
}

/** Texto para "Copiar texto": linha em branco entre blocos, tabulação entre células. */
export function documentText(doc: Document): string {
  const parts: string[] = [];
  for (const block of blocksInOrder(doc)) {
    if (block.cells.length > 0) {
      const rows = new Map<number, string[]>();
      for (const cell of [...block.cells].sort((a, b) => a.row - b.row || a.col - b.col)) {
        rows.set(cell.row, [...(rows.get(cell.row) ?? []), joinWords(cell.words)]);
      }
      parts.push([...rows.values()].map((cells) => cells.join("\t")).join("\n"));
    } else if (block.items.length > 0) {
      const starts = [...block.items.map((i) => i.word_start), block.words.length];
      parts.push(
        block.items
          .map((_, i) => joinWords(block.words.slice(starts[i], starts[i + 1])))
          .join("\n"),
      );
    } else if (block.words.length > 0) {
      parts.push(joinWords(block.words));
    }
  }
  return parts.filter(Boolean).join("\n\n");
}

export interface DiffChar {
  c: string;
  diff: boolean;
}

/** Marca em cada alternativa os caracteres que não fazem parte do que ela tem em comum com as
 * outras (maior subsequência comum), para destacar a diferença ("SILVA" × "SlLVA"). */
export function charDiff(alternatives: string[]): DiffChar[][] {
  const common = (a: string, b: string): boolean[] => {
    const n = a.length;
    const m = b.length;
    const table = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        table[i][j] =
          a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
      }
    }
    const kept = new Array<boolean>(n).fill(false);
    let i = 0;
    let j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) {
        kept[i] = true;
        i++;
        j++;
      } else if (table[i + 1][j] >= table[i][j + 1]) i++;
      else j++;
    }
    return kept;
  };
  return alternatives.map((alt, index) => {
    const others = alternatives.filter((_, k) => k !== index);
    const masks = others.map((other) => common(alt, other));
    return [...alt].map((c, i) => ({ c, diff: masks.some((mask) => !mask[i]) }));
  });
}

/** Números (a partir de 1) das páginas com baixa qualidade. */
export function lowQualityPages(doc: Document): number[] {
  return doc.pages.filter((p) => p.quality_issues.length > 0).map((p) => p.index + 1);
}
