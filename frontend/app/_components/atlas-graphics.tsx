export function Contours({ className = "" }: { className?: string }) {
  return <svg className={`contours ${className}`} viewBox="0 0 500 540" fill="none" aria-hidden="true">
    <g stroke="currentColor" strokeWidth=".7" opacity=".6">
      {Array.from({ length: 18 }, (_, i) => <path key={i} transform={`translate(${360 * (1 - (1 + i * .12))} ${110 * (1 - (1 + i * .12))}) scale(${1 + i * .12})`} d="M370 63C398 53 425 70 415 91C405 113 382 109 377 131C371 152 345 156 329 141C313 128 306 113 321 96C335 81 348 71 370 63Z" />)}
      {Array.from({ length: 15 }, (_, i) => <path key={i} transform={`translate(${355 * (1 - (1 + i * .13))} ${405 * (1 - (1 + i * .13))}) scale(${1 + i * .13})`} d="M355 365C382 347 415 372 412 396C408 414 389 417 375 438C357 459 331 443 319 423C303 399 330 382 355 365Z" />)}
    </g>
    <g stroke="currentColor" strokeWidth=".6" opacity=".2"><path d="M0 260h500M330 0v540M170 0v540" /><circle cx="330" cy="260" r="66" /><circle cx="330" cy="260" r="95" /></g>
    <circle cx="330" cy="260" r="23" fill="var(--sa-vermilion)" />
    <path d="M324 260h12m-6-6v12" stroke="var(--sa-paper)" />
    <path d="M100 300h14m-7-7v14M204 475h14m-7-7v14" stroke="currentColor" strokeWidth="1" />
  </svg>;
}

// Original vector terrain study: illustrative geometry, never a data visualization.
export function Terrain({ className = "" }: { className?: string }) {
  const ridge = "M0 168L30 150L48 157L78 115L94 123L124 72L143 86L168 39L183 51L203 17L221 66L236 54L258 99L274 81L307 121L324 108L353 146L377 133L412 166L450 181L0 181Z";
  return <svg className={`terrain ${className}`} viewBox="0 0 450 190" aria-hidden="true" fill="none">
    <path d={ridge} fill="var(--sa-canvas)" stroke="currentColor" strokeWidth=".8" />
    <g fill="currentColor" opacity=".18"><path d="M78 115L94 123L48 181H30Z M124 72L143 86L96 181H65Z M168 39L183 51L154 123L121 181H100Z M203 17L221 66L196 91L187 181H146Z M236 54L258 99L232 181H210Z M274 81L307 121L294 181H255Z M324 108L353 146L350 181H310Z" /></g>
    <g stroke="currentColor" strokeWidth=".65" opacity=".6">
      <path d="M203 17L194 70L170 103L187 119L161 152L146 181M168 39L156 80L137 99L148 113L115 145L100 181M124 72L117 104L95 121L104 134L65 181M236 54L229 104L246 124L218 153L210 181M274 81L266 113L282 133L255 181M324 108L313 137L333 151L310 181M78 115L69 140L48 181" />
      {Array.from({ length: 26 }, (_, i) => {
        const x = 27 + i * 14;
        const peak = 176 - 130 * Math.exp(-(((x - 204) / 93) ** 2));
        return <path key={i} d={`M${x} 181l12 -17 -5 -14 16 -17 -3 -12 M${x + 2} 177L${x + 29} ${Math.max(peak + 35, 80)}`} />;
      })}
    </g>
  </svg>;
}

export function Icon({ name }: { name: "check" | "layers" | "book" | "person" | "home" | "menu" }) {
  return <svg className="ui-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === "check" && <><circle cx="12" cy="12" r="9" fill="currentColor" stroke="none" /><path d="m7 12 3 3 7-7" stroke="var(--sa-paper)" /></>}
    {name === "layers" && <><path d="m12 3 10 5-10 5L2 8Z" /><path d="m2 12 10 5 10-5M2 16l10 5 10-5" /></>}
    {name === "book" && <><path d="M12 5v16M12 5C8 2 4 3 2 4v15c4-1 7-1 10 2 3-3 6-3 10-2V4c-2-1-6-2-10 1Z" /></>}
    {name === "person" && <><circle cx="12" cy="7" r="4" /><path d="M4 22v-3a8 8 0 0 1 16 0v3" /></>}
    {name === "home" && <><path d="m2 10 10-8 10 8M5 8v13h5v-7h4v7h5V8" /></>}
    {name === "menu" && <path d="M4 6h16M4 12h16M4 18h16" />}
  </svg>;
}
