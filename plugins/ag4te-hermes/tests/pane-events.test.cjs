const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')

// Load the shipped ESM with a small hook runner; no React or bundler dependency.
const source = fs.readFileSync(`${__dirname}/../desktop/plugin.js`, 'utf8')
  .replace(/^import .*$/gm, '').replace('export default', 'const plugin =')
function mount(name, ctx, dom = {}) {
  const slots = [], effects = [], listeners = new Map(), pending = []
  let index = 0, tree
  const hook = (init) => { const i = index++; if (!(i in slots)) slots[i] = init(); return i }
  const effect = (fn, deps) => {
    const i = index++, prev = slots[i]
    if (!prev || deps.some((d, j) => d !== prev.deps[j])) {
      slots[i] = { deps, cleanup: prev && prev.cleanup }
      effects.push(() => { slots[i].cleanup?.(); slots[i].cleanup = fn() })
    }
  }
  dom.querySelector ||= () => null
  const sandbox = {
    sdk: { host: { onEvent: (event, fn) => { listeners.set(event, fn); return () => listeners.delete(event) } } },
    useState: init => { const i = hook(() => typeof init === 'function' ? init() : init); return [slots[i], v => { slots[i] = typeof v === 'function' ? v(slots[i]) : v }] },
    useRef: value => slots[hook(() => ({ current: value }))],
    useMemo: fn => { index++; return fn() }, useEffect: effect, useLayoutEffect: effect,
    jsx: (type, props) => { if (props.ref && typeof type === 'string') props.ref.current = dom; return { type, props } },
    jsxs: (type, props) => sandbox.jsx(type, props),
    document: { hidden: false }, setTimeout: fn => pending.push(fn),
    setInterval: fn => { pending.push(fn); return pending.length }, clearInterval: () => {},
  }
  vm.createContext(sandbox)
  vm.runInContext(source + `\nuseMode = () => 'dark'; globalThis.component = ${name};`, sandbox)
  const render = () => { index = 0; tree = sandbox.component(ctx); while (effects.length) effects.shift()(); return tree }
  const flush = async () => { for (let i = 0; i < 8; i++) { await Promise.resolve(); render() } }
  render()
  return { render, flush, listeners, pending, get tree() { return tree },
    emit: (event, payload) => listeners.get(`plugin.ag4te.${event}`)?.({ payload }),
    unmount: () => slots.forEach(s => s?.cleanup?.()) }
}
const nodes = tree => !tree || typeof tree !== 'object' ? []
  : [tree, ...[tree.props?.children].flat().flatMap(nodes)]
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const project = p => ({ project: p, has_dig: true, commit_count: 1 })
const storage = { get: () => 'old', set: () => {} }

test('live dig selection wins over an in-flight project list', async () => {
  const oldList = deferred()
  let lists = 0
  const page = mount('Page', { ctx: { storage, rest: path => {
    if (path === '/projects') return ++lists === 1 ? oldList.promise : Promise.resolve({ projects: [project('new')] })
    return Promise.resolve(path === '/repos' ? { repos: [] } : { project: 'new', empty: true })
  } } })
  page.emit('dig.selected', { project: 'new' })
  await page.flush()
  oldList.resolve({ projects: [project('old')] })
  await page.flush()
  assert.equal(nodes(page.tree).find(n => n.props?.['aria-label'] === 'Dig to show').props.value, 'new')
  page.unmount()
  assert.equal(page.listeners.size, 0)
})

test('late dig and status responses cannot replace a live selection', async () => {
  const oldDig = deferred(), oldStatus = deferred()
  let lists = 0
  const page = mount('Page', { ctx: { storage, rest: path => {
    if (path === '/projects') return Promise.resolve({ projects: ++lists === 1
      ? [{ ...project('old'), state: 'running' }] : [project('new')] })
    if (path === '/dig?project=old') return oldDig.promise
    if (path === '/status?project=old') return oldStatus.promise
    return Promise.resolve(path === '/repos' ? { repos: [] } : { project: 'new', empty: true })
  } } })
  await page.flush()
  page.emit('dig.selected', { project: 'new' })
  // Resolve before React effects run: the event must invalidate these immediately.
  oldDig.resolve({ project: 'old', fault: 'stale dig' })
  oldStatus.resolve({ project: 'old', state: 'done' })
  await page.flush()
  assert.equal(nodes(page.tree).find(n => n.props?.['aria-label'] === 'Dig to show').props.value, 'new')
  assert(!JSON.stringify(page.tree).includes('stale dig'))
  page.unmount()
})

