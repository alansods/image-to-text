/* Gerado por `npm run gen:types` a partir de backend/app/models. Não edite à mão. */

export type JobState = "queued" | "processing" | "done" | "failed" | "cancelled" | "expired";

export interface Job {
  id: string;
  source_file: string;
  created_at: string;
  state: JobState;
  progress: number;
  error: string | null;
}
