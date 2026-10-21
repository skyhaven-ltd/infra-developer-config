import { describe, expect, test } from 'claude-code/testing'

import { compact, elapsed, money, parseCycle, parseTodo, pickTask, trackFromFolder, trackFromGit } from '../hooks/phase'

const states = (track: ReturnType<typeof trackFromFolder>) => track.steps.map(s => `${s.phase}:${s.state}`)

describe('full cycle from marker files', () => {
  test('empty folder starts at scope', async () => {
    const track = trackFromFolder('001 - Empty', { files: [], cycle: null, todo: null })
    expect(track.next).toBe('scope')
    expect(track.then).toBe('build')
  })

  test('SCOPE.md means build is next', async () => {
    const track = trackFromFolder('001 - A', { files: ['SCOPE.md'], cycle: null, todo: null })
    expect(states(track)).toEqual(['scope:done', 'build:current', 'review:pending', 'ship:pending'])
  })

  test('a legacy PLAN.md also finishes scope', async () => {
    const track = trackFromFolder('001 - A', { files: ['SPEC.md', 'PLAN.md'], cycle: null, todo: null })
    expect(track.next).toBe('build')
  })

  test('a legacy SPEC.md alone keeps scope current', async () => {
    const track = trackFromFolder('001 - A', { files: ['SPEC.md'], cycle: null, todo: null })
    expect(track.next).toBe('scope')
  })

  test('open BUILD items keep build current with progress', async () => {
    const build = '- [x] one\n- [x] two\n- [ ] three\n'
    const track = trackFromFolder('002 - B', { files: ['SCOPE.md', 'BUILD.md'], cycle: null, build, todo: null })
    expect(track.next).toBe('build')
    expect(track.steps[1]?.progress).toEqual({ done: 2, total: 3 })
  })

  test('BUILD.md wins over a legacy TODO.md', async () => {
    const track = trackFromFolder('002 - B', {
      files: ['SCOPE.md', 'BUILD.md', 'TODO.md'],
      cycle: null,
      build: '- [ ] one\n',
      todo: '- [x] one\n',
    })
    expect(track.next).toBe('build')
    expect(track.steps[1]?.progress).toEqual({ done: 0, total: 1 })
  })

  test('a legacy TODO.md counts when there is no BUILD.md', async () => {
    const todo = '- [x] one\r\n* [X] two\r\n'
    const track = trackFromFolder('002 - B', { files: ['SPEC.md', 'PLAN.md', 'TODO.md'], cycle: null, todo })
    expect(track.next).toBe('review')
    expect(track.then).toBe('ship')
  })

  test('all BUILD items ticked moves to review', async () => {
    const build = '- [x] one\r\n* [X] two\r\n'
    const track = trackFromFolder('002 - B', { files: ['SCOPE.md', 'BUILD.md'], cycle: null, build, todo: null })
    expect(track.next).toBe('review')
  })

  test('REVIEW.md without a scope marks earlier phases skipped', async () => {
    const track = trackFromFolder('003 - C', { files: ['REVIEW.md'], cycle: null, todo: null })
    expect(states(track)).toEqual(['scope:skipped', 'build:skipped', 'review:done', 'ship:current'])
  })

  test('SHIP.md finishes the cycle', async () => {
    const track = trackFromFolder('003 - C', {
      files: ['SCOPE.md', 'BUILD.md', 'REVIEW.md', 'SHIP.md'],
      cycle: null,
      build: '- [x] a',
      todo: null,
    })
    expect(track.next).toBeNull()
    expect(track.then).toBeNull()
  })

  test('marker names match case-insensitively', async () => {
    const track = trackFromFolder('004 - D', { files: ['scope.md'], cycle: null, todo: null })
    expect(track.next).toBe('build')
  })
})

