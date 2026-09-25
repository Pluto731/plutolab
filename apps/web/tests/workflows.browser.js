// Run as Playwright code. Mock API boundary; never connects to providers or real DB.
;async (page) => {
  page.setDefaultTimeout(10000)
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await page.addInitScript(() => {
    localStorage.setItem('pl_access', 'local-test')
    window.confirm = () => true
  })
  let rows = []
  let conflict = false
  let failure = false
  let writes = 0
  let imports = 0
  let failRunOnce = true
  const runRequests = []
  const runId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'
  const checks = []
  const agent = {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    name: '研究员',
    description: '',
    role_prompt: 'test',
    provider: 'openai',
    model: 'gpt-4o-mini',
    tools: [],
    version: 1,
    status: 'active',
    created_at: '',
    updated_at: '',
  }
  await page.route('**/*', async (route) => {
    const req = route.request()
    const parts = /^(https?:\/\/[^/]+)([^?]*)/.exec(req.url())
    const url = { origin: parts[1], pathname: parts[2] }
    const reply = (status, body) =>
      route.fulfill({
        status,
        headers: { 'access-control-allow-origin': '*' },
        contentType: 'application/json',
        body: JSON.stringify(body),
      })
    if (req.method() === 'OPTIONS')
      return route.fulfill({
        status: 204,
        headers: {
          'access-control-allow-origin': '*',
          'access-control-allow-headers': '*',
          'access-control-allow-methods': '*',
        },
      })
    if (url.pathname.startsWith('/api/v1/agents')) return reply(200, { items: [agent], total: 1 })
    if (url.pathname === '/api/v1/workflows/templates')
      return reply(200, {
        items: [
          {
            slug: 'research-and-review',
            version: 1,
            name: '资料研究与复核',
            description: 'mock template',
            required_tools: ['search_notes'],
          },
        ],
      })
    if (url.pathname.startsWith('/api/v1/workflows/templates/')) {
      imports++
      const value = {
        id: `ffffffff-ffff-4fff-8fff-${String(imports).padStart(12, '0')}`,
        version: 1,
        status: 'ready',
        name: '资料研究与复核',
        description: 'mock template',
        graph: {
          nodes: [
            {
              id: 'research',
              agent_id: `aaaaaaaa-aaaa-4aaa-8aaa-${String(imports * 2).padStart(12, '0')}`,
              agent_version: 1,
              label: '资料研究员',
            },
            {
              id: 'review',
              agent_id: `aaaaaaaa-aaaa-4aaa-8aaa-${String(imports * 2 + 1).padStart(12, '0')}`,
              agent_version: 1,
              label: '结论复核员',
            },
          ],
          edges: [{ source: 'research', target: 'review' }],
        },
        layout: {},
        created_at: '2026-09-24T00:00:00Z',
        updated_at: '2026-09-24T00:00:00Z',
      }
      rows.unshift(value)
      return reply(201, value)
    }
    if (/^\/api\/v1\/workflows\/[^/]+\/runs$/.test(url.pathname)) {
      runRequests.push({ body: req.postDataJSON(), key: req.headers()['idempotency-key'] })
      if (failRunOnce) {
        failRunOnce = false
        return reply(500, {})
      }
      return reply(202, {
        id: runId,
        workflow_id: rows[0].id,
        workflow_version: rows[0].version,
        state: 'pending',
        created_at: '2026-09-24T00:00:00Z',
        finished_at: null,
      })
    }
    if (url.pathname === '/api/v1/runs')
      return reply(200, {
        items: [
          {
            id: runId,
            workflow_id: rows[0].id,
            workflow_version: rows[0].version,
            state: 'succeeded',
            created_at: '2026-09-24T00:00:00Z',
            finished_at: '2026-09-24T00:00:01Z',
          },
        ],
        total: 1,
      })
    if (url.pathname === `/api/v1/runs/${runId}`)
      return reply(200, {
        id: runId,
        workflow_id: rows[0].id,
        workflow_version: rows[0].version,
        state: 'succeeded',
        created_at: '2026-09-24T00:00:00Z',
        finished_at: '2026-09-24T00:00:01Z',
        cancel_requested: false,
        event_sequence: 0,
        checkpoint: { completed_node_ids: [] },
        charged_tokens: 0,
        charged_cost_microusd: 0,
        graph: rows[0].graph,
        nodes: rows[0].graph.nodes.map(({ id }) => ({
          node_id: id,
          state: 'succeeded',
          error_code: null,
          output: null,
          attempts: 1,
          retries: 0,
        })),
      })
    if (url.pathname === `/api/v1/runs/${runId}/events`)
      return reply(200, { items: [], oldest_sequence: 0, latest_sequence: 0 })
    if (url.pathname.startsWith('/api/v1/workflows')) {
      if (req.method() === 'GET')
        return reply(
          200,
          url.pathname === '/api/v1/workflows' ? { items: rows, total: rows.length } : rows[0],
        )
      writes++
      if (failure) return reply(500, {})
      if (conflict) return reply(409, {})
      if (req.method() === 'DELETE') {
        rows = []
        return route.fulfill({ status: 204, headers: { 'access-control-allow-origin': '*' } })
      }
      const body = req.postDataJSON()
      if ('user_id' in body || 'api_key' in body) throw new Error('Unexpected privileged data')
      if (req.method() === 'PUT' && body.expected_version !== rows[0].version)
        throw new Error('Version mismatch')
      rows = [
        {
          ...body,
          id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
          version: (rows[0]?.version ?? 0) + 1,
          status: 'ready',
          created_at: '2026-09-24T00:00:00Z',
          updated_at: '2026-09-24T00:00:00Z',
        },
      ]
      return reply(req.method() === 'POST' ? 201 : 200, rows[0])
    }
    if (url.pathname.startsWith('/api/'))
      return reply(200, {
        id: agent.id,
        email: 'test@example.test',
        name: 'Tester',
        plan: 'free',
        email_verified: true,
      })
    if (url.origin !== 'http://localhost:3007') return route.abort()
    return route.continue()
  })
  await page.goto('http://localhost:3007/agents/workflows')
  await page.getByText('暂无流程。', { exact: true }).waitFor()
  if (!(await page.getByRole('button', { name: '保存流程', exact: true }).isDisabled()))
    throw new Error('Empty save enabled')
  checks.push('empty graph blocked')
  await page.getByLabel('流程名称', { exact: true }).fill('研究工作流')
  await page.getByRole('button', { name: '添加节点', exact: true }).click()
  await page.getByRole('button', { name: '添加节点', exact: true }).click()
  await page.getByLabel('节点 2 名称', { exact: true }).fill('复核员')
  await page.getByLabel('起点', { exact: true }).selectOption({ label: '1 · 研究员' })
  await page.getByLabel('终点', { exact: true }).selectOption({ label: '2 · 复核员' })
  await page.getByRole('button', { name: '添加连线', exact: true }).click()
  await page.locator('.react-flow__node').nth(1).waitFor()
  await page.locator('.react-flow__node').first().scrollIntoViewIfNeeded()
  const box = await page.locator('.react-flow__node').first().boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 + 50, box.y + box.height / 2 + 35, { steps: 6 })
  await page.mouse.up()
  checks.push('canvas add connect drag')
  await page.getByRole('button', { name: '保存流程', exact: true }).click()
  await page.getByText('流程已保存。', { exact: true }).waitFor()
  if (rows[0].graph.nodes.length !== 2 || rows[0].graph.edges.length !== 1)
    throw new Error('Graph not saved')
  const firstId = rows[0].graph.nodes[0].id
  if (rows[0].layout[firstId].x === 0 && rows[0].layout[firstId].y === 0)
    throw new Error('Drag not persisted')
  checks.push('save graph and layout')
  await page.getByLabel('起点', { exact: true }).selectOption({ label: '2 · 复核员' })
  await page.getByLabel('终点', { exact: true }).selectOption({ label: '1 · 研究员' })
  await page.getByRole('button', { name: '添加连线', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '存在环路' }).waitFor()
  if (!(await page.getByRole('button', { name: '保存流程', exact: true }).isDisabled()))
    throw new Error('Cycle save enabled')
  await page
    .getByRole('button', { name: /删除连线/ })
    .last()
    .click()
  checks.push('cycle located and repaired')
  await page.getByRole('button', { name: '仅用表单编辑' }).click()
  await page.getByRole('button', { name: '添加节点', exact: true }).focus()
  await page.keyboard.press('Enter')
  await page.getByLabel('节点 3 名称', { exact: true }).waitFor()
  await page.getByRole('button', { name: '删除节点 3', exact: true }).click()
  checks.push('keyboard and form fallback')
  failure = true
  await page.getByLabel('流程名称', { exact: true }).fill('失败后重试')
  await page.getByRole('button', { name: '保存流程', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '操作失败' }).waitFor()
  if ((await page.getByLabel('流程名称', { exact: true }).inputValue()) !== '失败后重试')
    throw new Error('Draft lost')
  failure = false
  await page.getByRole('button', { name: '保存流程', exact: true }).click()
  await page.getByText('流程已保存。', { exact: true }).waitFor()
  checks.push('failed save retains draft and retries')
  conflict = true
  await page.getByRole('button', { name: '保存流程', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '已被修改' }).waitFor()
  if (!(await page.getByRole('button', { name: '保存流程', exact: true }).isDisabled()))
    throw new Error('Conflict not blocked')
  conflict = false
  rows[0] = { ...rows[0], name: '服务器版本', version: 3 }
  await page.getByRole('button', { name: '重新加载流程' }).click()
  await page.getByText('已重新加载。', { exact: true }).waitFor()
  if ((await page.getByLabel('流程名称', { exact: true }).inputValue()) !== '服务器版本')
    throw new Error('Reload failed')
  checks.push('conflict reload')
  await page.getByRole('button', { name: '删除节点 1', exact: true }).click()
  if ((await page.getByRole('button', { name: /删除连线/ }).count()) !== 0)
    throw new Error('Dangling edges after removal')
  await page.getByRole('button', { name: '保存流程', exact: true }).click()
  await page.getByText('流程已保存。', { exact: true }).waitFor()
  checks.push('delete node cleans edges')
  await page.getByRole('button', { name: '归档流程' }).click()
  await page.getByText('流程已归档。', { exact: true }).waitFor()
  checks.push('archive')
  await page.getByRole('button', { name: '导入私有副本', exact: true }).click()
  await page.getByText('模板已复制到你的私有 Workflow，可独立编辑。', { exact: true }).waitFor()
  const firstTemplateId = rows[0].id
  await page.getByRole('button', { name: '导入私有副本', exact: true }).click()
  await page.getByText('模板已复制到你的私有 Workflow，可独立编辑。', { exact: true }).waitFor()
  if (imports !== 2 || rows[0].id === firstTemplateId)
    throw new Error('Template imports must create separate private copies')
  checks.push('versioned template imports create separate copies')
  await page.getByLabel('运行任务输入', { exact: true }).fill('请研究本地资料并复核结论')
  await page.getByLabel('流程描述', { exact: true }).fill('运行前需要先保存')
  if (!(await page.getByRole('button', { name: '创建 Run', exact: true }).isDisabled()))
    throw new Error('Run must be blocked while the Workflow has unsaved changes')
  checks.push('unsaved workflow changes block Run creation')
  await page.getByRole('button', { name: '保存流程', exact: true }).click()
  await page.getByText('流程已保存。', { exact: true }).waitFor()
  await page.getByRole('button', { name: '创建 Run', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '运行请求失败' }).waitFor()
  const firstRunKey = runRequests[0]?.key
  if (!firstRunKey) throw new Error('Run creation must send an idempotency key')
  await page.getByRole('button', { name: '创建 Run', exact: true }).click()
  await page.waitForURL(`**/agents/runs/${runId}`)
  if (
    runRequests.length !== 2 ||
    runRequests[0].body.workflow_version !== rows[0].version ||
    runRequests[1].body.workflow_version !== rows[0].version ||
    runRequests[1].body.text !== '请研究本地资料并复核结论' ||
    runRequests[1].key !== firstRunKey
  )
    throw new Error('Run retry must preserve saved version, input and idempotency key')
  checks.push('Run creation retries with the same idempotency key')
  return { checks, writes, imports, runAttempts: runRequests.length }
}
