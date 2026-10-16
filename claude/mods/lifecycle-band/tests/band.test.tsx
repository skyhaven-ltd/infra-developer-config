import { expect, mock, test } from 'claude-code/testing'

const BAND = {
  plugin: 'lifecycle-band',
  component: 'AbovePrompt',
  props: {
    hasSurvey: false,
    isWorking: false,
    maxRows: 10,
    bodyColumns: 160,
    scroll: { offset: 0, bodyRows: 9 },
    view: {},
  },
} as const

test('band draws on the terminal with no task and no button', async $ => {
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /No active task/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Context/ })).toBeDefined()
  expect(await ui.find({ type: 'Button' })).toBeUndefined()
  await ui.unmount()
})

test('usage sits on its own row under the task', async $ => {
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ key: 'band' }))?.props.flexDirection).toBe('column')
  await ui.unmount()
})

test('band sits in one rounded bubble', async $ => {
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  const boxes = await ui.findAll({ type: 'Box' })
  expect(boxes.filter(box => box.props.borderStyle !== undefined).map(box => box.props.borderStyle)).toEqual(['round'])
  await ui.unmount()
})

test('a model request refreshes the live context window and drops token totals', async ($, on) => {
  const clock = mock.clock(on)
  mock.store(on)
  on('session.usage', () => ({
    value: { startedAt: 0, context: { tokens: 45_000, window: 200_000, percent: 23 }, rateLimits: [], cost: { usd: 0.5 } },
  }) as never)
  on('turn.step', async function* () {
    return { turnId: 't', index: 0, answer: '', toolUses: [], stopReason: 'end_turn' } as never
  })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  for await (const _ of $.turn.step({ turnId: 't', index: 0, model: 'm', messageCount: 1 })) {
  }
  await clock.settle()
  expect(await ui.find({ type: 'Text', text: /Context: 45k \(23%\)/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Tokens/ })).toBeUndefined()
  await ui.unmount()
})

test('band yields to a survey', async ($, on) => {
  on('ui.render', { component: 'AbovePrompt' }, ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text key="engine">engine</Text>
  })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal', props: { ...BAND.props, hasSurvey: true } })
  expect(await ui.find({ type: 'Text', text: /No active task/ })).toBeUndefined()
  await ui.unmount()
})

test('band stacks labelled rows', async $ => {
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^Task: +No active task/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^Context: +– \| Cost: –/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Agents:/ })).toBeUndefined()
  await ui.unmount()
})

test('a subagent spins in the band while it runs, then ticks and leaves', async ($, on) => {
  const clock = mock.clock(on)
  let status = 'running'
  on('agent.spawn', () => ({ model: 'm', agentId: 'a1' }) as never)
  on('agent.list', () => ({ value: [{ id: 'a1', type: 'Explore', description: 'Find upload handlers', status }] }) as never)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  await $.agent.spawn({ prompt: 'look', description: 'Find upload handlers', subagentType: 'Explore' } as never)
  await clock.advance(65_000)
  expect(await ui.find({ type: 'Text', text: /Agents:/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] Explore  Find upload handlers  1:0\d · 0 tools$/ })).toBeDefined()
  status = 'completed'
  await clock.advance(200)
  expect(await ui.find({ type: 'Text', text: /^✓ Explore/ })).toBeDefined()
  await clock.advance(7_000)
  expect(await ui.find({ type: 'Text', text: /Agents:/ })).toBeUndefined()
  await ui.unmount()
})
