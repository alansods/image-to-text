"use client";

import type React from "react";
import { Check, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { cropUrl } from "@/lib/api";
import { charDiff, type Choice } from "@/lib/document";
import { useI18n } from "@/lib/i18n";
import type { Word } from "@/lib/types/document";
import { cn } from "@/lib/utils";

interface Props {
  jobId: string;
  word: Word;
  saving: boolean;
  error: string | null;
  onResolve: (choice: Choice) => void;
  onClose: () => void;
}

/** Quadro de conferência (spec review-editor): popover junto da palavra; no celular, painel
 * na parte de baixo da tela. Esc, "Fechar" ou clique fora fecham sem resolver. */
export function WordCheck({ jobId, word, saving, error, onResolve, onClose }: Props) {
  const { t } = useI18n();
  const box = useRef<HTMLDivElement>(null);
  const options = word.alternatives.length
    ? word.alternatives.map((a) => a.text)
    : [word.text];
  // Palavra já conferida: a escolha atual aparece marcada (ou digitada) para poder ser trocada.
  const edited = word.status === "edited";
  const chosen = !edited ? null : word.keep_original ? "keep" : options.indexOf(word.text);
  const [typed, setTyped] = useState(edited && chosen === -1 ? word.text : "");
  const diffs = charDiff(options);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  // Fica fora do parágrafo (HTML não aceita formulário dentro de <p>), posicionado logo
  // abaixo da palavra; no celular, o CSS transforma em painel inferior.
  useLayoutEffect(() => {
    const place = () => {
      const anchor = document.getElementById(`word-${word.id}`);
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      const width = 300;
      const left = Math.min(Math.max(rect.left - 60, 8), window.innerWidth - width - 8);
      setPosition({ top: rect.bottom + window.scrollY + 8, left: left + window.scrollX });
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [word.id]);

  useEffect(() => {
    const current = box.current?.querySelector<HTMLButtonElement>("button[aria-pressed='true']");
    // Sem rolar: o quadro já está junto da palavra (ou no painel inferior, no celular).
    (current ?? box.current?.querySelector<HTMLButtonElement>("button[data-option]"))?.focus({
      preventScroll: true,
    });
  }, [word.id]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Element | null;
      if (box.current && target && !box.current.contains(target) && !target.closest("[data-word]")) {
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [onClose]);

  const submitTyped = () => {
    const value = typed.trim();
    if (value) onResolve({ text: value });
  };

  if (typeof document === "undefined") return null;
  return createPortal(
    <>
      <span aria-hidden="true" className="fixed inset-0 z-40 bg-foreground/35 sm:hidden" />
      <div
        ref={box}
        role="dialog"
        aria-modal="true"
        aria-label={t.whichRight}
        className={cn(
          "z-50 flex flex-col gap-2.5 border border-border bg-popover p-4 font-sans text-sm leading-snug text-popover-foreground shadow-[0_12px_36px_rgba(20,18,14,.2)]",
          // celular: painel inferior
          "fixed inset-x-0 bottom-0 rounded-t-2xl pb-6",
          // telas maiores: popover abaixo da palavra
          "sm:absolute sm:inset-x-auto sm:top-(--pop-top) sm:bottom-auto sm:left-(--pop-left) sm:w-[300px] sm:rounded-[10px] sm:pb-4",
          // até saber onde fica a palavra, não aparece no topo da página
          !position && "sm:invisible",
        )}
        style={
          {
            "--pop-top": `${position?.top ?? 0}px`,
            "--pop-left": `${position?.left ?? 0}px`,
          } as React.CSSProperties
        }
      >
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-muted-foreground">{t.inImage}</span>
          <button
            type="button"
            onClick={onClose}
            aria-label={t.close}
            className="-mr-2 inline-flex size-11 cursor-pointer items-center justify-center rounded-lg text-muted-foreground hover:bg-muted sm:size-8"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        {/* eslint-disable-next-line @next/next/no-img-element -- imagem da API, sem otimização */}
        <img
          src={cropUrl(jobId, word.id)}
          alt={t.cropAlt}
          className="max-h-28 w-full rounded-md border border-border bg-paper object-contain p-2"
        />
        <span className="font-semibold">{t.whichRight}</span>
        {options.map((option, index) => (
          <button
            key={`${option}-${index}`}
            type="button"
            data-option
            disabled={saving}
            onClick={() => onResolve({ text: option })}
            aria-label={option || t.noWord}
            aria-pressed={edited ? chosen === index : undefined}
            className="flex h-12 w-full cursor-pointer items-center rounded-lg border border-border bg-card px-3.5 font-mono text-xl font-medium tracking-[0.06em] hover:border-primary hover:bg-primary-soft disabled:opacity-60 aria-pressed:border-success aria-pressed:bg-success/10"
          >
            {option === "" ? (
              <span className="text-base tracking-normal text-muted-foreground">{t.noWord}</span>
            ) : (
              diffs[index].map((ch, i) => (
                <span
                  key={i}
                  className={cn(
                    "inline-block whitespace-pre",
                    ch.diff &&
                      "rounded-[2px] border-b-2 border-doubt-line bg-doubt px-0.5 font-semibold text-doubt-foreground",
                  )}
                >
                  {ch.c}
                </span>
              ))
            )}
            {chosen === index && <Check className="ml-auto size-4 shrink-0 text-success" aria-hidden="true" />}
          </button>
        ))}
        <button
          type="button"
          disabled={saving}
          onClick={() => onResolve({ keep_original: true })}
          aria-pressed={edited ? chosen === "keep" : undefined}
          className="flex h-11 w-full cursor-pointer items-center rounded-lg border border-dashed border-border-strong bg-card px-3.5 text-left text-[15px] font-medium hover:border-primary hover:bg-primary-soft disabled:opacity-60 aria-pressed:border-success aria-pressed:bg-success/10"
        >
          {t.keepOriginal}
          {chosen === "keep" && <Check className="ml-auto size-4 shrink-0 text-success" aria-hidden="true" />}
        </button>
        <form
          className="flex gap-1.5"
          onSubmit={(event) => {
            event.preventDefault();
            submitTyped();
          }}
        >
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            aria-label={t.typeIt}
            placeholder={t.typeIt}
            className="h-12 min-w-0 flex-1 rounded-lg border border-border bg-card px-3 font-mono text-base sm:h-11"
          />
          <button
            type="submit"
            aria-label={t.useTyped}
            disabled={saving || !typed.trim()}
            className="inline-flex size-12 cursor-pointer items-center justify-center rounded-lg border border-border bg-card hover:bg-muted disabled:opacity-50 sm:size-11"
          >
            <Check className="size-4" aria-hidden="true" />
          </button>
        </form>
        {error && (
          <p role="alert" className="text-[13px] font-medium text-destructive">
            {error}
          </p>
        )}
      </div>
    </>,
    document.body,
  );
}
