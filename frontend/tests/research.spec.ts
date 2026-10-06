import { expect, test } from '@playwright/test'

test('archived research filters never treat missing leakage labels as clean', async ({ page }) => {
  const rows = [
    { project: 'example', bug_id: '1', source: 'real', operator: '', single: true, chain: false, fn_leak: null, chain_step1: null, chain_step2: null, chain_step3: null },
    { project: 'example', bug_id: '2', source: 'real', operator: '', single: false, chain: true, fn_leak: false, chain_step1: null, chain_step2: null, chain_step3: null },
  ]
  await page.route('**/api/research', route => route.fulfill({ json: [{ id: 'synthetic-study', name: 'Synthetic test study', run_count: 1, observation_count: 2 }] }))
  await page.route('**/api/research/synthetic-study', route => route.fulfill({ json: {
    id: 'synthetic-study', name: 'Synthetic test study', run_count: 1, observation_count: 2,
    notes: ['Recorded outcomes, not new inference.'],
    runs: [{ filename: 'results_test.csv', sha256: 'test-hash', model_label: 'Model unspecified', duplicate_of: null, rows }],
  } }))
  await page.goto('/')
  await expect(page.getByText('API connected')).toBeVisible()
  await page.getByRole('button', { name: 'Research', exact: true }).click()
  await expect(page.getByText('ARCHIVED RESULTS · NO NEW INFERENCE')).toBeVisible()
  await expect(page.getByTestId('research-pairs')).toHaveText('2')
  await page.getByLabel('Function leakage').selectOption('clean')
  await expect(page.getByTestId('research-pairs')).toHaveText('1')
  await expect(page.getByTestId('research-chain')).toHaveText('100.0%')
  await page.getByLabel('Function leakage').selectOption('unknown')
  await expect(page.getByTestId('research-pairs')).toHaveText('1')
  await expect(page.getByTestId('research-single')).toHaveText('100.0%')
})
