const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('typescript')

const source = fs.readFileSync(path.join(__dirname,
  '../src/app/(site)/rag/[id]/chat/components/chat-messages.tsx'), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
  },
}).outputText

// Run the real component's effects and scroll handler against controlled metrics.
// This checks scroll decisions; browser layout and painting require manual review.
function harness() {
  const refs = [], dependencies = []
  let refIndex, effectIndex, effects, tree
  const container = {
    scrollHeight: 1200, clientHeight: 400, scrollTop: 0, calls: 0,
    scrollTo({ top }) {
      this.scrollTop = Math.max(0, top - this.clientHeight)
      this.calls++
    },
  }
  const sandbox = {
    exports: {},
    require(id) {
      if (id === 'react') return {
        useRef(value) { return refs[refIndex++] ??= { current: value } },
        useEffect(effect, deps) {
          const previous = dependencies[effectIndex]
          if (!previous || deps.some((value, i) => !Object.is(value, previous[i]))) {
            effects.push(effect)
          }
          dependencies[effectIndex++] = deps
        },
      }
      if (id === 'react/jsx-runtime') {
        const jsx = (type, props) => ({ type, props })
        return { jsx, jsxs: jsx }
      }
      if (id === 'framer-motion') return { motion: { div: 'div' } }
      return new Proxy({}, { get: (_, name) => name })
    },
  }
  vm.runInNewContext(compiled, sandbox)
  const props = {
    kb: { title: 'Fixture' }, isLoading: false,
    conversation: { id: 'first', messages: [{ id: 'message', role: 'user', content: 'Hi' }] },
  }
  return {
    container,
    render(changes = {}) {
      Object.assign(props, changes)
      refIndex = effectIndex = 0
      effects = []
      if (tree?.props.ref) tree.props.ref.current = null
      tree = sandbox.exports.ChatMessages(props)
      if (tree.props.ref) tree.props.ref.current = container
      effects.forEach((effect) => effect())
    },
    scroll(top) {
      container.scrollTop = top
      tree.props.onScroll({ currentTarget: container })
    },
  }
}

test('stream follows bottom, preserves history, and resumes at the proximity threshold', () => {
  const h = harness()
  h.render()
  assert.equal(h.container.scrollTop, 800)
  h.scroll(200)
  h.container.scrollHeight = 1600
  h.render({ streamingMessage: 'First token', isStreaming: true })
  assert.equal(h.container.scrollTop, 200)
  assert.equal(h.container.calls, 1)
  h.scroll(1103) // 97px away: continue reading history.
  h.render({ streamingMessage: 'Second token' })
  assert.equal(h.container.calls, 1)
  h.scroll(1104) // 96px away: resume following.
  h.container.scrollHeight = 1800
  h.render({ streamingMessage: 'Third token' })
  assert.equal(h.container.scrollTop, 1400)
})

test('switching conversations resets history scroll tracking', () => {
  const h = harness()
  h.render()
  h.scroll(100)
  h.render({ conversation: { id: 'second', messages: [{ id: 'new', role: 'user', content: 'New' }] } })
  assert.equal(h.container.scrollTop, 800)
})

test('first streaming content follows after an empty conversation', () => {
  const h = harness()
  h.render({ conversation: { id: 'empty', messages: [] } })
  assert.equal(h.container.calls, 0)
  h.render({ streamingMessage: 'Answer', isStreaming: true })
  assert.equal(h.container.scrollTop, 800)
})
