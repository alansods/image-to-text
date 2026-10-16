"use client";

import type { CSSProperties, ReactNode } from "react";

import { imageUrl, wordImageUrl } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { bodyFontPt, pageLayout, pageMargins } from "@/lib/sheet";
import type { Block, Document, Page, Word } from "@/lib/types/document";
import { cn } from "@/lib/utils";

interface WordProps {
  jobId: string;
  openId: string | null;
  onOpen: (wordId: string) => void;
  renderCheck: (word: Word) => ReactNode;
}

const ALIGN: Record<Block["align"], CSSProperties["textAlign"]> = {
  left: "left",
  center: "center",
  right: "right",
  justify: "justify",
};

/** Tamanhos em unidades da largura da folha (cqw): a folha na tela segue as proporções do
 * papel. No celular a folha é estreita; o texto não fica menor que ~1,15 px por ponto
 * (11 pt → 12,6 px) e a folha cresce na altura quando precisa. */
function sizeCqw(pt: number, page: Page): string {
  return `max(${((pt / page.page_size.w_pt) * 100).toFixed(3)}cqw, ${(pt * 1.15).toFixed(1)}px)`;
}

function Words({ words, ctx }: { words: Word[]; ctx: WordProps }) {
  const { t } = useI18n();
  const visible = words.filter((w) => w.text !== "" || w.keep_original);
  return (
    <>
      {visible.map((word, index) => {
        const space = index < visible.length - 1 ? " " : "";
        const style = cn(word.bold && "font-semibold", word.italic && "italic");
        if (word.status !== "uncertain") {
          const edited = word.status === "edited";
          // Corrigida: verde e sublinhado contínuo, só na tela (nunca no Word/PDF).
          const mark = edited && "rounded-[3px] bg-success/15 px-0.5 underline decoration-success decoration-[1.5px] underline-offset-4";
          const content = word.keep_original ? (
            // eslint-disable-next-line @next/next/no-img-element -- recorte do original servido pela API
            <img
              src={wordImageUrl(ctx.jobId, word.id)}
              alt={word.text}
              className="inline-block h-[1.15em] w-auto align-[-0.2em]"
            />
          ) : (
            word.text
          );
          return (
            <span key={word.id}>
              <span
                id={`word-${word.id}`}
                tabIndex={edited ? -1 : undefined}
                aria-label={edited ? t.corrected(word.text) : undefined}
                className={cn(style, mark)}
              >
                {content}
              </span>
              {space}
            </span>
          );
        }
        const open = ctx.openId === word.id;
        return (
          <span key={word.id}>
            <span className="relative inline-block">
              <button
                type="button"
                id={`word-${word.id}`}
                data-word
                aria-label={t.doubtLabel(word.text)}
                aria-expanded={open}
                onClick={() => ctx.onOpen(word.id)}
                className={cn(
                  style,
                  "cursor-pointer rounded-[3px] border-0 bg-doubt px-0.5 text-inherit underline decoration-doubt-line decoration-wavy decoration-[1.5px] underline-offset-4",
                  open && "shadow-[0_0_0_2px_var(--doubt-line)]",
                )}
              >
                {word.text}
              </button>
              {open && ctx.renderCheck(word)}
            </span>
            {space}
          </span>
        );
      })}
    </>
  );
}

