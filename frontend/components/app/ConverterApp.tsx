"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ConvertingProgress, type Step } from "@/components/progress/ConvertingProgress";
import { ResultView } from "@/components/result/ResultView";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { UploadDropzone } from "@/components/upload/UploadDropzone";
import {
  ApiFailure,
  cancelOnLeave,
  createJob,
  deleteJob,
  getJob,
  getResult,
  uploadErrorFor,
} from "@/lib/api";
import { MAX_BYTES, prepareFile } from "@/lib/files";
import type { UploadError } from "@/lib/i18n";
import type { Document } from "@/lib/types/document";

const POLL_MS = 1500;
const QUEUED: Step = { stage: "queued", page: 0, pages: 0 };

type Screen =
  | { kind: "upload"; error: UploadError | null }
  | { kind: "converting"; jobId: string; fileName: string; progress: number; step: Step }
  | { kind: "result"; jobId: string; doc: Document };

/** Um endereço, três telas: envio → convertendo → resultado (spec site-interface).
 * Nada é guardado no navegador: recarregar volta ao envio vazio. */
export function ConverterApp() {
  const [screen, setScreen] = useState<Screen>({ kind: "upload", error: null });
  const active = useRef<string | null>(null);

  const reset = useCallback((error: UploadError | null = null) => {
    if (active.current) void deleteJob(active.current);
    active.current = null;
    setScreen({ kind: "upload", error });
  }, []);

  const start = useCallback(
    async (files: File[]) => {
      if (files.length !== 1) return setScreen({ kind: "upload", error: "multiple_files" });
      const [file] = files;
      if (file.size > MAX_BYTES) return setScreen({ kind: "upload", error: "file_too_large" });
      try {
        const prepared = await prepareFile(file);
        const job = await createJob(prepared.blob, prepared.name);
        active.current = job.id;
        setScreen({
          kind: "converting",
          jobId: job.id,
          fileName: job.source_file,
          progress: 0,
          step: QUEUED,
        });
      } catch (error) {
        const code = error instanceof ApiFailure ? error.code : "unreadable";
        setScreen({ kind: "upload", error: code === "unreadable" ? "unreadable" : uploadErrorFor(code) });
      }
    },
    [],
  );

  const jobId = screen.kind === "converting" ? screen.jobId : null;
  // Recarregar ou fechar a aba durante a conversão a cancela (spec job-processing): a próxima
  // não fica na fila atrás de uma que ninguém vai ver.
  useEffect(() => {
    if (!jobId) return;
    const leave = () => cancelOnLeave(jobId);
    window.addEventListener("pagehide", leave);
    return () => window.removeEventListener("pagehide", leave);
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    const tick = async () => {
      try {
        const job = await getJob(jobId);
        if (stopped) return;
        if (job.state === "done") {
          const doc = await getResult(jobId);
          if (!stopped) setScreen({ kind: "result", jobId, doc });
          return;
        }
        if (job.state === "failed") {
          active.current = null;
          return setScreen({ kind: "upload", error: "unreadable" });
        }
        if (job.state === "cancelled" || job.state === "expired") {
          active.current = null;
          return setScreen({ kind: "upload", error: null });
        }
        setScreen((s) =>
          s.kind === "converting" && s.jobId === jobId
            ? {
                ...s,
                progress: Math.max(s.progress, job.progress),
                step: { stage: job.stage, page: job.page, pages: job.pages },
              }
            : s,
        );
      } catch (error) {
        if (error instanceof ApiFailure && error.status === 404) {
          active.current = null;
          return setScreen({ kind: "upload", error: null });
        }
      }
      if (!stopped) timer = setTimeout(tick, POLL_MS);
    };
    let timer = setTimeout(tick, POLL_MS);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [jobId]);

  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader onHome={() => reset()} />
      <main className="flex w-full flex-1 flex-col">
        {screen.kind === "upload" && <UploadDropzone onFiles={start} error={screen.error} />}
        {screen.kind === "converting" && (
          <ConvertingProgress
            fileName={screen.fileName}
            progress={screen.progress}
            step={screen.step}
            onCancel={() => reset()}
          />
        )}
        {screen.kind === "result" && (
          <ResultView jobId={screen.jobId} initial={screen.doc} onReset={() => reset()} />
        )}
      </main>
      <SiteFooter />
    </div>
  );
}