describe('CYCLE.md picks the phases', () => {
  test('checklist form sets kind, phases and ticks', async () => {
    const cycle = parseCycle('type: Bug\n- [x] build\n- [ ] review\n- [ ] ship\n')
    expect(cycle).toEqual({ kind: 'bug', branches: [], phases: ['build', 'review', 'ship'], ticked: ['build'] })
  })

  test('legacy phase names fold into scope and build', async () => {
    const cycle = parseCycle('type: medium\n- [x] spec\n- [x] plan\n- [x] test\n- [ ] build\n- [ ] review\n')
    expect(cycle.phases).toEqual(['scope', 'build', 'review'])
    expect(cycle.ticked).toEqual(['scope'])
  })

  test('a folded phase is ticked only when every legacy item is', async () => {
    expect(parseCycle('- [x] spec\n- [ ] plan\n- [ ] build\n').ticked).toEqual([])
    expect(parseCycle('- [x] test\n- [x] build\n').ticked).toEqual(['build'])
  })

  test('branch lines bind the task to its branches', async () => {
    const cycle = parseCycle('type: small\nbranch: `patch/a-b`\r\nbranch: Minor/C\n- [ ] build\n')
    expect(cycle.branches).toEqual(['patch/a-b', 'Minor/C'])
    expect(cycle.phases).toEqual(['build'])
  })

  test('phases line form', async () => {
    expect(parseCycle('type: small\nphases: /build, /review → ship').phases).toEqual(['build', 'review', 'ship'])
    expect(parseCycle('phases: spec, plan, build').phases).toEqual(['scope', 'build'])
  })

  test('unknown words are not phases', async () => {
    expect(parseCycle('- [x] constructor\n- [ ] deploy\n- [ ] ship\n').phases).toEqual(['ship'])
  })

  test('bug cycle shows only its phases and the next one', async () => {
    const cycle = 'type: bug\n- [x] build\n- [ ] review\n- [ ] ship\n'
    const track = trackFromFolder('005 - Bug', { files: ['CYCLE.md'], cycle, todo: null })
    expect(track.kind).toBe('bug')
    expect(states(track)).toEqual(['build:done', 'review:current', 'ship:pending'])
    expect(track.next).toBe('review')
  })

  test('marker file counts as done even when unticked', async () => {
    const cycle = 'phases: build, review, ship'
    const track = trackFromFolder('006 - E', { files: ['CYCLE.md', 'REVIEW.md'], cycle, todo: null })
    expect(track.next).toBe('ship')
  })

  test('CYCLE.md with no phases falls back to the full cycle', async () => {
    const track = trackFromFolder('007 - F', { files: ['CYCLE.md'], cycle: 'type: large', todo: null })
    expect(track.steps.length).toBe(4)
    expect(track.kind).toBe('large')
  })
})

describe('git fallback with no task folder', () => {
  test('dirty tree is build', async () => {
    expect(trackFromGit({ isDirty: true, ahead: 0 })?.next).toBe('build')
  })

  test('clean with unpushed commits is review', async () => {
    const track = trackFromGit({ isDirty: false, ahead: 2 })
    expect(track?.next).toBe('review')
    expect(track?.steps[0]?.state).toBe('done')
  })

  test('clean and level is no task', async () => {
    expect(trackFromGit({ isDirty: false, ahead: 0 })).toBeNull()
  })
})

describe('helpers', () => {
  test('the task bound to the current branch wins over a newer one', async () => {
    const tasks = [
      { name: '001 - Mine', branches: ['patch/mine'] },
      { name: '002 - Other', branches: ['patch/other'] },
    ]
    expect(pickTask(tasks, 'patch/mine')).toBe('001 - Mine')
  })

  test('no task bound to the branch shows none', async () => {
    const tasks = [{ name: '001 - A', branches: ['patch/a'] }, { name: '002 - B', branches: [] }]
    expect(pickTask(tasks, 'minor/new-work')).toBeNull()
    expect(pickTask(tasks, null)).toBeNull()
  })

  test('branch matches case-insensitively and ignores non-task names', async () => {
    expect(pickTask([{ name: 'ADR', branches: ['patch/a'] }, { name: '003 - C', branches: ['Patch/A'] }], 'patch/a')).toBe(
      '003 - C',
    )
  })

  test('two tasks on one branch go to the higher number', async () => {
    const tasks = [
      { name: '007 - A', branches: ['patch/shared'] },
      { name: '008 - B', branches: ['patch/other', 'patch/shared'] },
    ]
    expect(pickTask(tasks, 'patch/shared')).toBe('008 - B')
  })

  test('todo counts', async () => {
    expect(parseTodo('# T\n- [ ] a\n- [x] b\ntext')).toEqual({ done: 1, total: 2 })
  })

  test('compact and money formats', async () => {
    expect(compact(47_200)).toBe('47k')
    expect(compact(1_250_000)).toBe('1.3M')
    expect(compact(787)).toBe('787')
    expect(money(0.29, 0.75491)).toBe('£0.22')
    expect(money(0.29, null)).toBe('$0.29')
  })
})

test('elapsed reads as minutes and seconds', () => {
  expect(elapsed(0)).toBe('0:00')
  expect(elapsed(65_400)).toBe('1:05')
})
