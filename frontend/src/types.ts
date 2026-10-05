export type Method = 'ochiai' | 'tarantula'
export type Bug = {
  id: string; title: string; module: string; category: string; difficulty: string
  description: string; function: string; fault_line: number; source: string; fix_explanation: string
  tests: { name: string; args: unknown[]; expected: unknown }[]
}
export type TestResult = {
  name: string; passed: boolean; expected: unknown; actual: unknown; error: string | null
  covered_lines: number[]; duration_ms: number
}
export type Candidate = { line: number; score: number; rank: number; failed_covered: number; passed_covered: number }
export type Result = {
  bug_id: string; title: string; method: Method; duration_ms: number
  tests: TestResult[]; candidates: Candidate[]; fault_rank: number | null
  top1: boolean; top3: boolean; reciprocal_rank: number; source_sha256: string; evidence_sha256: string
}
export type Summary = { cases: number; top1: number; top3: number; mrr: number; total_duration_ms: number }
export type Experiment = {
  id: string; name: string; created_at: string; bug_ids: string[]; methods: Method[]
  summary: Partial<Record<Method, Summary>>; results: Result[]; dataset: string; tie_policy: string
}
export type ExperimentEntry = Omit<Experiment, 'results' | 'dataset' | 'tie_policy'>
export type Catalog = { bugs: Bug[]; methods: { id: Method; name: string; description: string }[] }
