// Run as Playwright code. The API boundary is mocked; no database, Redis or Provider calls.
;async (page) => {
  page.setDefaultTimeout(12000)
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await page.addInitScript(() => localStorage.setItem('pl_access', 'local-run-test'))
  const checks = []
  const original = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
  const clone = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
  let done = false
  const now = () => new Date().toISOString()
  const started = {
    sequence: 1,
    event_type: 'run_started',
    node_id: null,
    state: 'running',
    summary: null,
    created_at: now(),
  }
  const finishedNode = {
    sequence: 2,
    event_type: 'node_finished',
    node_id: 'research',
    state: 'succeeded',
    summary: null,
    created_at: now(),
  }
  const finishedRun = {
    sequence: 3,
    event_type: 'run_finished',
    node_id: null,
    state: 'succeeded',
    summary: null,
    created_at: now(),
  }
  const reply = (route, status, body, contentType = 'application/json') =>
    route.fulfill({
      status,
      contentType,
      headers: {
        'access-control-allow-origin': '*',
        'access-control-allow-headers': '*',
        'access-control-allow-methods': '*',
      },
      body: typeof body === 'string' ? body : JSON.stringify(body),
    })
  const summary = (id, state) => ({
    id,
    workflow_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
    workflow_version: 2,
    state,
    created_at: now(),
    finished_at: state === 'succeeded' ? now() : null,
  })
  const detail = (id, state, eventSequence) => ({
    ...summary(id, state),
    cancel_requested: false,
    event_sequence: eventSequence,
    checkpoint: { completed_node_ids: state === 'succeeded' ? ['research', 'summary'] : [] },
    charged_tokens: state === 'succeeded' ? 140 : 0,
    charged_cost_microusd: state === 'succeeded' ? 42 : 0,
    graph: {
      nodes: [
        {
          id: 'research',
          agent_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
          agent_version: 1,
          label: '研究节点',
        },
        {
          id: 'summary',
          agent_id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
          agent_version: 1,
          label: '总结节点',
        },
      ],
      edges: [{ source: 'research', target: 'summary' }],
    },
    nodes: [
      {
        node_id: 'research',
        state: state === 'succeeded' ? 'succeeded' : 'running',
        error_code: null,
        output: state === 'succeeded' ? '<script>window.__runXss = true</script>结论文本' : null,
        attempts: 1,
        retries: 0,
      },
      {
        node_id: 'summary',
        state: state === 'succeeded' ? 'succeeded' : 'pending',
        error_code: null,
        output: state === 'succeeded' ? '完成' : null,
        attempts: 0,
        retries: 0,
      },
    ],
  })
  await page.route('**/*', async (route) => {
    const req = route.request()
    const parts = /^(https?:\/\/[^/]+)(\/[^?#]*)/.exec(req.url())
    const pathname = parts?.[2] || '/'
    if (!pathname.startsWith('/api/v1/')) return route.continue()
    if (req.method() === 'OPTIONS')
      return route.fulfill({
        status: 204,
        headers: {
          'access-control-allow-origin': '*',
          'access-control-allow-headers': '*',
          'access-control-allow-methods': '*',
        },
      })
    if (pathname === '/api/v1/health')
      return reply(route, 200, { status: 'ok', version: 'test', env: 'test' })
    if (pathname === '/api/v1/auth/me')
      return reply(route, 200, {
        id: original,
        email: 'test@example.test',
        name: 'Tester',
        plan: 'free',
        email_verified: true,
      })
    if (pathname === '/api/v1/runs')
      return reply(route, 200, {
        items: [summary(original, done ? 'succeeded' : 'running')],
        total: 1,
      })
    if (pathname === `/api/v1/runs/${original}/events/stream`) {
      if (req.headers()['last-event-id'] !== '1')
        throw new Error('SSE did not resume from Last-Event-ID')
      done = true
      return reply(
        route,
        200,
        `id: 2\nevent: node_finished\ndata: ${JSON.stringify(finishedNode)}\n\nid: 3\nevent: run_finished\ndata: ${JSON.stringify(finishedRun)}\n\n`,
        'text/event-stream',
      )
    }
    if (pathname === `/api/v1/runs/${original}/events`) {
      const after = Number(/[?&]after=(\d+)/.exec(req.url())?.[1] || 0)
      const events = done ? [started, finishedNode, finishedRun] : [started]
      return reply(route, 200, {
        items: events.filter((event) => event.sequence > after).slice(0, 128),
        oldest_sequence: 1,
        latest_sequence: done ? 3 : 1,
      })
    }
    if (pathname === `/api/v1/runs/${original}`)
      return reply(route, 200, detail(original, done ? 'succeeded' : 'running', done ? 3 : 1))
    if (pathname === `/api/v1/runs/${clone}/events`)
      return reply(route, 200, { items: [], oldest_sequence: 1, latest_sequence: 0 })
    if (pathname === `/api/v1/runs/${clone}`) return reply(route, 200, detail(clone, 'pending', 0))
    if (pathname === `/api/v1/runs/${original}/rerun`)
      return reply(route, 202, summary(clone, 'pending'))
    throw new Error(`Unexpected API request: ${req.method()} ${pathname}`)
  })
  await page.goto(`http://127.0.0.1:3007/agents/runs/${original}`)
  await page.getByText('协作运行监控', { exact: true }).waitFor()
  await page.getByText('研究节点', { exact: true }).waitFor()
  await page.getByText('总结节点', { exact: true }).waitFor()
  checks.push('Run detail and dependency topology render')
  await page.getByText('最近 3 条', { exact: true }).waitFor()
  await page.getByText('查看节点输出', { exact: true }).first().click()
  const output = await page.locator('pre').first().innerText()
  if (
    !output.includes('<script>window.__runXss = true</script>') ||
    (await page.locator('pre script').count()) !== 0 ||
    (await page.evaluate(() => window.__runXss))
  )
    throw new Error('Node output was not rendered as inert text')
  checks.push('Provider output renders as escaped plain text')
  await page.getByRole('button', { name: '按原快照重跑' }).waitFor()
  await page.getByRole('button', { name: '按最新 Workflow 重跑' }).waitFor()
  checks.push('terminal Run offers explicit snapshot and latest rerun choices')
  return { checks }
}
