import { expect, test } from 'claude-code/testing'

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

test('band draws on the terminal with no task and a Start button', async $ => {
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /No active task/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Tokens In/ })).toBeDefined()
  expect(await ui.find({ key: 'next' })).toBeDefined()
  await ui.unmount()
})

test('Start button fills the prompt with the spec skill, keeping the draft', async ($, on) => {
  let filled = ''
  on('prompt.read', () => ({ value: { text: 'fix login ', cursor: 10 } }) as never)
  on('prompt.fill', ($, e) => {
    filled = e.text
    return { isFilled: true, box: { text: e.text, cursor: e.text.length } } as never
  })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  await ui.press({ key: 'next' })
  expect(filled).toBe('/agent-skills:spec fix login ')
  await ui.unmount()
})

test('band yields to a survey', async ($, on) => {
  on('ui.render', { component: 'AbovePrompt' }, ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text key="engine">engine</Text>
  })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal', props: { ...BAND.props, hasSurvey: true } })
  expect(await ui.find({ key: 'next' })).toBeUndefined()
  await ui.unmount()
})
