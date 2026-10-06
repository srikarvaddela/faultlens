import { useEffect, useState } from 'react'
import { ArrowDownToLine, LoaderCircle } from 'lucide-react'
import { api } from './api'
import LocalInference from './LocalInference'
import type { Bug } from './types'

type Entry = { kind?: string; id: string; created_at: string; bug_id: string; strategy: string; evidence_mode: string; prompt_version: string }
type Plan = Entry & { status: string; steps: string[]; carry_evidence: boolean; first_messages: { role: string; content: string }[]; first_messages_sha256: string; evidence_sha256: string; source_sha256: string; plan_sha256: string; notes: string[] }
const labels: Record<string, string> = { single: 'Single prompt', chain_original: 'Three steps · evidence at step 1', chain_evidence: 'Three steps · evidence carried forward' }

export default function PromptLab({ bugs }: { bugs: Bug[] }) {
  const [bugId, setBugId] = useState(bugs[0]?.id ?? '')
  const [sourceKind, setSourceKind] = useState('curated')
  const [realId, setRealId] = useState('')
  const [realCases, setRealCases] = useState<{ id: string; case_label: string; status: string; reason: string | null }[]>([])
  const [strategy, setStrategy] = useState('single')
  const [mode, setMode] = useState('failure_details')
  const [entries, setEntries] = useState<Entry[]>([])
  const [plan, setPlan] = useState<Plan | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    api<typeof realCases>('/real-cases').then(items => { if (live) { setRealCases(items); setRealId(items.find(item => item.status === 'ready')?.id ?? '') } }).catch(err => { if (live) setError(err.message) })
    api<Entry[]>('/prompt-plans').then(items => { if (live) setEntries(items) }).catch(err => { if (live) setError(err.message) })
    return () => { live = false }
  }, [])
  async function prepare() {
    setBusy(true); setError('')
    try {
      const item = await api<Plan>(sourceKind === 'real' ? '/real-prompt-plans' : '/prompt-plans', { method: 'POST', body: JSON.stringify(sourceKind === 'real' ? { case_id: realId, strategy: strategy === 'chain_original' ? 'chain_evidence' : strategy } : { bug_id: bugId, strategy, evidence_mode: mode }) })
      setPlan(item); setEntries(previous => [item, ...previous])
    } catch (err) { setError(err instanceof Error ? err.message : 'Plan preparation failed') }
    finally { setBusy(false) }
  }
  async function open(id: string) {
    setBusy(true); setError('')
    try { setPlan(await api<Plan>(`/prompt-plans/${id}`)) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to open plan') }
    finally { setBusy(false) }
  }
  return <div className="prompt-lab">
    {error && <div className="error-banner" role="alert">{error}</div>}
    <section className="panel research-controls"><span className="small-pill">PLAN PREPARATION · NO MODEL CALLS</span><p>Freeze curated or validated real evidence and versioned prompt configuration. Preparation makes no model calls; run the saved plan below with Ollama.</p><form onSubmit={event => { event.preventDefault(); void prepare() }}><div className="research-selects"><label>Input source<select aria-label="Prompt input source" value={sourceKind} disabled={busy} onChange={event => { setSourceKind(event.target.value); setStrategy('single'); setPlan(null) }}><option value="curated">Curated fixtures</option><option value="real">Validated real cases</option></select></label>{sourceKind === 'real' ? <label>Real case<select aria-label="Real prompt case" value={realId} disabled={busy} onChange={event => setRealId(event.target.value)}>{realCases.filter(item => item.status === 'ready').map(item => <option key={item.id} value={item.id}>{item.case_label}</option>)}</select></label> : <label>Curated case<select aria-label="Prompt case" value={bugId} disabled={busy} onChange={event => setBugId(event.target.value)}>{bugs.map(bug => <option key={bug.id} value={bug.id}>{bug.id} · {bug.title}</option>)}</select></label>}<label>Prompt strategy<select aria-label="Prompt strategy" value={strategy} disabled={busy} onChange={event => setStrategy(event.target.value)}>{Object.entries(labels).filter(([id]) => sourceKind !== 'real' || id !== 'chain_original').map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select></label>{sourceKind === 'real' ? <p>Fresh regression output · full files · oracle-assisted file selection. No leakage-free or repository-wide claim.</p> : <label>Failure evidence<select aria-label="Failure evidence" value={mode} disabled={busy} onChange={event => setMode(event.target.value)}><option value="failure_details">Failing tests: expected / actual / exceptions</option><option value="exception_only">Captured exceptions only</option></select></label>}</div><button type="submit" className="button primary" disabled={busy || (sourceKind === 'real' ? !realId : !bugId)}>{busy && <LoaderCircle size={14} className="spin" />}Prepare prompt plan</button></form>{sourceKind === 'real' && <div className="real-exclusions"><h3>Selection and exclusions</h3>{realCases.length === 0 && <p>Freeze validated inputs locally with python -m app.freeze_real_cases PATH/validation.json.</p>}{realCases.map(item => <p key={item.id}>{item.case_label} · {item.status === 'ready' ? 'Ready for inference' : `Excluded: ${item.reason}`}</p>)}</div>}</section>
    {plan && <section className="panel prompt-preview" aria-label="Prepared prompt plan"><div className="panel-title"><div><span className="small-pill">PREPARED · NO INFERENCE</span><h2>{plan.bug_id} · {labels[plan.strategy]}</h2></div><a className="text-button" href={`/api/prompt-plans/${plan.id}/export`}><ArrowDownToLine size={14} />Export plan</a></div><div className="prompt-steps">{plan.steps.map((step, index) => <div key={step}><strong>{index + 1}. {step}</strong><span>{index === 0 ? 'Exact first-step messages saved below' : 'Pending previous model responses; not materialized'}</span></div>)}</div><div className="prompt-messages"><h3>Frozen first-step messages</h3>{plan.first_messages.map((message, index) => <article key={index}><span className="small-pill">{message.role}</span><pre aria-label={`${message.role} prompt`}>{message.content}</pre></article>)}</div><div className="audit-provenance"><span>Prompt version: {plan.prompt_version}</span><span>Evidence SHA-256: {plan.evidence_sha256}</span><span>First-step messages SHA-256: {plan.first_messages_sha256}</span><span>Plan SHA-256: {plan.plan_sha256}</span><p>These hashes identify prepared content. Local inference stores each materialized request, model/configuration, response, and available usage separately from this prepared plan.</p></div><div className="prose-panel"><ul>{plan.notes.map(note => <li key={note}>{note}</li>)}</ul></div></section>}
    {plan && <LocalInference key={plan.id} planId={plan.id} kind={plan.kind} />}
    <section className="panel prompt-history"><div className="panel-title"><h2>Saved prompt plans</h2><span className="count-badge">{entries.length}</span></div>{!entries.length ? <p className="empty-small">Prepare a plan to start a reproducible input history.</p> : <div className="table-wrap"><table><thead><tr><th>Case</th><th>Strategy</th><th>Evidence</th><th /></tr></thead><tbody>{entries.map(item => <tr key={item.id}><td>{item.bug_id}</td><td>{labels[item.strategy]}</td><td>{item.evidence_mode.replaceAll('_', ' ')}</td><td><button className="text-button" disabled={busy} onClick={() => void open(item.id)}>Open plan</button></td></tr>)}</tbody></table></div>}</section>
  </div>
}
