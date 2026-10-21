import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, Timer } from 'claude-code'

import type { Context, Cost, Crew, Radar, Step, Track, Where } from '../types'
import { compact, elapsed, money, parseCycle, pickTask, title, trackFromFolder, trackFromGit } from './phase'
import type { GitState } from './phase'

const where = atom({ plugin: 'lifecycle-band', key: 'where' } as const, { track: null, branch: null } as Where)
const context = atom({ plugin: 'lifecycle-band', key: 'context' } as const, null as Context | null)
const cost = atom({ plugin: 'lifecycle-band', key: 'cost' } as const, null as Cost | null)
const radar = atom({ plugin: 'lifecycle-band', key: 'radar' } as const, { frame: 0, now: 0, crew: [] } as Radar)

const GH = {
  fg: '#e6edf3',
  muted: '#8b949e',
  subtle: '#6e7681',
  accent: '#58a6ff',
  success: '#3fb950',
  attention: '#d29922',
  done: '#a371f7',
  danger: '#f85149',
}

const SPIN = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
const CREW_COLORS = [GH.accent, GH.done, GH.success, GH.attention, '#f778ba', '#39c5cf']
const SPIN_MS = 120
const LINGER_MS = 6_000
const ACTIVE = new Set(['pending', 'running', 'waiting'])
const FAILED = new Set(['failed', 'killed'])
const LABEL_WIDTH = 9

const RATE_URL = 'https://api.frankfurter.dev/v1/latest?base=USD&symbols=GBP'
const POLL_MS = 15_000
const REFRESH_TOOLS = new Set(['Write', 'Edit', 'NotebookEdit', 'Bash', 'PowerShell', 'EnterWorktree', 'ExitWorktree'])

async function git($: EngineInterface, cwd: string, args: string[]): Promise<string | null> {
  try {
    const { exitCode, stdout } = await $.process.run(['git', ...args], { cwd, timeoutMs: 5_000 })
    return exitCode === 0 ? stdout.trim() : null
  } catch {
    return null
  }
}

async function isDir($: EngineInterface, path: string): Promise<boolean> {
  try {
    return (await $.fs.stat(path, { resolve: true })).kind === 'dir'
  } catch {
    return false
  }
}

async function agentsDir($: EngineInterface, cwd: string, top: string | null): Promise<string | null> {
  const repo = await $.session.repo().catch(() => null)
  const roots = [top, repo?.root ?? null, cwd].filter((root): root is string => root !== null)

  for (const root of new Set(roots)) {
    const dir = `${root}/.agents`
    if (await isDir($, dir)) return dir
  }

  return null
}

async function folderTrack($: EngineInterface, dir: string, branch: string | null): Promise<Track | null> {
  if (branch === null) return null
  const entries = await $.fs.list(dir)
  const folders = await Promise.all(
    entries.map(async entry => {
      const path = `${dir}/${entry.name}`
      if (entry.kind !== 'dir' && !(entry.isLink && (await isDir($, path)))) return null
      const files = (await $.fs.list(path)).filter(file => file.kind === 'file').map(file => file.name)
      const text = async (wanted: string) => {
        const file = files.find(name => name.toUpperCase() === wanted)
        return file ? $.fs.read(`${path}/${file}`).catch(() => null) : null
      }
      const cycle = await text('CYCLE.MD')
      return { name: entry.name, files, cycle, text, branches: cycle === null ? [] : parseCycle(cycle).branches }
    }),
  )
  const present = folders.filter(folder => folder !== null)
  const name = pickTask(present, branch)
  const folder = present.find(candidate => candidate.name === name)
  if (!name || !folder) return null

  return trackFromFolder(name, {
    files: folder.files,
    cycle: folder.cycle,
    build: await folder.text('BUILD.MD'),
    todo: await folder.text('TODO.MD'),
  })
}

async function gitState($: EngineInterface, cwd: string): Promise<GitState> {
  const status = await git($, cwd, ['status', '--porcelain'])
  const ahead =
    (await git($, cwd, ['rev-list', '--count', '@{upstream}..HEAD'])) ??
    (await git($, cwd, ['rev-list', '--count', 'origin/HEAD..HEAD'])) ??
    '0'
  return { isDirty: !!status, ahead: Number(ahead) || 0 }
}

