import { useEffect, useRef, useState } from 'react'
import { ArrowDownToLine, ArrowRight, Beaker, BookOpen, Check, CheckCircle2, ChevronDown, ChevronRight, CircleHelp, Clock3, Code2, Crosshair, Database, ExternalLink, FileCode2, FlaskConical, GitBranch, Layers3, LoaderCircle, Play, Search, ShieldCheck, SlidersHorizontal, Terminal, X, XCircle } from 'lucide-react'
import { api } from './api'
import Research from './Research'
import PromptLab from './PromptLab'
import type { Bug, Catalog, Experiment, ExperimentEntry, Job, Method, Result } from './types'

type Page = 'workbench' | 'experiments' | 'methodology' | 'research' | 'prompts'
const methodNames: Record<Method, string> = { ochiai: 'Ochiai', tarantula: 'Tarantula' }
const pct = (value: number) => `${Math.round(value * 100)}%`
const date = (value: string) => new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
const json = (value: unknown) => JSON.stringify(value)

function CodeText({ text }: { text: string }) {
  return <>{text.split(/('[^']*'|\b(?:def|if|return|raise|for|in|not)\b|\b\d+(?:\.\d+)?\b)/g).map((token, index) =>
    <span key={index} className={/^'/.test(token) ? 'syntax-string' : /^(def|if|return|raise|for|in|not)$/.test(token) ? 'syntax-keyword' : /^\d/.test(token) ? 'syntax-number' : ''}>{token}</span>)}</>
}

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [entries, setEntries] = useState<ExperimentEntry[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [experiment, setExperiment] = useState<Experiment | null>(null)
  const [selectedId, setSelectedId] = useState('FL-001')
  const [method, setMethod] = useState<Method>('ochiai')
  const [page, setPage] = useState<Page>('workbench')
  const [query, setQuery] = useState('')
  const [reveal, setReveal] = useState(false)
  const [focusedLine, setFocusedLine] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [ready, setReady] = useState(false)
  const [dialog, setDialog] = useState(false)
  const [running, setRunning] = useState(false)
  const [loadingExperiment, setLoadingExperiment] = useState(false)
  const [runName, setRunName] = useState('Curated baseline comparison')
  const [runIds, setRunIds] = useState<string[]>([])
  const [runMethods, setRunMethods] = useState<Method[]>(['ochiai', 'tarantula'])
  const modalRef = useRef<HTMLDialogElement>(null)
  const loadSequence = useRef(0)
  const pendingJob = useRef<string | null>(null)

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if (event.key === '/' && !(event.target instanceof HTMLInputElement) && !(event.target instanceof HTMLTextAreaElement) && !modalRef.current?.open) {
        event.preventDefault()
        document.querySelector<HTMLInputElement>('[aria-label="Search bugs"]')?.focus()
      }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [])

  async function load() {
    setError('')
    try {
      const [nextCatalog, nextEntries, nextJobs] = await Promise.all([api<Catalog>('/catalog'), api<ExperimentEntry[]>('/experiments'), api<Job[]>('/jobs')])
      setJobs(nextJobs)
      pendingJob.current = nextJobs.find(job => job.status === 'queued' || job.status === 'running')?.id ?? null
      setCatalog(nextCatalog); setEntries(nextEntries); setRunIds(nextCatalog.bugs.map(bug => bug.id)); setReady(true)
      if (nextEntries[0]) {
        const latest = await api<Experiment>(`/experiments/${nextEntries[0].id}`)
        setExperiment(latest); setSelectedId(latest.bug_ids[0]); setMethod(latest.methods[0])
      }
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to connect to the API.') }
  }
  useEffect(() => { void load() }, [])
  useEffect(() => {
    if (!ready) return
    let stopped = false
    let polling = false
    async function poll() {
      if (polling) return
      polling = true
      try {
        const [nextJobs, nextEntries] = await Promise.all([api<Job[]>('/jobs'), api<ExperimentEntry[]>('/experiments')])
        if (stopped) return
        setJobs(nextJobs); setEntries(nextEntries)
        const current = nextJobs.find(job => job.id === pendingJob.current)
        if (current?.status === 'completed' && current.experiment_id) {
          pendingJob.current = null
          await openExperiment(current.experiment_id)
        } else if (current?.status === 'failed' || current?.status === 'cancelled') pendingJob.current = null
      } catch (err) {
        if (!stopped) setError(err instanceof Error ? err.message : 'Could not refresh job status.')
      } finally { polling = false }
    }
    const timer = window.setInterval(() => void poll(), 1500)
    return () => { stopped = true; window.clearInterval(timer) }
  }, [ready])
  useEffect(() => {
    if (dialog) modalRef.current?.showModal()
    else modalRef.current?.close()
  }, [dialog])
  const bugs = catalog?.bugs ?? []
  const bug = bugs.find(item => item.id === selectedId)
  const result = experiment?.results.find(item => item.bug_id === selectedId && item.method === method)
  const summary = experiment?.summary[method]
  const visibleBugs = bugs.filter(item => `${item.id} ${item.title} ${item.module} ${item.category}`.toLowerCase().includes(query.toLowerCase()))

  function selectBug(id: string) { setSelectedId(id); setReveal(false); setFocusedLine(null) }
  async function openExperiment(id: string) {
    const sequence = ++loadSequence.current
    setError(''); setLoadingExperiment(true)
    try {
      const item = await api<Experiment>(`/experiments/${id}`)
      if (sequence !== loadSequence.current) return
      setExperiment(item); selectBug(item.bug_ids[0]); setMethod(item.methods[0]); setPage('workbench')
    } catch (err) { if (sequence === loadSequence.current) setError(err instanceof Error ? err.message : 'Could not open experiment.') }
    finally { if (sequence === loadSequence.current) setLoadingExperiment(false) }
  }
  async function run() {
    setRunning(true); setError('')
    try {
      const item = await api<Job>('/jobs', { method: 'POST', body: JSON.stringify({ name: runName.trim(), bug_ids: runIds, methods: runMethods }) })
      pendingJob.current = item.id
      setJobs(previous => [item, ...previous]); setPage('workbench'); setDialog(false)
    } catch (err) { setError(err instanceof Error ? err.message : 'Evaluation failed.') }
    finally { setRunning(false) }
  }

  async function jobAction(job: Job, action: 'cancel' | 'retry') {
    try {
      const item = await api<Job>(`/jobs/${job.id}/${action}`, { method: 'POST' })
      if (action === 'retry') {
        pendingJob.current = item.id
        setJobs(previous => [item, ...previous])
      } else setJobs(previous => previous.map(existing => existing.id === item.id ? item : existing))
    } catch (err) { setError(err instanceof Error ? err.message : 'Job action failed.') }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#" onClick={event => { event.preventDefault(); setPage('workbench') }}><span className="brand-icon"><Crosshair size={22} /></span>FaultLens<span className="version">v0.2</span></a>
      <div className="workspace-label">RESEARCH WORKSPACE</div>
      <nav aria-label="Main navigation">
        <button className={page === 'workbench' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('workbench')}><Code2 size={18} />Workbench</button>
        <button className={page === 'experiments' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('experiments')}><FlaskConical size={18} />Experiments<span className="nav-count">{entries.length}</span></button>
        <button className={page === 'research' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('research')}><Beaker size={18} />Research</button>
        <button className={page === 'prompts' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('prompts')}><FileCode2 size={18} />Prompt lab</button>
        <button className={page === 'methodology' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('methodology')}><BookOpen size={18} />Methodology</button>
      </nav>
      <div className="sidebar-bottom">
        <div className="dataset-card"><span className="eyebrow"><Database size={13} />ACTIVE DATASET</span><strong>{page === 'research' ? 'Archived research' : 'Curated Python bugs'}</strong><span>{page === 'research' ? 'Recorded study outcomes' : '6 cases · 30 executable tests'}</span><span className="small-pill">{page === 'research' ? 'Offline results' : 'Educational fixtures'}</span></div>
        <a className="github-link" href="https://github.com/srikarvaddela/faultlens" target="_blank" rel="noreferrer"><GitBranch size={17} />Project on GitHub<ExternalLink size={13} /></a>
        <div className="profile"><div className="avatar">SV</div><div><strong>Srikar Vaddela</strong><span>Personal workspace</span></div></div>
      </div>
    </aside>

    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">Workspace<ChevronRight size={13} /><span>{page === 'workbench' ? 'Fault localization' : page === 'experiments' ? 'Experiment history' : page === 'research' ? 'Archived research' : page === 'prompts' ? 'Prompt preparation' : 'Evaluation methodology'}</span></div><div className="topbar-right"><span className={`connection ${ready ? '' : 'offline'}`}><i />{ready ? 'API connected' : 'Connecting'}</span><a aria-label="Read methodology" href="#methodology" onClick={event => { event.preventDefault(); setPage('methodology') }}><CircleHelp size={18} /></a></div></header>
      <main>
        <div className="page-heading"><div><div className="eyebrow heading-eyebrow">LESS GUESSWORK. MORE EVIDENCE.</div><h1>{page === 'workbench' ? 'The debugging workbench' : page === 'experiments' ? 'Every experiment, accounted for.' : page === 'research' ? 'Your research, inspectable.' : page === 'prompts' ? 'Make the inputs reproducible.' : 'Know what you’re measuring.'}</h1><p>{page === 'workbench' ? 'Trace a failure. Rank the evidence. Compare what works.' : page === 'experiments' ? 'Revisit reproducible runs and export the evidence behind each result.' : page === 'research' ? 'Explore recorded outcomes without running new inference.' : page === 'prompts' ? 'Version the prompt. Freeze the evidence. Inspect what will be sent.' : 'Transparent baselines, explicit assumptions, and results you can inspect.'}</p></div>{page !== 'research' && page !== 'prompts' && <button className="button primary" disabled={!ready || running} onClick={() => setDialog(true)}><Play size={15} fill="currentColor" />New experiment</button>}</div>

        {error && <div className="error-banner" role="alert"><XCircle size={17} /><span>{error}</span>{!ready && <button onClick={() => void load()}>Retry connection</button>}<button aria-label="Dismiss error" onClick={() => setError('')}><X size={16} /></button></div>}
        {!ready && !error && <div className="loading-state"><LoaderCircle className="spin" size={20} />Connecting to the evaluation service…</div>}
        {ready && jobs.length > 0 && page !== 'methodology' && page !== 'research' && page !== 'prompts' && <section className="panel jobs-panel" aria-label="Evaluation jobs"><div className="panel-title"><h2>Evaluation jobs</h2><span className="muted">Runs continue when you leave this page</span></div>{jobs.slice(0, page === 'experiments' ? 20 : 3).map(job => <div className="job-row" data-job-id={job.id} key={job.id}><div><strong>{job.name}</strong><span>{job.status === 'queued' ? 'Waiting for worker' : job.status === 'running' ? `${job.progress} / ${job.total} ${job.unit ?? 'cases'} evaluated` : job.status === 'completed' ? `${job.total} ${job.unit ?? 'cases'} evaluated` : job.last_error ?? 'Cancelled before publication'} · attempt {job.attempts} / {job.max_attempts}</span></div><span className={`job-status ${job.status}`}>{job.cancel_requested && job.status === 'running' ? 'cancelling' : job.status}</span>{(job.status === 'queued' || job.status === 'running') && <button className="text-button" disabled={job.cancel_requested} onClick={() => void jobAction(job, 'cancel')}>Cancel</button>}{(job.status === 'failed' || job.status === 'cancelled') && <button className="text-button" onClick={() => void jobAction(job, 'retry')}>Retry</button>}{job.experiment_id && <button className="text-button" disabled={loadingExperiment} onClick={() => void openExperiment(job.experiment_id!)}>View results<ArrowRight size={13} /></button>}</div>)}</section>}

        {ready && page === 'research' && <Research />}
        {ready && page === 'prompts' && <PromptLab bugs={bugs} />}
        {ready && page === 'workbench' && <>
          <div className="metrics">
            <Metric label="BENCHMARK CASES" value={summary ? String(summary.cases) : '6'} detail={summary ? 'Evaluated in this experiment' : 'Original, inspectable Python bugs'} icon={<Layers3 size={19} />} />
            <Metric label="TOP-1 ACCURACY" value={summary ? pct(summary.top1) : '—'} detail="Conservative scoring for ties" icon={<Crosshair size={19} />} />
            <Metric label="MEAN RECIPROCAL RANK" value={summary ? summary.mrr.toFixed(3) : '—'} detail={`${methodNames[method]} · rank of the known fault`} icon={<Beaker size={19} />} />
            <Metric label="EVALUATION TIME" value={summary ? `${(summary.total_duration_ms / 1000).toFixed(2)}s` : '—'} detail="Measured execution + ranking time" icon={<Clock3 size={19} />} />
          </div>
          <div className="experiment-strip"><span className="experiment-indicator" /><strong>{experiment ? experiment.name : 'Ready for your first experiment'}</strong><span className="strip-detail">{experiment ? date(experiment.created_at) : 'Run both baselines on the same test cases'}</span>{experiment && <a className="text-button" href={`/api/experiments/${experiment.id}/export`}><ArrowDownToLine size={14} />Export JSON</a>}</div>

          <div className="workbench-grid">
            <section className="panel bug-panel"><div className="panel-title"><h2>Bug explorer</h2><span className="count-badge">{bugs.length}</span></div><label className="search-box"><Search size={16} /><input aria-label="Search bugs" placeholder="Search cases…" value={query} onChange={event => setQuery(event.target.value)} /><kbd>/</kbd></label><div className="bug-list">{visibleBugs.map(item => <button key={item.id} className={`bug-item ${selectedId === item.id ? 'selected' : ''}`} onClick={() => selectBug(item.id)}><div><span className="mono muted">{item.id}</span><span className="bug-type">{item.category}</span></div><strong>{item.title}</strong><span className="bug-module"><FileCode2 size={12} />{item.module}</span>{selectedId === item.id && <ChevronRight className="selected-chevron" size={15} />}</button>)}{!visibleBugs.length && <div className="empty-small">No matching bugs.</div>}</div><div className="panel-foot"><ShieldCheck size={13} />Trusted, packaged fixtures only</div></section>

            {bug && <section className="panel code-panel"><div className="code-heading"><div><div className="case-label"><span className="mono">{bug.id}</span><span className="small-pill">{bug.difficulty}</span></div><h2>{bug.title}</h2><p>{bug.description}</p></div></div><div className="file-tab"><FileCode2 size={15} /><span className="mono">{bug.module}</span><span className="language-tag">Python</span></div><div className="code-view" aria-label="Source code">{bug.source.trimEnd().split('\n').map((line, index) => {
              const number = index + 1
              const suspicious = result?.candidates[0]?.line === number
              return <div key={number} id={`line-${number}`} className={`code-line ${focusedLine === number ? 'focused' : ''} ${suspicious ? 'suspicious' : ''} ${reveal && bug.fault_line === number ? 'ground-truth' : ''}`}><span className="line-marker">{reveal && bug.fault_line === number ? <Crosshair size={12} /> : suspicious ? '●' : ''}</span><span className="line-number">{number}</span><code><CodeText text={line || ' '} /></code></div>
            })}</div><div className="code-legend"><span><i className="legend-dot" />Highest score</span><button className="text-button" onClick={() => setReveal(value => !value)}><Crosshair size={13} />{reveal ? 'Hide' : 'Reveal'} known fault</button></div>{reveal && <div className="truth-note"><strong>Known fault: line {bug.fault_line}</strong><p>{bug.fix_explanation}</p><span>Ground truth is used for scoring only; it is excluded from ranking inputs.</span></div>}<TestEvidence bug={bug} result={result} /></section>}

            <section className="panel ranking-panel"><div className="panel-title"><h2>Suspicious lines</h2><SlidersHorizontal size={16} /></div><div className="method-switch" role="group" aria-label="Ranking method">{(['ochiai', 'tarantula'] as Method[]).map(item => <button key={item} className={method === item ? 'selected' : ''} onClick={() => { setMethod(item); setFocusedLine(null) }}>{methodNames[item]}</button>)}</div>{result ? <><div className="ranking-caption">Higher score = stronger association<br />with failing tests.</div><div className="candidate-list">{result.candidates.map((candidate, index) => <button className={`candidate ${focusedLine === candidate.line ? 'focused' : ''}`} key={candidate.line} onClick={() => setFocusedLine(candidate.line)}><div className="candidate-top"><span className={`candidate-order ${index === 0 ? 'first' : ''}`}>{index + 1}</span><strong>Line {candidate.line}</strong><span className="mono score">{candidate.score.toFixed(3)}</span></div><div className="score-track"><div style={{ width: `${candidate.score * 100}%` }} /></div><div className="candidate-evidence"><span>{candidate.failed_covered} failing</span><span>{candidate.passed_covered} passing</span><span>rank {candidate.rank}</span></div></button>)}</div><div className="rank-summary"><span>Known fault rank</span><strong>{result.fault_rank ?? 'Uncovered'}</strong><span>Top-3 hit</span><strong className={result.top3 ? 'success-text' : ''}>{result.top3 ? 'Yes' : 'No'}</strong></div><div className="tie-note"><CircleHelp size={14} /><p>Equal scores share the worst rank in their group. Display order does not break ties.</p></div></> : <div className="ranking-empty"><div className="empty-icon"><Crosshair size={28} /></div><h3>{experiment ? 'No result for this selection' : 'Follow the evidence'}</h3><p>{experiment ? 'This bug or method was not included in the selected experiment.' : 'Run an experiment to see which lines are most associated with failing tests.'}</p><button className="text-button" onClick={() => setDialog(true)}>Run a comparison<ArrowRight size={14} /></button></div>}<div className="ranking-bottom"><ShieldCheck size={15} /><div><strong>Evidence, not certainty</strong><span>Scores are associations, not probabilities.</span></div></div></section>
          </div>
          <div className="bottom-note"><FlaskConical size={15} /><span>A small benchmark, honestly measured. Results here describe educational fixtures, not real-world accuracy.</span><button className="text-button" onClick={() => setPage('methodology')}>Read methodology<ArrowRight size={13} /></button></div>
        </>}

        {ready && page === 'experiments' && <section className="panel history-panel"><div className="panel-title"><h2>Saved runs</h2><span className="count-badge">{entries.length}</span></div>{entries.length ? <div className="table-wrap"><table><thead><tr><th>Experiment</th><th>Cases</th><th>Methods</th><th>Best Top-1</th><th>Created</th><th /></tr></thead><tbody>{entries.map(entry => <tr key={entry.id}><td><strong>{entry.name}</strong><span className="table-id mono">{entry.id.slice(0, 8)}</span></td><td>{entry.bug_ids.length}</td><td>{entry.methods.map(item => methodNames[item]).join(' + ')}</td><td>{pct(Math.max(...Object.values(entry.summary).map(item => item.top1)))}</td><td>{date(entry.created_at)}</td><td><button className="text-button" disabled={loadingExperiment} onClick={() => void openExperiment(entry.id)}>Open<ArrowRight size={14} /></button></td></tr>)}</tbody></table></div> : <div className="history-empty"><FlaskConical size={34} /><h3>Your experiment notebook starts here.</h3><p>Run a baseline comparison to save test evidence and rankings.</p><button className="button primary" onClick={() => setDialog(true)}>New experiment</button></div>}</section>}

        {ready && page === 'methodology' && <div className="methodology-grid"><section className="panel prose-panel"><span className="small-pill">EVALUATOR v1.1.0</span><h2>A reproducible starting point</h2><p>FaultLens runs 30 tests across six original Python fixtures. It collects line coverage per test, then ranks lines using only coverage and pass/fail outcomes. Known fault locations enter the scoring stage after ranking.</p><h3>Two transparent baselines</h3><div className="formula-card"><strong>Ochiai</strong><code>failed(line) / √(total_failed × covered(line))</code><p>A line covered mostly by failing tests receives a higher score.</p></div><div className="formula-card"><strong>Tarantula</strong><code>fail_rate(line) / (fail_rate(line) + pass_rate(line))</code><p>Coverage rates are normalized by the number of passing and failing tests.</p></div><h3>What the metrics mean</h3><p><strong>Top-1 / Top-3:</strong> fraction of bugs with the known fault ranked within the first one or three positions. <strong>MRR:</strong> average of 1 / fault rank. Higher is better. An uncovered fault contributes zero.</p><p><strong>Ties:</strong> all equally scored lines receive the worst position in their group. This prevents line-number ordering from inflating accuracy. A displayed score is rounded; scoring uses its full precision.</p><p><strong>Timing:</strong> wall-clock time for process startup, test execution, and ranking. It depends on your machine and is not an LLM latency measurement.</p></section><div><section className="panel prose-panel"><ShieldCheck size={23} /><h2>Boundaries matter</h2><ul><li>These are educational fixtures, not BugsInPy or production defects.</li><li>No live LLM runs or AI accuracy claims in this release.</li><li>Only packaged code executes. Child processes are not a security sandbox.</li><li>Ground-truth labels and fixes are never used by the ranking algorithms.</li><li>Jobs survive restarts with bounded retries. Saved runs include dataset and evaluator versions, source and evidence hashes, test outcomes, and exact scores.</li><li>The local demo has no authentication and must not be exposed as a shared service.</li></ul></section><section className="next-card"><span className="eyebrow">UP NEXT</span><h3>From baselines to AI evaluation</h3><p>Versioned prompts, model usage accounting, and leakage-controlled comparisons on a real-world benchmark.</p><a className="text-button" href="https://github.com/srikarvaddela/faultlens" target="_blank" rel="noreferrer">Follow the roadmap<ArrowRight size={14} /></a></section></div></div>}
        <footer>FaultLens <span>Built to make debugging measurable.</span><span className="footer-version">Curated dataset v1.0.0</span></footer>
      </main>
    </div>

    <dialog ref={modalRef} className="run-dialog" onCancel={event => { event.preventDefault(); if (!running) setDialog(false) }} onClose={() => setDialog(false)}><form onSubmit={event => { event.preventDefault(); void run() }}><div className="dialog-header"><div className="empty-icon"><FlaskConical size={22} /></div><button type="button" className="icon-button" aria-label="Close experiment dialog" disabled={running} onClick={() => setDialog(false)}><X size={20} /></button></div><h2>Start an experiment</h2><p>Run real tests and compare rankings on the same evidence.</p><label className="field-label" htmlFor="experiment-name">Experiment name</label><input autoFocus id="experiment-name" className="text-input" maxLength={100} value={runName} disabled={running} onChange={event => setRunName(event.target.value)} required /><div className="field-label selection-title">Cases<span>{runIds.length} selected</span><button type="button" disabled={running} onClick={() => setRunIds(runIds.length === bugs.length ? [] : bugs.map(item => item.id))}>{runIds.length === bugs.length ? 'Clear' : 'Select all'}</button></div><div className="dialog-case-list">{bugs.map(item => <label key={item.id}><input type="checkbox" checked={runIds.includes(item.id)} disabled={running} onChange={event => setRunIds(previous => event.target.checked ? [...previous, item.id] : previous.filter(id => id !== item.id))} /><span className="mono">{item.id}</span><span>{item.title}</span></label>)}</div><div className="field-label">Methods</div><div className="method-options">{catalog?.methods.map(item => <label className={runMethods.includes(item.id) ? 'checked' : ''} key={item.id}><input type="checkbox" checked={runMethods.includes(item.id)} disabled={running} onChange={event => setRunMethods(previous => event.target.checked ? [...previous, item.id] : previous.filter(id => id !== item.id))} /><strong>{item.name}</strong><span>{item.description}</span></label>)}</div>{error && <div className="dialog-error" role="alert">{error}</div>}<div className="dialog-footer"><span><Database size={13} />Results saved locally</span><button type="submit" className="button primary" disabled={running || !runIds.length || !runMethods.length || !runName.trim()}>{running ? <LoaderCircle className="spin" size={15} /> : <Play size={15} fill="currentColor" />}{running ? 'Running tests…' : 'Run experiment'}</button></div></form></dialog>
  </div>
}

function Metric({ label, value, detail, icon }: { label: string; value: string; detail: string; icon: React.ReactNode }) {
  return <div className="metric"><div className="metric-label">{label}{icon}</div><strong>{value}</strong><span>{detail}</span></div>
}

function TestEvidence({ bug, result }: { bug: Bug; result?: Result }) {
  const [openTest, setOpenTest] = useState<string | null>(null)
  const failed = result?.tests.filter(test => !test.passed).length
  return <div className="tests-section"><div className="tests-heading"><h3><Terminal size={15} />Test evidence</h3>{result ? <span><span className="fail-count">{failed} failing</span><span className="pass-count">{result.tests.length - failed!} passing</span></span> : <span>{bug.tests.length} tests · not run yet</span>}</div><div>{bug.tests.map(test => {
    const outcome = result?.tests.find(item => item.name === test.name)
    const open = openTest === `${bug.id}/${test.name}`
    return <div className="test-item" key={test.name}><button className="test-row" aria-expanded={open} onClick={() => setOpenTest(open ? null : `${bug.id}/${test.name}`)}>{outcome ? outcome.passed ? <CheckCircle2 className="success-text" size={14} /> : <XCircle className="failure-text" size={14} /> : <span className="test-pending" />}<span className="mono">test_{test.name}</span><span className={`test-status ${outcome?.passed ? 'passed' : outcome ? 'failed' : ''}`}>{outcome ? outcome.passed ? 'PASS' : 'FAIL' : 'READY'}</span>{open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}</button>{open && <div className="test-details"><div><span>Arguments</span><code>{json(test.args)}</code></div><div><span>Expected</span><code>{json(test.expected)}</code></div>{outcome && <><div><span>{outcome.error ? 'Exception' : 'Actual'}</span><code className={!outcome.passed ? 'failure-text' : ''}>{outcome.error || json(outcome.actual)}</code></div><div><span>Covered lines</span><code>{outcome.covered_lines.join(', ')}</code></div></>}</div>}</div>
  })}</div></div>
}
