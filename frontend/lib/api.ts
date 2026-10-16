// Cliente da API do backend (docs/layout/rotas-e-paginas.md, seção 7).
import type { UploadError } from "@/lib/i18n";
import type { Document } from "@/lib/types/document";
import type { Job } from "@/lib/types/job";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

/** Falha com o código de erro da API (`{"error": "..."}`) ou "network". */
export class ApiFailure extends Error {
  constructor(
    readonly code: string,
    readonly status = 0,
  ) {
    super(code);
  }
}

const UPLOAD_ERRORS = new Set<UploadError>([
  "unsupported_format",
  "file_too_large",
  "too_many_pages",
  "pdf_password",
  "multiple_files",
  "too_many_active_jobs",
]);

/** Mensagem de envio para um código de erro (desconhecido = falha de envio). */
export function uploadErrorFor(code: string): UploadError {
  return UPLOAD_ERRORS.has(code as UploadError) ? (code as UploadError) : "network";
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiFailure("network");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { error?: string } | null;
    throw new ApiFailure(body?.error ?? "network", response.status);
  }
  return response;
}

export async function createJob(file: Blob, name: string): Promise<Job> {
  const form = new FormData();
  form.append("file", file, name);
  return (await request("/jobs", { method: "POST", body: form })).json();
}

export async function getJob(id: string): Promise<Job> {
  return (await request(`/jobs/${id}`)).json();
}

export async function getResult(id: string): Promise<Document> {
  return (await request(`/jobs/${id}/result`)).json();
}

export async function deleteJob(id: string): Promise<void> {
  await request(`/jobs/${id}`, { method: "DELETE" }).catch(() => undefined);
}

export async function reviewWord(id: string, wordId: string, text: string): Promise<void> {
  await request(`/jobs/${id}/result`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ words: [{ id: wordId, text }] }),
  });
}

export function cropUrl(id: string, wordId: string): string {
  return `${API_URL}/jobs/${id}/crops/${encodeURIComponent(wordId)}`;
}

export function imageUrl(id: string, blockId: string): string {
  return `${API_URL}/jobs/${id}/images/${encodeURIComponent(blockId)}`;
}

/** Baixa o Word ou PDF; o nome vem do servidor (nome base do arquivo enviado). */
export async function downloadExport(id: string, fmt: "docx" | "pdf", fallbackName: string) {
  const response = await request(`/jobs/${id}/export?fmt=${fmt}`);
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = /filename\*=UTF-8''([^;]+)|filename="([^"]+)"/i.exec(disposition);
  const name = match ? decodeURIComponent(match[1] ?? match[2]) : `${fallbackName}.${fmt}`;
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
