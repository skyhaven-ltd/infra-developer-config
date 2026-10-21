export type Phase = 'scope' | 'build' | 'review' | 'ship'

export type StepState = 'done' | 'current' | 'skipped' | 'pending'

export type Step = {
  phase: Phase
  state: StepState
  progress: { done: number; total: number } | null
}

export type Track = {
  task: string | null
  kind: string | null
  steps: Step[]
  next: Phase | null
  then: Phase | null
}

export type Where = { track: Track | null; branch: string | null }

export type Context = { tokens: number; percent: number | null }

export type Cost = { usd: number; gbpPerUsd: number | null }

export type Crew = {
  id: string
  type: string
  description: string
  state: 'running' | 'done' | 'failed'
  startedAt: number
  endedAt: number | null
  tools: number
}

export type Radar = { frame: number; now: number; crew: Crew[] }

declare module 'claude-code' {
  interface PluginState {
    'lifecycle-band': { where: Where; context: Context | null; cost: Cost | null; radar: Radar }
  }
}