async function locate($: EngineInterface): Promise<Where> {
  const cwd = await $.session.cwd()
  const top = await git($, cwd, ['rev-parse', '--show-toplevel'])
  const branch = top === null ? null : await git($, cwd, ['branch', '--show-current'])
  const dir = await agentsDir($, cwd, top)
  const fromFolder = dir === null ? null : await folderTrack($, dir, branch || null).catch(() => null)
  const track = fromFolder ?? (top === null ? null : trackFromGit(await gitState($, cwd)))

  return { track, branch: branch || null }
}

async function gbpPerUsd($: EngineInterface): Promise<number | null> {
  const day = new Date(await $.clock.now()).toISOString().slice(0, 10)
  const cached = (await $.store.get('rate')) as { day: string; gbpPerUsd: number } | undefined
  if (cached?.day === day) return cached.gbpPerUsd

  try {
    const { ok, text } = await $.http.fetch(RATE_URL)
    const rate = ok ? (JSON.parse(text) as { rates?: { GBP?: number } }).rates?.GBP : undefined
    if (typeof rate === 'number' && rate > 0) {
      await $.store.set('rate', { day, gbpPerUsd: rate })
      return rate
    }
  } catch {}

  return cached?.gbpPerUsd ?? null
}

let isRefreshing = false
let isQueued = false
let poll: Timer | undefined

async function refresh($: EngineInterface): Promise<void> {
  if (isRefreshing) {
    isQueued = true
    return
  }
  isRefreshing = true
  try {
    const usage = await $.session.usage()
    const { tokens, percent } = usage.context
    if (tokens !== undefined) await update($, context, () => ({ tokens, percent: percent ?? null }))
    const usd = usage.cost?.usd
    if (usd !== undefined) {
      const rate = await gbpPerUsd($)
      await update($, cost, () => ({ usd, gbpPerUsd: rate }))
    }
  } catch {}
  try {
    const next = await locate($)
    await update($, where, () => next)
  } catch {
  } finally {
    isRefreshing = false
    if (isQueued) {
      isQueued = false
      void refresh($)
    }
  }
}

const started = new Map<string, number>()
const finished = new Map<string, { at: number; state: Crew['state'] }>()
const toolCounts = new Map<string, number>()
let frame = 0
let spinner: Timer | undefined
let isSweeping = false

function hue(type: string): string {
  let sum = 0
  for (const char of type) sum = (sum * 31 + char.charCodeAt(0)) >>> 0
  return CREW_COLORS[sum % CREW_COLORS.length]!
}

async function sweep($: EngineInterface): Promise<void> {
  if (isSweeping) return
  isSweeping = true
  try {
    const now = await $.clock.now()
    const agents = await $.agent.list().catch(() => [])
    const crew: Crew[] = []
    for (const agent of agents) {
      if (agent.status === 'idle') continue
      if (ACTIVE.has(agent.status)) {
        if (!started.has(agent.id)) started.set(agent.id, now)
      } else if (started.has(agent.id) && !finished.has(agent.id)) {
        const state = FAILED.has(agent.status) ? 'failed' : 'done'
        finished.set(agent.id, { at: now, state })
        const took = elapsed(now - started.get(agent.id)!)
        const verdict = state === 'done' ? '✓' : '✗'
        $.ui.toast(`${verdict} ${agent.type} ${state} in ${took} · ${toolCounts.get(agent.id) ?? 0} tools · ${agent.description}`)
      }
      const startedAt = started.get(agent.id)
      if (startedAt === undefined) continue
      const end = finished.get(agent.id)
      if (end && now - end.at > LINGER_MS) continue
      crew.push({
        id: agent.id,
        type: agent.type,
        description: agent.description,
        state: end?.state ?? 'running',
        startedAt,
        endedAt: end?.at ?? null,
        tools: toolCounts.get(agent.id) ?? 0,
      })
    }
    frame += 1
    await update($, radar, () => ({ frame, now, crew }))
    if (crew.length === 0) {
      spinner?.cancel()
      spinner = undefined
    }
  } catch {
  } finally {
    isSweeping = false
  }
}

