import { money, number, readable, timestamp, type Explanation, type TransactionRow } from "../_lib/transactions";
import { ResponsiveDisclosure } from "./responsive-disclosure";

export function RiskLabel({ band }: { band: string }) {
  return <span className={`risk-label risk-${band.toLowerCase()}`}>{band} risk</span>;
}

export function TransactionRows({ items }: { items: TransactionRow[] }) {
  return <><table className="tx-table tx-desktop"><caption className="sr-only">Organization transactions, newest event first</caption>
    <thead><tr><th scope="col">Reference / event</th><th scope="col">Amount</th><th scope="col">Screening score</th><th scope="col">Risk band</th></tr></thead>
    <tbody>{items.map(tx => <tr key={tx.id}><th scope="row"><a href={`/transactions/${tx.id}`}>{tx.external_id}<span aria-hidden="true"> ↗</span></a><small>{timestamp(tx.occurred_at)}</small></th><td className="tx-number">{money(tx.amount, tx.currency)}</td><td className="tx-number">{number(tx.risk_score, 2)} / 100</td><td><RiskLabel band={tx.risk_band} /></td></tr>)}</tbody>
  </table><div className="tx-mobile">{items.map(tx => <article className="tx-card" key={tx.id}><h2><a href={`/transactions/${tx.id}`}>{tx.external_id}<span aria-hidden="true"> ↗</span></a></h2><p className="muted">{timestamp(tx.occurred_at)}</p><dl className="tx-card-values"><div><dt>Amount</dt><dd>{money(tx.amount, tx.currency)}</dd></div><div><dt>Screening score</dt><dd>{number(tx.risk_score, 2)} <span>/ 100</span></dd></div></dl><RiskLabel band={tx.risk_band} /></article>)}</div></>;
}

function EvidenceValues({ values }: { values: Record<string, unknown> }) {
  return <dl className="tx-facts">{Object.entries(values).map(([key, value]) => <div key={key}><dt>{readable(key)}</dt><dd>{value === null ? "Not recorded" : typeof value === "object" ? JSON.stringify(value) : String(value)}</dd></div>)}</dl>;
}

export function ScoringEvidence({ evidence }: { evidence: Explanation }) {
  const attribution = evidence.supervised_attribution;
  const labels = { supervised: "Supervised model output", anomaly: "Anomaly percentile", rules: "Rule signal" };
  const states: Record<string, string> = { HIT: "Fired", NOT_HIT: "Evaluated · no hit", DISABLED: "Disabled", NOT_CONFIGURED: "Not evaluated · not configured", MISSING_HISTORY: "Not evaluated · missing history", UNSUPPORTED_PARAMETERS: "Not evaluated · unsupported parameters" };
  return <>
    {!attribution.available && <p className="status">Feature attribution is unavailable: {readable(attribution.reason ?? "not recorded at scoring time")}. Available components and rules remain below.</p>}
    {evidence.rule_evaluations.some(rule => !["HIT", "NOT_HIT", "DISABLED"].includes(rule.status)) && <p className="status">Some rules were not evaluated. Missing rule evidence is not evidence of safety; expand Rule evidence for the recorded reasons.</p>}
    <ResponsiveDisclosure id="components-evidence" title="Risk components" eyebrow="01 / Persisted evidence" mobileOpen className="tx-panel">
      <p className="muted">Values and weights recorded with this score. Component values use a 0–1 scale; risk points use a 0–100 scale.</p>
      <div className="tx-component-grid">{Object.entries(evidence.component_contributions).map(([key, component]) => <article key={key}><h3>{labels[key as keyof typeof labels]}</h3><dl><dt>Value</dt><dd>{number(component.value, 6)}</dd><dt>Weight</dt><dd>{number(component.weight, 6)}</dd><dt>Risk points</dt><dd>{number(component.risk_points, 6)}</dd></dl></article>)}</div>
      <details><summary>Historical scoring configuration</summary><EvidenceValues values={evidence.settings_snapshot} /></details>
    </ResponsiveDisclosure>
    <ResponsiveDisclosure id="rules-evidence" title="Rule evidence" eyebrow="02 / Recorded observations" className="tx-panel"><p className="muted">Missing history or unevaluated rules are not evidence of safety.</p>
      {evidence.rule_evaluations.map(({ code, status, ...values }) => <article className="tx-rule" key={code}><h3>{readable(code)}</h3><p>{states[status] ?? readable(status)}</p>{Object.keys(values).length > 0 && <details><summary>Recorded parameters and observations</summary><EvidenceValues values={values} /></details>}</article>)}
      {!evidence.rule_evaluations.length && <p>No rule evaluations were recorded with this score.</p>}
    </ResponsiveDisclosure>
    <ResponsiveDisclosure id="shap-evidence" title="Supervised SHAP contributions" eyebrow="03 / Model attribution" className="tx-panel"><p className="muted">SHAP explains only the supervised classifier, not the composite screening score. Contributions are in log-odds, not risk points or probabilities.</p>
      {attribution.available ? <><p className="tx-technical">{attribution.method} · Model {evidence.model_version_id}</p>
        <ul className="tx-attributions">{attribution.top_features.slice(0, 5).map(feature => <li key={feature.transformed_feature}><div><strong>{readable(feature.feature)}</strong><small>{feature.transformed_feature}</small></div><div><strong>{Number(feature.contribution) > 0 ? "+" : ""}{number(feature.contribution, 6)}</strong><small>{Number(feature.contribution) > 0 ? "Increases" : Number(feature.contribution) < 0 ? "Decreases" : "No change to"} model log-odds</small></div></li>)}</ul>
        {attribution.top_features.length === 0 && <p>No feature contributions were recorded.</p>}
        <EvidenceValues values={{ base_value: attribution.base_value, model_output: attribution.model_output, remaining_features_contribution: attribution.remaining_features_contribution }} /><p className="muted">{attribution.limitation}</p>
      </> : <p className="status">Feature attribution is unavailable: {readable(attribution.reason ?? "not recorded at scoring time")}. No contributions have been invented.</p>}
      <ul className="tx-limitations">{evidence.limitations.map(text => <li key={text}>{text}</li>)}</ul>
    </ResponsiveDisclosure>
  </>;
}
