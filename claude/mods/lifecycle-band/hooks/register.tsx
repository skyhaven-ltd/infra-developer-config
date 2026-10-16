import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, Timer } from 'claude-code'

import type { Context, Cost, Step, Track, Where } from '../types'
import { compact, money, parseCycle, pickTask, title, trackFromFolder, trackFromGit } from './phase'
import type { GitState } from './phase'

const where = atom({ plugin: 'lifecycle-band', key: 'where' } as const, { track: null, branch: null } as Where)
const context = atom({ plugin: 'lifecycle-band', key: 'context' } as const, null as Context | null)
const cost = atom({ plugin: 'lifecycle-band', key: 'cost' } as const, null as Cost | null)

const GH = {
  fg: '#e6edf3',
  muted: '#8b949e',
  subtle: '#6e7681',
  accent: '#58a6ff',
  success: '#3fb950',
  attention: '#d29922',
  done: '#a371f7',
}

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

  return trackFromFolder(name, { files: folder.files, cycle: folder.cycle, todo: await folder.text('TODO.MD') })
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

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    poll?.cancel()
    poll = $.clock.every(POLL_MS, () => void refresh($))
    void refresh($)
    return result
  })

  on('tool.call', async ($, e, next) => {
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

    return (
      <Box key="band" paddingX={1} flexDirection="column">
        <Box flexDirection="row" flexWrap="wrap" columnGap={2} alignItems="center">
          <Text color={GH.fg} bold>
            {label}
            <Text color={GH.muted}>{kind}</Text>
            {branch ? <Text color={GH.done}>{`  ${branch}`}</Text> : null}
          </Text>
          {(track?.steps ?? []).map(step)}
          {track && !track.next ? (
            <Text key="shipped" color={GH.success} bold>
              Shipped
            </Text>
          ) : null}
        </Box>
        <Box flexDirection="row" columnGap={2}>
          <Text color={GH.muted}>
            Context:{' '}
            <Text color={GH.fg}>
              {window ? `${compact(window.tokens)}${window.percent === null ? '' : ` (${window.percent}%)`}` : '–'}
            </Text>
          </Text>
          <Text color={GH.muted}>
            Cost: <Text color={GH.attention}>{spent ? money(spent.usd, spent.gbpPerUsd) : '–'}</Text>
          </Text>
        </Box>
      </Box>
    )
  })
}
