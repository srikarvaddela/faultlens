type Source = { path: string; sha256: string; patch_verified: boolean; targets: { line: number; kind: string; function?: string | null }[] }
type TestRun = { exit_code: number; timeout: boolean; output: string; output_sha256: string; latency_ms: number }
type Case = { project: string; bug_id: string; status: string; ready_for_prompt_review?: boolean; upstream?: string; buggy_commit?: string; fixed_commit?: string; capture_commit_matches?: boolean | null; sources: Source[]; fresh_runs: Record<string, TestRun>; deviations?: (string | Record<string, unknown>)[]; error?: string }
export type Validation = { version: string; benchmark_revision: string; selection: string; cases: Case[]; notes: string[]; capture_inventory?: { rows: unknown[]; counts: Record<string, number>; note: string }; previous_attempts?: { cases: { status: string }[] }[] }

const statusLabel = (value: string) => ({ buggy_fails_fixed_passes: 'Bug reproduced · fixed passes', both_revisions_fail: 'Both revisions fail', environment_failure: 'Environment failure', bug_not_reproduced: 'Bug did not reproduce' }[value] ?? value.replaceAll('_', ' '))

export default function RealValidation({ validation }: { validation: Validation }) {
  const ready = validation.cases.filter(item => item.ready_for_prompt_review).length
  return <section className="panel real-validation" aria-label="Real-case validation">
    <div className="panel-title"><div><span className="small-pill">FRESH REPRODUCTION CHECKS</span><h2>Real-case readiness</h2></div><span className="muted">{ready}/{validation.cases.length} ready for prompt review</span></div>
    <div className="validation-intro"><p>Buggy and fixed revisions run the same regression tests in fresh source directories. A reproduced case still needs a frozen prompt and a leakage review before an AI benchmark.</p><p>{validation.selection}</p>{validation.capture_inventory && <p>Capture commit audit: {Object.entries(validation.capture_inventory.counts).map(([label, count]) => `${count} ${label.replaceAll('_', ' ')}`).join(' · ')}. {validation.capture_inventory.note}</p>}<p>Earlier attempts retained: {validation.previous_attempts?.length ?? 0}. Historical prompt identity remains unverified.</p></div>
    {validation.cases.map(item => <details key={`${item.project}-${item.bug_id}`} className="validation-case"><summary><strong>{item.project} #{item.bug_id}</strong><span className={item.ready_for_prompt_review ? 'success-text' : 'failure-text'}>{statusLabel(item.status)}</span></summary>
      {item.error && <p>{item.error}</p>}
      <p className="mono">Buggy revision: {item.buggy_commit ?? 'Unavailable'}<br />Fixed revision: {item.fixed_commit ?? 'Unavailable'}</p>
      <p>Archived capture commit: {item.capture_commit_matches === true ? 'Matches benchmark' : item.capture_commit_matches === false ? 'Mismatch or unrecorded' : 'Unavailable'}</p>
      {item.sources.map(source => <div key={source.path}><h3>{source.path} · {source.patch_verified ? 'Patch context verified' : 'Source needs review'}</h3><p>Changed old-file locations: {source.targets.map(t => `${t.line} (${t.function ?? 'module/class body'}${t.kind === 'insertion_anchor' ? ', insertion anchor' : ''})`).join(', ')}</p><p className="mono">Source SHA-256: {source.sha256}</p></div>)}
      {Object.entries(item.fresh_runs).map(([variant, run]) => <div key={variant}><h3>{variant} test · exit {run.exit_code}{run.timeout ? ' · timed out' : ''}</h3><pre aria-label={`${item.project} ${item.bug_id} ${variant} reproduction output`}>{run.output}</pre><p className="mono">Output SHA-256: {run.output_sha256}</p></div>)}
      {!!item.deviations?.length && <><h3>Environment and setup adjustments</h3><ul>{item.deviations.map((value, index) => <li key={index}>{typeof value === 'string' ? value : JSON.stringify(value)}</li>)}</ul></>}
    </details>)}
    <div className="validation-intro"><p className="mono">BugsInPy revision: {validation.benchmark_revision}</p><ul>{validation.notes.map(note => <li key={note}>{note}</li>)}</ul></div>
  </section>
}
