"use client";

import { Check, Copy, Download, RefreshCw, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { DocumentPages } from "@/components/result/DocumentPages";
import { Band } from "@/components/site/Band";
import { WordCheck } from "@/components/result/WordCheck";
import { ApiFailure, downloadExport, reviewWord } from "@/lib/api";
import {
  type Choice,
  applyEdit,
  documentText,
  lowQualityPages,
  nextUncertain,
  uncertainWords,
} from "@/lib/document";
import { useI18n } from "@/lib/i18n";
import type { Document, Word } from "@/lib/types/document";
import { cn } from "@/lib/utils";

interface Props {
  jobId: string;
  initial: Document;
  onReset: () => void;
}

const BUTTON =
  "inline-flex min-h-[50px] cursor-pointer items-center justify-center gap-2 rounded-full px-4 font-semibold whitespace-nowrap disabled:opacity-60";
const PRIMARY =
  "min-h-[52px] bg-primary px-6 text-base text-primary-foreground shadow-[0_8px_20px_rgba(37,99,217,.3)] hover:bg-[#1f55c4]";

export function ResultView({ jobId, initial, onReset }: Props) {
  const { t } = useI18n();
  const [doc, setDoc] = useState(initial);
  const [openId, setOpenId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState<"docx" | "pdf" | null>(null);
  const [exportError, setExportError] = useState(false);
  // Barra fixa do pé da tela: só quando o cartão de ações do topo saiu da tela.
  const topCard = useRef<HTMLDivElement>(null);
  const [topVisible, setTopVisible] = useState(true);
  useEffect(() => {
    const card = topCard.current;
    if (!card || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) =>
      setTopVisible(entry.isIntersecting),
    );
    observer.observe(card);
    return () => observer.disconnect();
  }, []);

  const pending = uncertainWords(doc);
  const lowQuality = lowQualityPages(doc);
  const baseName = doc.source_file.replace(/\.[^.]+$/, "") || "documento";

  const open = useCallback((wordId: string | null) => {
    setSaveError(null);
    setOpenId(wordId);
    if (wordId) {
      // Só rola quando a palavra está fora da tela ("Conferir próxima"); clicada, ela já está
      // visível e o quadro abre ali mesmo.
      requestAnimationFrame(() => {
        const target = document.getElementById(`word-${wordId}`);
        if (!target) return;
        const rect = target.getBoundingClientRect();
        if (rect.top < 0 || rect.bottom > window.innerHeight) {
          target.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      });
    }
  }, []);

  const close = useCallback(() => {
    const current = openId;
    setOpenId(null);
    if (current)
      document
        .getElementById(`word-${current}`)
        ?.focus({ preventScroll: true });
  }, [openId]);

  // Última palavra conferida: "Conferir próxima" segue dali, e o foco fica nela.
  const [cursor, setCursor] = useState<string | null>(null);

  const resolve = async (word: Word, choice: Choice) => {
    setSaving(true);
    setSaveError(null);
    try {
      await reviewWord(jobId, word.id, choice);
    } catch {
      setSaving(false);
      setSaveError(t.saveFailed);
      return;
    }
    setDoc(applyEdit(doc, word.id, choice));
    setSaving(false);
    setCursor(word.id);
    setOpenId(null);
    // Fica na palavra corrigida para o usuário ver como ficou (spec review-editor).
    requestAnimationFrame(() =>
      document
        .getElementById(`word-${word.id}`)
        ?.focus({ preventScroll: true }),
    );
  };

  const copy = async () => {
    await navigator.clipboard.writeText(documentText(doc));
    setCopied(true);
  };

  const download = async (fmt: "docx" | "pdf") => {
    setExporting(fmt);
    setExportError(false);
    try {
      await downloadExport(jobId, fmt, baseName);
    } catch (error) {
      if (error instanceof ApiFailure || error instanceof Error)
        setExportError(true);
    } finally {
      setExporting(null);
    }
  };

  const reset = (
    <button
      type="button"
      onClick={onReset}
      className={`${BUTTON} bg-primary-soft px-5 text-[15px] text-navy hover:bg-[#d6e3ff]`}
    >
      <RefreshCw className="size-[18px]" aria-hidden="true" />
      {t.another}
    </button>
  );

  return (
    <div className="flex flex-col">
      <Band className="pb-[84px] sm:pb-24">
        <div className="mx-auto flex max-w-[780px] flex-col gap-1.5 px-5 pt-4 sm:gap-2 sm:px-6 sm:pt-7">
          <span
            aria-live="polite"
            className={cn(
              "inline-flex items-center gap-2 text-sm font-semibold sm:text-[15px]",
              pending.length > 0
                ? "text-doubt-on-navy"
                : "text-success-on-navy",
            )}
          >
            {pending.length === 0 && (
              <Check
                className="size-[18px]"
                strokeWidth={2.6}
                aria-hidden="true"
              />
            )}
            {pending.length > 0 ? t.almostReady : t.allChecked}
          </span>
          <h1 className="text-2xl font-bold tracking-[-0.015em] [overflow-wrap:anywhere] sm:text-[30px]">
            {doc.source_file}
          </h1>
        </div>
      </Band>

      <div className="mx-auto -mt-[60px] flex w-full max-w-[780px] flex-col gap-4 px-4 pb-36 sm:-mt-[72px] sm:px-6">
        <div
          ref={topCard}
          className="flex flex-col gap-3.5 rounded-[22px] bg-card p-4 shadow-[0_20px_50px_rgba(15,35,71,.16)] sm:p-5"
        >
          {lowQuality.length > 0 && (
            <p className="flex items-start gap-2.5 rounded-[14px] bg-doubt px-3.5 py-3 text-sm leading-normal text-doubt-foreground">
              <TriangleAlert
                className="mt-px size-[18px] shrink-0"
                aria-hidden="true"
              />
              {t.quality(lowQuality, doc.pages.length)}
            </p>
          )}

          <div role="status" aria-live="polite">
            {pending.length > 0 ? (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
                <span
                  aria-hidden="true"
                  className="flex size-11 shrink-0 items-center justify-center rounded-full bg-doubt text-[17px] font-bold text-doubt-foreground"
                >
                  {pending.length}
                </span>
                <div className="min-w-56 flex-1">
                  <div className="text-[17px] font-semibold">
                    {t.gate(pending.length)}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {t.gateSub}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    open(
                      nextUncertain(doc, openId ?? cursor)?.id ?? pending[0].id,
                    )
                  }
                  className={`${BUTTON} ${PRIMARY} w-full sm:w-auto`}
                >
                  {t.checkNext}
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-2.5">
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    disabled={exporting !== null}
                    onClick={() => download("pdf")}
                    className={`${BUTTON} ${PRIMARY}`}
                  >
                    <Download className="size-[18px]" aria-hidden="true" />
                    {t.downloadPdf}
                  </button>
                  <button
                    type="button"
                    disabled={exporting !== null}
                    onClick={() => download("docx")}
                    className={`${BUTTON} ${PRIMARY}`}
                  >
                    <Download className="size-[18px]" aria-hidden="true" />
                    {t.downloadWord}
                  </button>
                  <button
                    type="button"
                    onClick={copy}
                    className={`${BUTTON} bg-primary-soft text-[15px] text-navy hover:bg-[#d6e3ff]`}
                  >
                    {copied ? (
                      <Check className="size-[18px]" aria-hidden="true" />
                    ) : (
                      <Copy className="size-[18px]" aria-hidden="true" />
                    )}
                    {copied ? t.copied : t.copy}
                  </button>
                  {reset}
                </div>
                {exportError && (
                  <p
                    role="alert"
                    className="m-0 text-sm font-medium text-destructive"
                  >
                    {t.exportFailed}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        <DocumentPages
          doc={doc}
          jobId={jobId}
          openId={openId}
          onOpen={(id) => open(openId === id ? null : id)}
          renderCheck={(word) => (
            <WordCheck
              key={word.id}
              jobId={jobId}
              word={word}
              saving={saving}
              error={saveError}
              onResolve={(choice) => resolve(word, choice)}
              onClose={close}
            />
          )}
        />
      </div>

      {!topVisible && openId === null && (
        <ProgressBar
          left={pending.length}
          busy={exporting !== null}
          onNext={() => open(nextUncertain(doc, cursor)?.id ?? pending[0].id)}
          onDownload={download}
        />
      )}
    </div>
  );
}

/** Barra presa ao pé da tela (spec "Barra fixa de andamento"): quantas faltam e "Conferir
 * próxima"; sem dúvidas, "Tudo conferido" com os downloads. Não rouba o foco nem rola. */
function ProgressBar({
  left,
  busy,
  onNext,
  onDownload,
}: {
  left: number;
  busy: boolean;
  onNext: () => void;
  onDownload: (fmt: "docx" | "pdf") => void;
}) {
  const { t } = useI18n();
  const done = left === 0;
  return (
    <section
      aria-label={t.barLabel}
      className="fixed inset-x-0 bottom-0 z-30 sm:bottom-6 sm:px-6"
    >
      <div
        key={done ? "done" : "left"}
        className={cn(
          "bar-rise mx-auto flex max-w-[732px] flex-wrap items-center gap-3 rounded-t-[22px] px-4 pt-3 pb-[calc(1.25rem+env(safe-area-inset-bottom,0px))] shadow-[0_-10px_34px_rgba(15,35,71,.18)] sm:flex-nowrap sm:gap-3.5 sm:rounded-[20px] sm:py-3 sm:pr-3 sm:pl-4 sm:shadow-[0_16px_44px_rgba(15,35,71,.22)]",
          done ? "bg-navy text-on-navy" : "border border-border bg-card",
        )}
      >
        {done ? (
          <>
            <span
              aria-hidden="true"
              className="flex size-10 shrink-0 items-center justify-center rounded-full bg-success-on-navy text-navy"
            >
              <Check className="size-5" strokeWidth={2.8} />
            </span>
            <span className="flex min-w-0 flex-1 flex-col leading-tight">
              <span className="font-bold">{t.allChecked}</span>
              <span className="text-[13px] text-on-navy-soft">{t.barDone}</span>
            </span>
            <div className="grid w-full grid-cols-2 gap-2.5 sm:flex sm:w-auto">
              {(["pdf", "docx"] as const).map((fmt) => (
                <button
                  key={fmt}
                  type="button"
                  disabled={busy}
                  onClick={() => onDownload(fmt)}
                  className={`${BUTTON} ${PRIMARY} min-h-12 px-5 text-[15px]`}
                >
                  <Download className="size-[17px]" aria-hidden="true" />
                  {fmt === "pdf" ? t.downloadPdf : t.downloadWord}
                </button>
              ))}
            </div>
          </>
        ) : (
          <>
            <span
              aria-hidden="true"
              className="flex size-10 shrink-0 items-center justify-center rounded-full bg-doubt font-bold text-doubt-foreground"
            >
              {left}
            </span>
            <span className="min-w-0 flex-1 font-semibold">
              {t.barLeft(left)}
            </span>
            <button
              type="button"
              onClick={onNext}
              className={`${BUTTON} ${PRIMARY} min-h-12 px-5 text-[15px]`}
            >
              {t.checkNext}
            </button>
          </>
        )}
      </div>
    </section>
  );
}