function watch($: EngineInterface): void {
  spinner ??= $.clock.every(SPIN_MS, () => void sweep($))
  void sweep($)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    poll?.cancel()
    poll = $.clock.every(POLL_MS, () => void refresh($))
    void refresh($)
    watch($)
    return result
  })

  on('agent.spawn', async ($, e, next) => {
    const result = await next(e)
    if (result.agentId) started.set(result.agentId, await $.clock.now())
    watch($)
    return result
  })

  on('tool.call', async ($, e, next) => {
    if (e.agentId) toolCounts.set(e.agentId, (toolCounts.get(e.agentId) ?? 0) + 1)
    const result = await next(e)
    if (REFRESH_TOOLS.has(e.tool)) void refresh($)
    return result
  })

  on('turn.step', async function* ($, e, next) {
    const result = yield* next(e)
    void refresh($)
    return result
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)

    const { Box, Text } = $.ui.resolve(e)
    const { track, branch } = await read($, where)
    const window = await read($, context)
    const spent = await read($, cost)
    const crewRadar = await read($, radar)

    const glyph: Record<Step['state'], { mark: string; color: string }> = {
      done: { mark: '✓', color: GH.success },
      current: { mark: '●', color: GH.accent },
      skipped: { mark: '–', color: GH.subtle },
      pending: { mark: '○', color: GH.muted },
    }

    const step = (s: Step) => {
      const { mark, color } = glyph[s.state]
      const progress = s.progress && s.state !== 'done' ? ` ${s.progress.done}/${s.progress.total}` : ''
      return (
        <Text key={`step-${s.phase}`} color={color} bold={s.state === 'current'} dimColor={s.state === 'skipped'}>
          {`${mark} ${title(s.phase)}${progress}`}
        </Text>
      )
    }

    const label = track?.task ?? (track ? 'Small change' : 'No active task')
    const kind = track?.kind ? ` (${track.kind})` : ''
    const name = (text: string) => `${text}:`.padEnd(LABEL_WIDTH)

    const fixed = 4 + (branch || track ? 1 : 0)
    const room = Math.max(1, e.props.maxRows - fixed)
    const crew = crewRadar.crew
    const shown = crew.length <= room ? crew : crew.slice(0, room - 1)
    const hidden = crew.length - shown.length

    const member = (c: Crew, index: number) => {
      const color = hue(c.type)
      const spin = SPIN[(crewRadar.frame + index * 3) % SPIN.length]!
      const mark = c.state === 'running' ? spin : c.state === 'done' ? '✓' : '✗'
      const markColor = c.state === 'running' ? color : c.state === 'done' ? GH.success : GH.danger
      const took = elapsed((c.endedAt ?? crewRadar.now) - c.startedAt)
      return (
        <Text key={`agent-${c.id}`} wrap="truncate-end">
          <Text color={markColor}>{`${mark} `}</Text>
          <Text color={color} bold>
            {c.type}
          </Text>
          <Text color={GH.fg}>{`  ${c.description}`}</Text>
          <Text color={GH.muted}>{`  ${took} · ${c.tools} tools`}</Text>
        </Text>
      )
    }

    return (
      <Box
        key="band"
        paddingX={1}
        borderStyle="round"
        borderColor={GH.muted}
        alignSelf="flex-start"
        flexDirection="column"
      >
        <Box key="summary" flexDirection="row" flexWrap="wrap" columnGap={3}>
          <Box key="left" flexDirection="column">
            <Text color={GH.muted}>
              {name('Task')}
              <Text color={GH.fg} bold>
                {label}
              </Text>
              {kind}
            </Text>
            {branch ? (
              <Text color={GH.muted}>
                {name('Branch')}
                <Text color={GH.done}>{branch}</Text>
              </Text>
            ) : null}
          </Box>
          <Box key="right" flexDirection="column">
            {track ? (
              <Box flexDirection="row">
                <Text color={GH.muted}>{name('Stage')}</Text>
                <Box flexDirection="row" flexWrap="wrap" columnGap={2}>
                  {track.steps.map(step)}
                </Box>
              </Box>
            ) : null}
            <Text color={GH.muted}>
              {name('Context')}
              <Text color={GH.fg}>
                {window ? `${compact(window.tokens)}${window.percent === null ? '' : ` (${window.percent}%)`}` : '–'}
              </Text>
              {' | Cost: '}
              <Text color={GH.attention}>{spent ? money(spent.usd, spent.gbpPerUsd) : '–'}</Text>
            </Text>
          </Box>
        </Box>
        {crew.length > 0 ? (
          <Box flexDirection="row">
            <Text color={GH.muted}>{name('Agents')}</Text>
            <Box flexDirection="column">
              {shown.map(member)}
              {hidden > 0 ? (
                <Text key="agents-more" color={GH.muted}>
                  {`+${hidden} more`}
                </Text>
              ) : null}
            </Box>
          </Box>
        ) : null}
      </Box>
    )
  })
}
