import { describe, expect, test } from 'claude-code/testing'

import { compact, money, parseCycle, parseTodo, pickTask, trackFromFolder, trackFromGit } from '../hooks/phase'

const states = (track: ReturnType<typeof trackFromFolder>) => track.steps.map(s => `${s.phase}:${s.state}`)

describe('full cycle from marker files', () => {
  test('empty folder starts at spec', async () => {
    const track = trackFromFolder('001 - Empty', { files: [], cycle: null, todo: null })
    expect(track.next).toBe('spec')
    expect(track.then).toBe('plan')
  })

  test('SPEC.md means plan is next', async () => {
    const track = trackFromFolder('001 - A', { files: ['SPEC.md'], cycle: null, todo: null })
    expect(states(track)).toEqual(['spec:done', 'plan:current', 'build:pending', 'review:pending', 'ship:pending'])
  })

  test('open TODO items keep build current with progress', async () => {
    const todo = '- [x] one\n- [x] two\n- [ ] three\n'
    const track = trackFromFolder('002 - B', { files: ['SPEC.md', 'PLAN.md', 'TODO.md'], cycle: null, todo })
    expect(track.next).toBe('build')
    expect(track.steps[2]?.progress).toEqual({ done: 2, total: 3 })
  })

  test('all TODO items ticked moves to review', async () => {
    const todo = '- [x] one\r\n* [X] two\r\n'
    const track = trackFromFolder('002 - B', { files: ['SPEC.md', 'PLAN.md', 'TODO.md'], cycle: null, todo })
    expect(track.next).toBe('review')
    expect(track.then).toBe('ship')
  })

  test('REVIEW.md without a spec marks earlier phases skipped', async () => {
    const track = trackFromFolder('003 - C', { files: ['REVIEW.md'], cycle: null, todo: null })
    expect(states(track)).toEqual(['spec:skipped', 'plan:skipped', 'build:skipped', 'review:done', 'ship:current'])
  })

  test('SHIP.md finishes the cycle', async () => {
    const track = trackFromFolder('003 - C', { files: ['SPEC.md', 'PLAN.md', 'REVIEW.md', 'SHIP.md'], cycle: null, todo: '- [x] a' })
    expect(track.next).toBeNull()
    expect(track.then).toBeNull()
  })

  test('marker names match case-insensitively', async () => {
    const track = trackFromFolder('004 - D', { files: ['spec.md'], cycle: null, todo: null })
    expect(track.next).toBe('plan')
  })
})

describe('CYCLE.md picks the phases', () => {
  test('checklist form sets kind, phases and ticks', async () => {
    const cycle = parseCycle('type: Bug\n- [x] test\n- [ ] build\n- [ ] review\n- [ ] ship\n')
    expect(cycle).toEqual({ kind: 'bug', phases: ['test', 'build', 'review', 'ship'], ticked: ['test'] })
  })

  test('phases line form', async () => {
    expect(parseCycle('type: small\nphases: /build, /review → ship').phases).toEqual(['build', 'review', 'ship'])
  })

  test('bug cycle shows only its phases and the next one', async () => {
    const cycle = 'type: bug\n- [x] test\n- [ ] build\n- [ ] review\n- [ ] ship\n'
    const track = trackFromFolder('005 - Bug', { files: ['CYCLE.md'], cycle, todo: null })
    expect(track.kind).toBe('bug')
    expect(states(track)).toEqual(['test:done', 'build:current', 'review:pending', 'ship:pending'])
    expect(track.next).toBe('build')
  })

  test('marker file counts as done even when unticked', async () => {
    const cycle = 'phases: build, review, ship'
    const track = trackFromFolder('006 - E', { files: ['CYCLE.md', 'REVIEW.md'], cycle, todo: null })
    expect(track.next).toBe('ship')
  })

  test('CYCLE.md with no phases falls back to the full cycle', async () => {
    const track = trackFromFolder('007 - F', { files: ['CYCLE.md'], cycle: 'type: large', todo: null })
    expect(track.steps.length).toBe(5)
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
  test('newest folder wins, ignoring non-task names', async () => {
    const picked = pickTask([
      { name: '001 - Old', newest: 10 },
      { name: '002 - New', newest: 30 },
      { name: 'ADR', newest: 99 },
    ])
    expect(picked).toBe('002 - New')
  })

  test('tie goes to the higher number', async () => {
    expect(pickTask([{ name: '001 - A', newest: 5 }, { name: '002 - B', newest: 5 }])).toBe('002 - B')
  })

  test('no task folders', async () => {
    expect(pickTask([{ name: 'CONSTRAINTS.md', newest: 1 }])).toBeNull()
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
