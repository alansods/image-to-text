"use client";

import { AlertCircle, Check, Copy, Download, FileText, Info } from "lucide-react";
import { useCallback, useState } from "react";

import { DocumentPages } from "@/components/result/DocumentPages";
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

interface Props {
  jobId: string;
  initial: Document;
  onReset: () => void;
}

const BUTTON =
  "inline-flex h-11 cursor-pointer items-center justify-center gap-2 rounded-lg border px-[18px] font-medium whitespace-nowrap disabled:opacity-60";

export function ResultView({ jobId, initial, onReset }: Props) {
  const { t } = useI18n();
  const [doc, setDoc] = useState(initial);
  const [openId, setOpenId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState<"docx" | "pdf" | null>(null);
  const [exportError, setExportError] = useState(false);

  const pending = uncertainWords(doc);
  const lowQuality = lowQualityPages(doc);
  const baseName = doc.source_file.replace(/\.[^.]+$/, "") || "documento";

  const open = useCallback((wordId: string | null) => {
    setSaveError(null);
    setOpenId(wordId);
    if (wordId) {
      requestAnimationFrame(() =>
        document
          .getElementById(`word-${wordId}`)
          ?.scrollIntoView({ block: "center", behavior: "smooth" }),
      );
    }
  }, []);

  const close = useCallback(() => {
    const current = openId;
    setOpenId(null);
    if (current) document.getElementById(`word-${current}`)?.focus();
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
    requestAnimationFrame(() => document.getElementById(`word-${word.id}`)?.focus());
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
      if (error instanceof ApiFailure || error instanceof Error) setExportError(true);
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col gap-4 px-4 pt-6 pb-24 sm:px-6 sm:pt-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground">
          <FileText className="size-4 shrink-0" aria-hidden="true" />
          <span className="truncate">{doc.source_file}</span>
        </div>
        <button
          type="button"
          onClick={onReset}
          className="inline-flex h-11 cursor-pointer items-center rounded-lg px-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground sm:h-9"
        >
          {t.another}
        </button>
      </div>

      {lowQuality.length > 0 && (
        <p className="flex items-start gap-2.5 rounded-xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {t.quality(lowQuality, doc.pages.length)}
        </p>
      )}

      <div role="status" aria-live="polite">
        {pending.length > 0 ? (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-doubt-line bg-doubt px-4 py-3.5">
            <AlertCircle className="size-[18px] shrink-0 text-doubt-foreground" aria-hidden="true" />
            <div className="min-w-60 flex-1">
              <div className="font-semibold">{t.gate(pending.length)}</div>
              <div className="text-sm text-doubt-foreground">{t.gateSub}</div>
            </div>
            <button
              type="button"
              onClick={() => open(nextUncertain(doc, openId ?? cursor)?.id ?? pending[0].id)}
              className={`${BUTTON} w-full border-transparent bg-primary text-primary-foreground sm:w-auto`}
            >
              {t.checkNext}
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-2.5">
            <p className="m-0 flex items-center gap-2 font-medium text-success">
              <Check className="size-[18px]" aria-hidden="true" />
              {t.allChecked}
            </p>
            <div className="flex flex-wrap gap-2.5">
              <button
                type="button"
                onClick={copy}
                className={`${BUTTON} flex-[1_1_200px] border-transparent bg-primary text-primary-foreground`}
              >
                {copied ? <Check className="size-[18px]" aria-hidden="true" /> : <Copy className="size-[18px]" aria-hidden="true" />}
                {copied ? t.copied : t.copy}
              </button>
              <button
                type="button"
                disabled={exporting !== null}
                onClick={() => download("docx")}
                className={`${BUTTON} flex-[1_1_160px] border-border bg-card hover:bg-muted`}
              >
                <Download className="size-[18px]" aria-hidden="true" />
                {t.downloadWord}
              </button>
              <button
                type="button"
                disabled={exporting !== null}
                onClick={() => download("pdf")}
                className={`${BUTTON} flex-[1_1_160px] border-border bg-card hover:bg-muted`}
              >
                <Download className="size-[18px]" aria-hidden="true" />
                {t.downloadPdf}
              </button>
            </div>
            {exportError && (
              <p role="alert" className="m-0 text-sm font-medium text-destructive">
                {t.exportFailed}
              </p>
            )}
          </div>
        )}
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
  );
}
