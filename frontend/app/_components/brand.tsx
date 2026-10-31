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
