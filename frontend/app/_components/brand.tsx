export function Mark() {
  return <svg aria-hidden="true" viewBox="0 0 40 40" className="brand-mark" fill="none">
    <path d="M6 10h28M6 30h28M20 3v34" stroke="currentColor" strokeWidth="1.5" />
    <ellipse cx="20" cy="20" rx="9" ry="17" transform="rotate(38 20 20)" stroke="currentColor" strokeWidth="2" />
    <circle cx="20" cy="20" r="3" fill="currentColor" />
  </svg>;
}

export function Brand() {
  return <a className="brand" href="/" aria-label="SentinelAI home"><Mark /><span>Sentinel<span className="brand-ai">AI</span></span></a>;
}

export function AtlasArt() {
  return <svg className="atlas-art" aria-hidden="true" viewBox="0 0 560 280" fill="none">
    <path d="M0 140h560M280 0v280" stroke="currentColor" strokeOpacity=".2" />
    {[0, 1, 2, 3, 4, 5].map(i => <ellipse key={i} cx="280" cy="140" rx={210 - i * 21} ry={71 + i * 6} transform={`rotate(${-24 + i * 9} 280 140)`} stroke="currentColor" strokeWidth="1.2" />)}
    <circle cx="280" cy="140" r="24" fill="var(--sa-vermilion)" />
    <path d="M273 140h14M280 133v14" stroke="var(--sa-paper)" strokeWidth="1.5" />
    <path d="M52 48h18m-9-9v18M490 232h18m-9-9v18" stroke="currentColor" />
  </svg>;
}
