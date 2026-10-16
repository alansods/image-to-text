// Logotipo: uma folha com linhas de texto e um selo de conferido.
export function LogoMark({ size = 26 }: { size?: number }) {
  return (
    <svg viewBox="0 0 28 28" width={size} height={size} aria-hidden="true" className="shrink-0">
      <rect x="3" y="2" width="18" height="24" rx="3" fill="none" stroke="var(--primary)" strokeWidth="2" />
      <path d="M8 9h8M8 13h8M8 17h5" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" />
      <rect x="15" y="15" width="11" height="11" rx="3" fill="var(--primary)" />
      <path
        d="m18 20.5 2 2 3.5-4"
        stroke="var(--primary-foreground)"
        strokeWidth="1.8"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
