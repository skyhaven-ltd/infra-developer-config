import type { Phase, Step, Track } from '../types'

export const FULL_CYCLE: Phase[] = ['spec', 'plan', 'build', 'review', 'ship']

const ALL_PHASES: Phase[] = ['spec', 'plan', 'test', 'build', 'review', 'ship']

const MARKERS: Partial<Record<Phase, string>> = {
  spec: 'SPEC.md',
  plan: 'PLAN.md',
  review: 'REVIEW.md',
  ship: 'SHIP.md',
}

const TASK_NAME = /^\d{3} - .+/

const isPhase = (word: string): word is Phase => (ALL_PHASES as string[]).includes(word)

export type Cycle = { kind: string | null; branches: string[]; phases: Phase[]; ticked: Phase[] }

export function parseCycle(text: string): Cycle {
  let kind: string | null = null
  const branches: string[] = []
  const phases: Phase[] = []
  const ticked: Phase[] = []

  for (const line of text.split(/\r?\n/)) {
    const type = /^\s*type\s*:\s*(.+?)\s*$/i.exec(line)
    if (type?.[1]) {
      kind = type[1].toLowerCase()
      continue
    }

    const branch = /^\s*branch\s*:\s*`?([^`\s]+)`?\s*$/i.exec(line)
    if (branch?.[1]) {
      branches.push(branch[1])
      continue
    }

    const list = /^\s*phases\s*:\s*(.+)$/i.exec(line)
    if (list?.[1]) {
      for (const word of list[1].split(/[,\s→>]+/)) {
        const phase = word.trim().toLowerCase().replace(/^\//, '')
        if (isPhase(phase) && !phases.includes(phase)) phases.push(phase)
      }
      continue
    }

    const item = /^\s*[-*]\s*\[([ xX])\]\s*\/?([a-zA-Z]+)/.exec(line)
    const phase = item?.[2]?.toLowerCase()
    if (item && phase && isPhase(phase)) {
      if (!phases.includes(phase)) phases.push(phase)
      if (item[1] !== ' ' && !ticked.includes(phase)) ticked.push(phase)
    }
  }

  return { kind, branches, phases, ticked }
}

export function parseTodo(text: string): { done: number; total: number } {
  let done = 0
  let total = 0

  for (const line of text.split(/\r?\n/)) {
    const item = /^\s*[-*]\s*\[([ xX])\]/.exec(line)
    if (!item) continue
    total += 1
    if (item[1] !== ' ') done += 1
  }

  return { done, total }
}

export type Folder = { files: string[]; cycle: string | null; todo: string | null }

export function trackFromFolder(task: string, folder: Folder): Track {
  const cycle = folder.cycle === null ? null : parseCycle(folder.cycle)
  const phases = cycle && cycle.phases.length > 0 ? cycle.phases : FULL_CYCLE
  const files = new Set(folder.files.map(name => name.toUpperCase()))
  const todo = folder.todo === null ? null : parseTodo(folder.todo)

  const isDone = (phase: Phase): boolean => {
    if (cycle?.ticked.includes(phase)) return true
    const marker = MARKERS[phase]
    if (marker && files.has(marker.toUpperCase())) return true
    return phase === 'build' && todo !== null && todo.total > 0 && todo.done === todo.total
  }

  const done = phases.map(isDone)
  const current = done.lastIndexOf(true) + 1

  const steps: Step[] = phases.map((phase, i) => ({
    phase,
    state: done[i] ? 'done' : i < current ? 'skipped' : i === current ? 'current' : 'pending',
    progress: phase === 'build' && todo !== null && todo.total > 0 ? todo : null,
  }))

  return {
    task,
    kind: cycle?.kind ?? null,
    steps,
    next: phases[current] ?? null,
    then: phases[current + 1] ?? null,
  }
}

export type GitState = { isDirty: boolean; ahead: number }

export function trackFromGit(git: GitState): Track | null {
  const current = git.isDirty ? 0 : git.ahead > 0 ? 1 : -1
  if (current < 0) return null

  const phases: Phase[] = ['build', 'review', 'ship']

  return {
    task: null,
    kind: 'small',
    steps: phases.map((phase, i) => ({
      phase,
      state: i < current ? 'done' : i === current ? 'current' : 'pending',
      progress: null,
    })),
    next: phases[current] ?? null,
    then: phases[current + 1] ?? null,
  }
}

export type TaskEntry = { name: string; branches: string[] }

export function pickTask(entries: TaskEntry[], branch: string | null): string | null {
  if (branch === null) return null
  const wanted = branch.toLowerCase()
  const tasks = entries.filter(
    entry => TASK_NAME.test(entry.name) && entry.branches.some(bound => bound.toLowerCase() === wanted),
  )
  tasks.sort((a, b) => b.name.localeCompare(a.name))
  return tasks[0]?.name ?? null
}

export function compact(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${Math.round(n / 1e3)}k`
  return String(Math.round(n))
}

export function money(usd: number, gbpPerUsd: number | null): string {
  return gbpPerUsd === null ? `$${usd.toFixed(2)}` : `£${(usd * gbpPerUsd).toFixed(2)}`
}

export const title = (phase: Phase): string => phase[0]!.toUpperCase() + phase.slice(1)
