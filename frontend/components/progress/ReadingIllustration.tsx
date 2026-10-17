/** Folha sendo lida: uma faixa de leitura desce pela página e as linhas de texto vão
 * aparecendo atrás dela. Só decoração (o texto ao lado diz o que acontece); com "reduzir
 * movimento" no sistema, fica parada (animações em globals.css). */
const LINES = [
  { y: 30, w: 52 },
  { y: 44, w: 76 },
  { y: 54, w: 70 },
  { y: 64, w: 74 },
  { y: 74, w: 48 },
  { y: 88, w: 76 },
  { y: 98, w: 62 },
];

export function ReadingIllustration() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 160 132"
      className="reading-illustration h-[132px] w-40"
      data-testid="reading-illustration"
    >
      <rect x="38" y="10" width="92" height="116" rx="6" className="fill-foreground/5" />
      <rect
        x="32"
        y="4"
        width="92"
        height="116"
        rx="6"
        className="fill-paper stroke-border-strong"
        strokeWidth="1.5"
      />
      <g>
        {LINES.map((line) => (
          <rect
            key={line.y}
            x="44"
            y={line.y}
            width={line.w}
            height="5"
            rx="2.5"
            className="reading-line fill-primary/70"
            // aparece quando a faixa (100 px em 3,2 s) chega à linha
            style={{ animationDelay: `${(((line.y - 17) / 100) * 3.2).toFixed(2)}s` }}
          />
        ))}
      </g>
      <g className="reading-scan">
        <rect x="33" y="4" width="90" height="14" className="fill-primary-soft/70" />
        <rect x="33" y="17" width="90" height="2" rx="1" className="fill-primary" />
      </g>
    </svg>
  );
}
