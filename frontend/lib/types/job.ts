/* Gerado por `npm run gen:types` a partir de backend/app/models. Não edite à mão. */

export type JobState = "queued" | "processing" | "done" | "failed" | "cancelled" | "expired";
/**
 * Etapa real da conversão, mostrada na tela de progresso (spec job-processing).
 */
export type JobStage = "queued" | "preparing" | "layout" | "reading" | "finishing";

export interface Job {
  id: string;
  source_file: string;
  created_at: string;
  state: JobState;
  progress: number;
  stage: JobStage;
  page: number;
  pages: number;
  error: string | null;
}
