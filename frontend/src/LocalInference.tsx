import { useEffect, useState } from 'react'
import { ArrowDownToLine, LoaderCircle } from 'lucide-react'
import { api } from './api'

type Inventory = { connected: boolean; models: { name: string; digest: string }[]; error?: string; server_version?: string }
type Run = {
  id: string; status: string; cancel_requested: boolean; error: string | null
  model_identity: { name: string; digest: string }; options: Record<string, unknown>
  calls: { strategy: string; step: number; status: string; messages: { role: string; content: string }[]; latency_ms?: number; response: { message?: { content?: string }; prompt_eval_count?: number; eval_count?: number; done_reason?: string; load_duration?: number } | null }[]
  results: { strategy: string; fault_rank: number | null; top1: boolean; top3: boolean; parse: { valid: boolean; error: string | null; candidates: { line: number; reason: string }[] } }[]
}
const label = (strategy: string) => strategy === 'single' ? 'Single prompt' : strategy === 'chain_evidence' ? 'Three-step chain · evidence carried' : 'Three-step chain · original carryover'

export default function LocalInference({ planId }: { planId: string }) {
  const [inventory, setInventory] = useState<Inventory | null>(null)
  const [model, setModel] = useState('')
  const [compare, setCompare] = useState(true)
  const [run, setRun] = useState<Run | null>(null)
  const [history, setHistory] = useState<{ id: string; model: string; bug_id: string; status: string }[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function refresh() {
    const result = await api<Inventory>('/ollama/status')
    setInventory(result)
    setModel(previous => result.models.some(item => item.name === previous) ? previous : result.models.find(item => item.name === 'llama3.2:1b')?.name ?? result.models[0]?.name ?? '')
  }
  useEffect(() => { void refresh().catch(err => setError(err.message)); void api<typeof history>('/ollama/runs').then(setHistory).catch(err => setError(err.message)) }, [])
  useEffect(() => {
    if (!run || !['queued', 'running'].includes(run.status)) return
    let live = true
    let pending = false
    const timer = window.setInterval(async () => {
      if (pending) return
      pending = true
      try {
        const updated = await api<Run>(`/ollama/runs/${run.id}`)
        if (live) { setRun(updated); setHistory(previous => previous.map(item => item.id === updated.id ? { ...item, status: updated.status } : item)) }
      } catch (err) { if (live) setError(err instanceof Error ? err.message : 'Could not refresh local run') }
      finally { pending = false }
    }, 1000)
    return () => { live = false; window.clearInterval(timer) }
  }, [run?.id, run?.status])
  async function start() {
    setBusy(true); setError('')
    try {
      const job = await api<{ id: string }>('/ollama/runs', { method: 'POST', body: JSON.stringify({ plan_id: planId, model, compare }) })
      const result = await api<Run>(`/ollama/runs/${job.id}`)
      setRun(result); setHistory(await api<typeof history>('/ollama/runs'))
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to start Ollama run') }
    finally { setBusy(false) }
  }
  async function action(name: 'cancel' | 'retry') {
    if (!run) return
    setBusy(true); setError('')
    try {
      const job = await api<{ id: string }>(`/jobs/${run.id}/${name}`, { method: 'POST' })
      setRun(await api<Run>(`/ollama/runs/${job.id}`))
      setHistory(await api<typeof history>('/ollama/runs'))
    } catch (err) { setError(err instanceof Error ? err.message : 'Local run action failed') }
    finally { setBusy(false) }
  }
  return <section className="panel local-inference" aria-label="Local Ollama inference"><div className="panel-title"><h2>Run locally with Ollama</h2><span className="small-pill">LOCAL INFERENCE · CURATED CASE</span></div><div className="local-controls"><p>{inventory?.connected ? `${inventory.models.length} installed local models · Ollama ${inventory.server_version ?? ''}` : inventory?.error ?? 'Checking Ollama…'}</p>{!inventory?.connected && <button className="text-button" onClick={() => void refresh().catch(err => setError(err.message))}>Refresh connection</button>}<div className="research-selects"><label>Installed model<select aria-label="Ollama model" disabled={busy || !inventory?.models.length} value={model} onChange={event => setModel(event.target.value)}>{inventory?.models.map(item => <option key={item.digest} value={item.name}>{item.name}</option>)}</select></label><label>Run mode<select aria-label="Ollama run mode" disabled={busy} value={compare ? 'compare' : 'selected'} onChange={event => setCompare(event.target.value === 'compare')}><option value="compare">Compare single vs evidence-carrying chain</option><option value="selected">Run selected plan only</option></select></label></div><p>Both comparison methods use the same frozen source and evidence. Generation is bounded to 256 output tokens per call; a comparison makes four calls. This is a smoke test, not a general accuracy benchmark. Sequential timings include model loading and cache effects.</p><button className="button primary" onClick={() => void start()} disabled={busy || !model || !!run && ['queued', 'running'].includes(run.status)}>{busy && <LoaderCircle size={14} className="spin" />}Run with Ollama</button></div>{error && <div className="error-banner" role="alert">{error}</div>}{run && <div className="local-result" aria-label="Local inference result"><div className="panel-title"><h3>{run.cancel_requested && run.status === 'running' ? 'Cancelling after current call' : `Run ${run.status}`}</h3><div className="audit-actions">{['queued', 'running'].includes(run.status) && <button className="text-button" disabled={busy || run.cancel_requested} onClick={() => void action('cancel')}>Cancel local run</button>}{['failed', 'cancelled'].includes(run.status) && <button className="text-button" disabled={busy} onClick={() => void action('retry')}>Retry as new run</button>}<a className="text-button" href={`/api/ollama/runs/${run.id}/export`}><ArrowDownToLine size={13} />Export transcript</a></div></div>{run.error && <div className="audit-warning">{run.error}</div>}<div className="audit-provenance"><span>Model: {run.model_identity.name}</span><span>Digest: {run.model_identity.digest}</span><span>Settings: {JSON.stringify(run.options)}</span></div>{run.results.map(result => <div className="local-ranking" key={result.strategy}><strong>{label(result.strategy)}</strong><span>{result.parse.valid ? `Known fault rank: ${result.fault_rank ?? 'Not ranked'} · Top-1: ${result.top1 ? 'hit' : 'miss'}` : `Parse failure: ${result.parse.error}`}</span><ol>{result.parse.candidates.map(candidate => <li key={candidate.line}>Line {candidate.line}: {candidate.reason}</li>)}</ol></div>)}<div className="local-calls">{run.calls.map((call, index) => <details key={index}><summary>{label(call.strategy)} · step {call.step} · {call.status}{call.latency_ms !== undefined && ` · ${(call.latency_ms / 1000).toFixed(2)}s`}</summary><p>Input tokens: {call.response?.prompt_eval_count ?? 'Unavailable'} · Output tokens: {call.response?.eval_count ?? 'Unavailable'} · Stop: {call.response?.done_reason ?? 'Unavailable'}</p><p>Model-load time: {call.response?.load_duration === undefined ? 'Unavailable' : `${(call.response.load_duration / 1e9).toFixed(2)}s`}</p><h4>Exact messages saved before request</h4><pre>{JSON.stringify(call.messages, null, 2)}</pre><h4>Saved response</h4><pre>{call.response?.message?.content ?? 'No response captured; call completion may be uncertain.'}</pre></details>)}</div></div>}{history.length > 0 && <div className="local-history"><h3>Saved local runs</h3>{history.slice(0, 10).map(item => <button className="text-button" key={item.id} onClick={() => void api<Run>(`/ollama/runs/${item.id}`).then(setRun).catch(err => setError(err.message))}>{item.bug_id} · {item.model} · {item.status}</button>)}</div>}</section>
}
