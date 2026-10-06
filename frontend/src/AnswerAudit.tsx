import { useEffect, useRef } from 'react'
import { ArrowRight, X } from 'lucide-react'

export type AuditedAnswer = {
  answer: string; answer_sha256: string; recorded: boolean | null; legacy_replay: boolean | null
  matched_functions: string[]; line_token_hit: boolean; explicit_line_hit: boolean
  explicit_lines: number[]; flags: string[]
}
export type Audit = {
  version: string; raw_filename: string; raw_sha256: string; needs_review: boolean; flags: string[]
  ground_truth: { functions: string[]; line: number | null }
  csv_ground_truth: { functions: string[]; line: number | null }
  answers: { single: AuditedAnswer; chain: AuditedAnswer }
}
const labels: Record<string, string> = {
  empty_saved_answer: 'Saved answer is empty',
  unanchored_line_number: 'Ground-truth number appears without an explicit line reference or matching function',
  recorded_replay_disagreement: 'Recorded score differs from legacy scorer replay',
  credential_pattern_redacted: 'A credential-like string was redacted',
  csv_raw_ground_truth_disagreement: 'CSV and saved-answer ground truth differ',
}
const hit = (value: boolean | null) => value === null ? 'Unknown' : value ? 'Hit' : 'Miss'

export default function AnswerAudit({ audit, caseLabel, onClose, onNext }: { audit: Audit; caseLabel: string; onClose: () => void; onNext?: () => void }) {
  const panel = useRef<HTMLElement>(null)
  useEffect(() => { panel.current?.focus() }, [audit])
  return <section ref={panel} tabIndex={-1} className="panel answer-audit" aria-label="Answer audit">
    <div className="panel-title"><div><span className="small-pill">AUDIT v{audit.version} · HUMAN REVIEW</span><h2>{caseLabel}</h2></div><div className="audit-actions">{onNext && <button className="text-button" onClick={onNext}>Next flagged case<ArrowRight size={13} /></button>}<button className="icon-button" aria-label="Close answer audit" onClick={onClose}><X size={18} /></button></div></div>
    <div className="audit-truth"><strong>Saved-answer ground truth</strong><span>Functions: {audit.ground_truth.functions.join(', ') || 'Not recorded'}</span><span>Line: {audit.ground_truth.line ?? 'Not recorded'}</span><p>This is archived metadata, not independently reconstructed ground truth. Review flags do not change recorded results.</p></div>
    {audit.flags.length > 0 && <div className="audit-warning" role="status">{audit.flags.map(flag => <p key={flag}>{labels[flag] ?? flag}</p>)}<p>CSV functions: {audit.csv_ground_truth.functions.join(', ') || 'Not recorded'} · CSV line: {audit.csv_ground_truth.line ?? 'Not recorded'}</p></div>}
    <div className="audit-answers">{(['single', 'chain'] as const).map(method => {
      const answer = audit.answers[method]
      return <article key={method}><h3>{method === 'single' ? 'Single-prompt' : 'Chain-of-prompt'}</h3><div className="audit-score"><span>Recorded: <strong>{hit(answer.recorded)}</strong></span><span>Legacy replay: <strong>{hit(answer.legacy_replay)}</strong></span></div>{answer.flags.length > 0 && <div className="audit-warning">{answer.flags.map(flag => <p key={flag}>{labels[flag] ?? flag}</p>)}</div>}<pre aria-label={`${method === 'single' ? 'Single-prompt' : 'Chain-of-prompt'} saved answer`}>{answer.answer || '(Empty saved answer)'}</pre><dl><dt>Matched function names</dt><dd>{answer.matched_functions.join(', ') || 'None detected'}</dd><dt>Ground-truth numeric token</dt><dd>{answer.line_token_hit ? 'Present' : 'Not detected'}</dd><dt>Explicit ground-truth line reference</dt><dd>{answer.explicit_line_hit ? 'Detected' : 'Not detected'}</dd><dt>Explicit line references</dt><dd>{answer.explicit_lines.join(', ') || 'None detected'}</dd></dl><div className="audit-hash">Answer SHA-256: {answer.answer_sha256}</div></article>
    })}</div><div className="audit-provenance"><span>Source: {audit.raw_filename}</span><span>Raw-file SHA-256: {audit.raw_sha256}</span><p>The legacy replay follows the archived function-name or numeric-token rule. Explicit-line detection is a limited text heuristic; missing a reference does not prove the model was wrong. No new inference or automatic regrading occurs.</p></div>
  </section>
}