function BlockView({ block, page, base, ctx }: { block: Block; page: Page; base: number; ctx: WordProps }) {
  const { t } = useI18n();
  const fontSize = sizeCqw(block.font_pt ?? base * block.rel_size, page);
  if (block.image_ref) {
    return (
      <div style={{ textAlign: ALIGN[block.align] }}>
        {/* eslint-disable-next-line @next/next/no-img-element -- recorte servido pela API */}
        <img
          src={imageUrl(ctx.jobId, block.id)}
          alt={t.figureAlt}
          className="inline-block max-w-full"
          style={{ width: `${(block.bbox.w / page.width) * 100}cqw` }}
        />
      </div>
    );
  }
  if (block.cells.length > 0) {
    const rows = Math.max(...block.cells.map((c) => c.row + c.row_span));
    return (
      <table className="w-full border-collapse" style={{ fontSize }}>
        <tbody>
          {Array.from({ length: rows }, (_, row) => (
            <tr key={row}>
              {block.cells
                .filter((c) => c.row === row)
                .sort((a, b) => a.col - b.col)
                .map((cell) => (
                  <td
                    key={`${cell.row}-${cell.col}`}
                    rowSpan={cell.row_span}
                    colSpan={cell.col_span}
                    className="border border-muted-foreground px-[0.5em] py-[0.25em] align-top"
                    style={cell.bbox ? { width: `${(cell.bbox.w / page.width) * 100}cqw` } : undefined}
                  >
                    <Words words={cell.words} ctx={ctx} />
                  </td>
                ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  if (block.items.length > 0) {
    const starts = [...block.items.map((i) => i.word_start), block.words.length];
    return (
      <div style={{ fontSize }}>
        {block.items.map((item, i) => (
          <p
            key={i}
            className="m-0"
            style={{ paddingLeft: `${1.5 * (item.level + 1)}em`, textIndent: "-1.5em" }}
          >
            <Words words={block.words.slice(starts[i], starts[i + 1])} ctx={ctx} />
          </p>
        ))}
      </div>
    );
  }
  const Tag = block.type === "heading" ? "h2" : "p";
  return (
    <Tag
      className={cn("m-0 leading-[1.4]", block.type === "heading" && "font-normal")}
      style={{ fontSize, textAlign: ALIGN[block.align] }}
    >
      <Words words={block.words} ctx={ctx} />
    </Tag>
  );
}

function PageSheet({ page, total, base, ctx }: { page: Page; total: number; base: number; ctx: WordProps }) {
  const { t } = useI18n();
  const layout = pageLayout(page);
  const margins = pageMargins(page);
  const small = sizeCqw(base * 0.8, page);
  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs font-semibold tracking-[0.06em] text-muted-foreground uppercase">
        {t.pageLabel(page.index + 1, total)}
      </div>
      <article
        aria-label={t.pageAria(page.index + 1)}
        className="@container flex flex-col rounded-[4px] border border-border bg-card font-serif text-foreground shadow-[0_2px_10px_rgba(20,18,14,.08)]"
        style={{ aspectRatio: `${page.page_size.w_pt} / ${page.page_size.h_pt}` }}
      >
        <div
          className="flex flex-1 flex-col"
          style={{
            padding: `${margins.top / 2}cqw ${margins.x}cqw ${margins.bottom / 2}cqw`,
            gap: sizeCqw(base * 0.6, page),
          }}
        >
          {layout.header.map((block) => (
            <div key={block.id} style={{ fontSize: small }}>
              <BlockView block={block} page={page} base={base * 0.8} ctx={ctx} />
            </div>
          ))}
          {layout.body.map((group, index) => (
            <div
              key={index}
              className="grid"
              style={{
                gridTemplateColumns: `repeat(${group.columns}, minmax(0, 1fr))`,
                columnGap: "5cqw",
              }}
            >
              {group.lanes.map((lane, laneIndex) => (
                <div key={laneIndex} className="flex flex-col" style={{ gap: sizeCqw(base * 0.6, page) }}>
                  {lane.map((block) => (
                    <BlockView key={block.id} block={block} page={page} base={base} ctx={ctx} />
                  ))}
                </div>
              ))}
            </div>
          ))}
          <div className="mt-auto flex flex-col gap-1 pt-4">
            {layout.footer.map((block) => (
              <BlockView key={block.id} block={block} page={page} base={base * 0.8} ctx={ctx} />
            ))}
            <span className="text-center font-sans text-[13px] text-muted-foreground">
              {page.index + 1}
            </span>
          </div>
        </div>
      </article>
    </div>
  );
}

/** O documento como será baixado: uma folha por página, na proporção do papel original. */
export function DocumentPages({ doc, ...ctx }: { doc: Document } & WordProps) {
  const base = bodyFontPt(doc);
  return (
    <div className="flex flex-col gap-6">
      {doc.pages.map((page) => (
        <PageSheet key={page.index} page={page} total={doc.pages.length} base={base} ctx={ctx} />
      ))}
    </div>
  );
}
