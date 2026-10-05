import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const windows = process.platform === 'win32'
const python = path.join(root, 'backend', '.venv', windows ? 'Scripts/python.exe' : 'bin/python')
const vite = path.join(root, 'frontend/node_modules/vite/bin/vite.js')
if (!existsSync(python) || !existsSync(vite)) {
  console.error('Install the backend environment and frontend dependencies first. See README.md.')
  process.exit(1)
}
const children = [
  spawn(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], { cwd: path.join(root, 'backend'), stdio: 'inherit' }),
  spawn(process.execPath, [vite, '--host', '127.0.0.1'], { cwd: path.join(root, 'frontend'), stdio: 'inherit' }),
]
let stopping = false
function stop(code = 0) {
  if (stopping) return
  stopping = true
  for (const child of children) child.kill()
  process.exitCode = code
}
for (const child of children) {
  child.on('error', error => { console.error(error.message); stop(1) })
  child.on('exit', code => { if (!stopping) stop(code ?? 1) })
}
process.on('SIGINT', () => stop())
process.on('SIGTERM', () => stop())
