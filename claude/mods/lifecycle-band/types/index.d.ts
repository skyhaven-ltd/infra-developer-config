export type Phase = 'spec' | 'plan' | 'test' | 'build' | 'review' | 'ship'

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

export type Tokens = { input: number; output: number }

export type Cost = { usd: number; gbpPerUsd: number | null }

declare module 'claude-code' {
  interface PluginState {
    'lifecycle-band': { where: Where; tokens: Tokens; cost: Cost | null }
  }
}
