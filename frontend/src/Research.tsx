import { useEffect, useMemo, useState } from 'react'
import { BookOpen, Database, LoaderCircle } from 'lucide-react'
import { api } from './api'
import AnswerAudit from './AnswerAudit'
import type { Audit } from './AnswerAudit'
import LeakageReview from './LeakageReview'
import type { Capture, DerivedLeakage } from './LeakageReview'

type Row = { project: string; bug_id: string; source: string; operator: string; single: boolean | null; chain: boolean | null; fn_leak: boolean | null; chain_step1: boolean | null; chain_step2: boolean | null; chain_step3: boolean | null; audit?: Audit | null; audit_status?: string; derived_leakage?: DerivedLeakage }
type Run = { filename: string; sha256: string; model_label: string; duplicate_of: string | null; rows: Row[] }
type Report = { id: string; name: string; runs: Run[]; notes: string[]; run_count: number; observation_count: number; capture_evidence?: Record<string, Capture> }
type Entry = { id: string; name: string; run_count: number; observation_count: number }
const percentage = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`
const hit = (value: boolean | null) => value === null ? 'Unknown' : value ? 'Hit' : 'Miss'

export default function Research() {
  const [entries, setEntries] = useState<Entry[]>([])
  const [importId, setImportId] = useState('')
  const [report, setReport] = useState<Report | null>(null)
  const [runIndex, setRunIndex] = useState(0)
  const [project, setProject] = useState('all')
  const [leakage, setLeakage] = useState('all')
  const [labelSource, setLabelSource] = useState('recorded')
  const [evidenceRow, setEvidenceRow] = useState<Row | null>(null)
  const [auditFilter, setAuditFilter] = useState('all')
  const [selected, setSelected] = useState<Row | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let live = true
    api<Entry[]>('/research').then(items => {
      if (!live) return
      setEntries(items); setImportId(items[0]?.id ?? ''); setLoading(false)
    }).catch(err => { if (live) { setError(err.message); setLoading(false) } })
    return () => { live = false }
  }, [])
  useEffect(() => {
    if (!importId) return
    let live = true
    setLoading(true); setError(''); setReport(null)
    api<Report>(`/research/${importId}`).then(item => {
      if (!live) return
      setReport(item); setRunIndex(0); setProject('all'); setLeakage('all'); setLoading(false)
    }).catch(err => { if (live) { setError(err.message); setLoading(false) } })
    return () => { live = false }
  }, [importId])
  const run = report?.runs[runIndex]
  useEffect(() => { setSelected(null); setEvidenceRow(null) }, [runIndex, importId, project, leakage, auditFilter, labelSource])
  const leakageValue = (row: Row) => labelSource === 'recorded' ? row.fn_leak : row.derived_leakage?.fn_leak ?? null
  const rows = useMemo(() => (run?.rows ?? []).filter(row =>
    (project === 'all' || row.project === project) &&
    (leakage === 'all' || leakage === 'unknown' && leakageValue(row) === null || leakage === 'leak' && leakageValue(row) === true || leakage === 'clean' && leakageValue(row) === false) &&
    (auditFilter === 'all' || auditFilter === 'flagged' && row.audit?.needs_review || auditFilter === 'available' && row.audit || auditFilter === 'missing' && !row.audit)
  ), [run, project, leakage, auditFilter, labelSource])
  const pairs = rows.filter(row => row.single !== null && row.chain !== null)
  const single = pairs.length ? pairs.filter(row => row.single).length / pairs.length : null
  const chain = pairs.length ? pairs.filter(row => row.chain).length / pairs.length : null

  if (error) return <div className="error-banner" role="alert">{error}</div>
  if (loading) return <div className="loading-state"><LoaderCircle className="spin" size={18} />Reading archived results…</div>
  if (!entries.length) return <section className="panel prose-panel"><BookOpen size={24} /><h2>Connect an archived study</h2><p>Import result CSVs from a research ZIP locally. No model calls or archive scripts run.</p><code>python -m app.import_research PATH.zip --name "Research archive"</code><p>Run this from the backend directory, then reopen this view. Imports stay in your local database.</p></section>
  if (!report || !run) return null
  return <div className="research-view">
    <section className="panel research-controls"><span className="small-pill">ARCHIVED RESULTS · NO NEW INFERENCE</span><div className="research-selects"><label>Study<select aria-label="Research study" value={importId} onChange={event => setImportId(event.target.value)}>{entries.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Recorded run<select aria-label="Recorded run" value={runIndex} onChange={event => { setRunIndex(Number(event.target.value)); setProject('all'); setLeakage('all') }}>{report.runs.map((item, index) => <option key={item.filename} value={index}>{item.filename}</option>)}</select></label><label>Project<select aria-label="Research project" value={project} onChange={event => setProject(event.target.value)}><option value="all">All projects</option>{[...new Set(run.rows.map(row => row.project))].sort().map(value => <option key={value}>{value}</option>)}</select></label><label>Label source<select aria-label="Label source" value={labelSource} onChange={event => { setLabelSource(event.target.value); setLeakage('all') }}><option value="recorded">Recorded labels</option><option value="derived">Capture-derived labels</option></select></label><label>Function leakage<select aria-label="Function leakage" value={leakage} onChange={event => setLeakage(event.target.value)}><option value="all">All labels</option><option value="leak">{labelSource === 'recorded' ? 'Recorded leak' : 'Capture name match'}</option><option value="clean">{labelSource === 'recorded' ? 'Recorded no leak' : 'No capture name match'}</option><option value="unknown">Unknown</option></select></label><label>Saved answer audit<select aria-label="Saved answer audit" value={auditFilter} onChange={event => setAuditFilter(event.target.value)}><option value="all">All observations</option><option value="flagged">Review flags</option><option value="available">Answers available</option><option value="missing">Answers missing</option></select></label></div><p>{run.model_label} · {report.run_count} files · {report.observation_count} observations across files. Repeated runs are not independent bugs.</p>{run.duplicate_of && <p className="failure-text">Identical file contents also appear in {run.duplicate_of}. Do not count both as independent runs.</p>}</section>
    {labelSource === 'derived' && <div className="audit-warning" role="status">Capture-derived labels describe function-name matches in archived error text. Exact historical inputs are unverified. These strata do not reproduce the original leakage-controlled study; recorded scores and labels are unchanged.</div>}
    <div className="metrics research-metrics"><div className="metric"><div className="metric-label">PAIRED OBSERVATIONS<Database size={18} /></div><strong data-testid="research-pairs">{pairs.length}</strong><span>Within this file and current filters</span></div><div className="metric"><div className="metric-label">SINGLE-PROMPT LOCALIZED</div><strong data-testid="research-single">{percentage(single)}</strong><span>Recorded function-or-line hit</span></div><div className="metric"><div className="metric-label">CHAIN-OF-PROMPT LOCALIZED</div><strong data-testid="research-chain">{percentage(chain)}</strong><span>Recorded function-or-line hit</span></div><div className="metric"><div className="metric-label">CHAIN − SINGLE</div><strong>{single === null || chain === null ? '—' : `${((chain - single) * 100).toFixed(1)} pp`}</strong><span>Descriptive difference, not significance</span></div></div>
    {labelSource === 'derived' && <section className="panel derived-strata"><div className="panel-title"><h2>Capture-derived strata</h2><span className="muted">Current filters · descriptive recorded outcomes</span></div><div className="table-wrap"><table><thead><tr><th>Capture function-name match</th><th>Paired observations</th><th>Recorded single</th><th>Recorded chain</th></tr></thead><tbody>{([true, false, null] as const).map(value => {
      const group = rows.filter(row => (row.derived_leakage?.fn_leak ?? null) === value && row.single !== null && row.chain !== null)
      return <tr key={String(value)}><td>{value === null ? 'Unknown' : value ? 'Name match' : 'No name match'}</td><td>{group.length}</td><td>{percentage(group.length ? group.filter(row => row.single).length / group.length : null)}</td><td>{percentage(group.length ? group.filter(row => row.chain).length / group.length : null)}</td></tr>
    })}</tbody></table></div></section>}
    {selected?.audit && <AnswerAudit audit={selected.audit} caseLabel={`${selected.project} #${selected.bug_id}`} onClose={() => setSelected(null)} onNext={rows.some(row => row !== selected && row.audit?.needs_review) ? () => {
      const flagged = rows.filter(row => row.audit?.needs_review)
      setSelected(flagged[(flagged.indexOf(selected) + 1) % flagged.length])
    } : undefined} />}
    {evidenceRow?.derived_leakage && <LeakageReview label={`${evidenceRow.project} #${evidenceRow.bug_id}`} derived={evidenceRow.derived_leakage} capture={report.capture_evidence?.[evidenceRow.derived_leakage.evidence_id ?? '']} onClose={() => setEvidenceRow(null)} />}
    <section className="panel research-table"><div className="panel-title"><h2>Recorded outcomes</h2><span className="muted">{rows.filter(row => leakageValue(row) === null).length} unknown leakage labels</span></div><div className="table-wrap"><table><thead><tr><th>Case</th><th>Source / operator</th><th>Single</th><th>Chain</th><th>Recorded leakage</th><th>Capture-derived match</th><th>Chain steps 1 → 3</th><th>Saved answers</th></tr></thead><tbody>{rows.slice(0, 500).map((row, index) => <tr key={index}><td><strong>{row.project} #{row.bug_id}</strong></td><td>{row.source}{row.operator && ` / ${row.operator}`}</td><td className={row.single ? 'success-text' : ''}>{hit(row.single)}</td><td className={row.chain ? 'success-text' : ''}>{hit(row.chain)}</td><td>{row.fn_leak === null ? 'Unknown' : row.fn_leak ? 'Recorded leak' : 'Recorded no leak'}</td><td>{row.derived_leakage ? <button className="text-button" aria-label={`Review capture ${row.project} #${row.bug_id}`} onClick={() => setEvidenceRow(row)}>{row.derived_leakage.fn_leak === null ? 'Unknown · inspect' : row.derived_leakage.fn_leak ? 'Name match · inspect' : 'No match · inspect'}</button> : 'Not derived'}</td><td>{[row.chain_step1, row.chain_step2, row.chain_step3].every(value => value === null) ? 'Not recorded' : [row.chain_step1, row.chain_step2, row.chain_step3].map(hit).join(' → ')}</td><td>{row.audit ? <button className="text-button" aria-label={`Audit ${row.project} #${row.bug_id}`} onClick={() => setSelected(row)}>{row.audit.needs_review ? 'Review flags' : 'Audit answers'}</button> : row.audit_status === 'ambiguous_case_identity' ? 'Ambiguous case identity' : 'Unavailable'}</td></tr>)}</tbody></table></div>{!rows.length && <p className="empty-small">No observations match these filters. Unknown labels are not clean cases.</p>}{rows.length > 500 && <p className="empty-small">Showing the first 500 rows; metrics include all matching rows.</p>}</section>
    <section className="panel prose-panel research-notes"><h3>How to read these results</h3><ul>{report.notes.map(note => <li key={note}>{note}</li>)}</ul><p className="mono">CSV SHA-256: {run.sha256}</p></section>
  </div>
}