test('dig events refresh same-project snapshots and ignore malformed navigation', async () => {
  let reads = 0
  const page = mount('Page', { ctx: { storage, rest: path => {
    if (path === '/projects') return Promise.resolve({ projects: [project('old')] })
    if (path.startsWith('/dig?')) { reads++; return Promise.resolve({ project: 'old', empty: true }) }
    return Promise.resolve({ repos: [] })
  } } })
  await page.flush()
  const before = reads
  page.emit('view.set', { view: 'unknown' })
  page.emit('view.set', { view: 'story', item_id: 'x'.repeat(129) })
  page.emit('dig.selected', { project: '/home/private' })
  page.emit('dig.selected', { project: 'old\r' })
  page.emit('projects.updated', { count: -1 })
  page.emit('view.set', { view: 'story', item_id: 'origin\r' })
  page.emit('view.set', { view: 'story', text: 'private' })
  await page.flush()
  assert.equal(reads, before)
  page.emit('projects.updated', { count: 1 })
  await page.flush()
  assert(reads > before)
  const refreshed = reads
  page.emit('dig.updated', { project: 'old', state: 'done' })
  await page.flush()
  assert(reads > refreshed)
  page.unmount()
})

test('show focuses a section item after the current dig loads', async () => {
  let focused = 0, scrolled = 0
  const item = { dataset: { agItem: 'origin' }, setAttribute() {}, focus() { focused++ }, scrollIntoView() { scrolled++ } }
  const section = { querySelectorAll: () => [item] }
  const dom = { querySelector: selector => selector === '[data-ag-view="story"]' ? section : null }
  const page = mount('Page', { ctx: { storage, rest: path => Promise.resolve(path === '/projects'
    ? { projects: [project('old')] } : path === '/repos' ? { repos: [] } : { project: 'old', empty: true }) } }, dom)
  page.emit('view.set', { view: 'story', item_id: 'origin' })
  await page.flush()
  assert(focused > 0 && scrolled > 0)
  page.unmount()
})

test('terminal dig events fetch status details without broadcasting them', async () => {
  const page = mount('Page', { ctx: { storage, rest: path => Promise.resolve(path === '/projects'
    ? { projects: [project('old')] } : path === '/status?project=old'
      ? { state: 'done', warnings: ['Signals unavailable'] } : { project: 'old', empty: true }) } })
  await page.flush()
  page.emit('dig.updated', { project: 'old', state: 'done' })
  await page.flush()
  assert(JSON.stringify(page.tree).includes('Signals unavailable'))
  page.unmount()
})

test('commit focus reveals a row beyond the first page', async () => {
  let focused = 0
  const dom = { dataset: { agView: 'commits' }, setAttribute() {}, scrollIntoView() {}, focus() {},
    querySelectorAll: () => [{ dataset: { agItem: 'abc89' }, setAttribute() {}, scrollIntoView() {}, focus() { focused++ } }] }
  const commits = Array.from({ length: 90 }, (_, i) => ({ sha: `abc${i}`, t: `2026-01-01T00:${String(i % 60).padStart(2, '0')}:00Z`, msg: 'test', author: 'A', kind: 'test' }))
  const page = mount('Commits', { d: { project: 'demo', commits, clusters: [] }, pal: {}, eraNo: [], target: { view: 'commits', item_id: 'abc89', revision: 1 } }, dom)
  await page.flush()
  assert(nodes(page.tree).some(n => n.props?.['data-ag-item'] === 'abc89'))
  assert(focused > 0)
  const before = focused
  nodes(page.tree).find(n => n.props?.['aria-label'] === 'Search commits').props.onChange({ target: { value: 'test' } })
  await page.flush()
  assert.equal(focused, before, 'manual search must keep keyboard focus')
  page.unmount()
})

test('release focus renders a target older than the ten newest releases', () => {
  const sandbox = {
    jsx: (type, props) => ({ type, props }),
    jsxs: (type, props) => ({ type, props }),
    Date, Intl, Math, Number, String, Array, Object,
  }
  vm.createContext(sandbox)
  vm.runInContext(source + '\nglobalThis.Releases = Releases;', sandbox)
  const releases = Array.from({ length: 11 }, (_, i) => ({
    name: `v${i}`,
    sha: `sha${i}`,
    d: `2026-01-${String(i + 1).padStart(2, '0')}`,
    on_history: true,
  }))
  const tree = sandbox.Releases({
    d: { releases, commits: [] },
    multiYear: false,
    target: { view: 'releases', item_id: 'sha0', revision: 1 },
  })

  assert(nodes(tree).some(n => n.props?.['data-ag-item'] === 'sha0'))
})
