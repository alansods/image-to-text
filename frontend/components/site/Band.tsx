import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Faixa azul-escura no topo de cada tela (continua a barra superior); o cartão principal da
 * tela sobe por cima dela com margem negativa. */
export function Band({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("bg-navy text-on-navy", className)}>{children}</div>;
}
