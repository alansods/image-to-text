/* Gerado por `npm run gen:types` a partir de backend/app/models. Não edite à mão. */

/**
 * Motivo de uma página ter baixa qualidade (spec image-preprocessing, D13).
 */
export type QualityIssue = "resolution" | "blur" | "contrast" | "uncertain_reading";
export type BlockType =
  "heading" | "paragraph" | "list" | "table" | "figure" | "formula" | "header" | "footer";
export type Alignment = "left" | "center" | "right" | "justify";
export type ReadingSource = "paddle" | "doctr" | "arbiter" | "similar";
export type WordStatus = "accepted" | "resolved" | "uncertain" | "edited";
export type ResolvedBy = "confidence" | "reread" | "shape" | "arbiter";

export interface Document {
  id: string;
  source_file: string;
  pages: Page[];
  counts: WordCounts;
}
export interface Page {
  index: number;
  width: number;
  height: number;
  page_size: PageSize;
  columns: number;
  image_ref: string;
  blank: boolean;
  quality_issues: QualityIssue[];
  blocks: Block[];
  counts: WordCounts;
}
/**
 * Tamanho da folha em pontos (1/72 de polegada), usado para repetir a paginação.
 */
export interface PageSize {
  w_pt: number;
  h_pt: number;
}
export interface Block {
  id: string;
  type: BlockType;
  bbox: BBox;
  order: number;
  column: number;
  align: Alignment;
  rel_size: number;
  font_pt: number | null;
  words: Word[];
  cells: Cell[];
  items: ListItem[];
  image_ref: string | null;
  confidence: number;
}
/**
 * Caixa delimitadora em pixels da imagem da página.
 */
export interface BBox {
  x: number;
  y: number;
  w: number;
  h: number;
}
export interface Word {
  id: string;
  text: string;
  bbox: BBox;
  confidence: number;
  bold: boolean;
  italic: boolean;
  alternatives: Alternative[];
  status: WordStatus;
  resolved_by: ResolvedBy | null;
}
/**
 * Uma leitura possível de uma palavra, mostrada na conferência.
 */
export interface Alternative {
  text: string;
  confidence: number;
  source: ReadingSource;
}
export interface Cell {
  row: number;
  col: number;
  row_span: number;
  col_span: number;
  bbox: BBox | null;
  words: Word[];
}
/**
 * Item de uma lista: índice da palavra onde ele começa (o marcador) e o nível de recuo.
 */
export interface ListItem {
  word_start: number;
  level: number;
}
/**
 * Quantas palavras estão em cada status (spec reading-reconciliation, contagem de dúvidas).
 */
export interface WordCounts {
  accepted: number;
  resolved: number;
  uncertain: number;
  edited: number;
}
