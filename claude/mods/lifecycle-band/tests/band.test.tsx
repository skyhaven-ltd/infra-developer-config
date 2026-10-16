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

test('band draws no border rows', async $ => {
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  const boxes = await ui.findAll({ type: 'Box' })
  expect(boxes.filter(box => box.props.borderStyle !== undefined)).toHaveLength(0)
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
