import { defineConfig, devices } from '@playwright/test'
import { existsSync } from 'node:fs'

const venvPython = process.platform === 'win32' ? '../backend/.venv/Scripts/python.exe' : '../backend/.venv/bin/python'
const python = existsSync(venvPython) ? venvPython : 'python'

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  use: { baseURL: 'http://127.0.0.1:5174', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } }],
  webServer: [
    { command: `"${python}" -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8010`, url: 'http://127.0.0.1:8010/api/health', env: { DATABASE_URL: 'sqlite:///e2e.db' }, reuseExistingServer: false },
    { command: `"${python}" -c "import sys; sys.path.insert(0, '../backend'); from app.worker import main; main()"`, wait: 1500, env: { DATABASE_URL: 'sqlite:///e2e.db' }, reuseExistingServer: false },
    { command: 'npm run dev -- --port 5174', url: 'http://127.0.0.1:5174', env: { FAULTLENS_API_URL: 'http://127.0.0.1:8010' }, reuseExistingServer: false },
  ],
})
