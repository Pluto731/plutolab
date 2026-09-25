// Run via Playwright browser_run_code_unsafe filename; API traffic is mocked.
;async (page) => {
  page.setDefaultTimeout(10000)
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await page.addInitScript(() => localStorage.setItem('pl_access', 'local-test'))
  let rows = []
  let conflict = false
  let fail = false
  let writes = 0
  const checks = []
  await page.route('**/*', async (route) => {
    const req = route.request()
    const parts = /^(https?:\/\/[^/]+)([^?]*)/.exec(req.url())
    const url = { origin: parts[1], pathname: parts[2] }
    if (url.pathname.startsWith('/api/v1/agents')) {
      if (req.method() === 'OPTIONS')
        return route.fulfill({
          status: 204,
          headers: {
            'access-control-allow-origin': '*',
            'access-control-allow-headers': '*',
            'access-control-allow-methods': '*',
          },
        })
      const reply = (status, body) =>
        route.fulfill({
          status,
          headers: { 'access-control-allow-origin': '*' },
          contentType: 'application/json',
          body: JSON.stringify(body),
        })
      if (req.method() === 'GET')
        return reply(fail ? 500 : 200, { items: rows, total: rows.length })
      writes++
      if (conflict) return reply(409, {})
      if (req.method() === 'DELETE') {
        rows = []
        return reply(200, {})
      }
      const body = req.postDataJSON()
      if ('user_id' in body || 'api_key' in body) throw new Error('Unexpected privileged field')
      if (req.method() === 'PUT' && body.expected_version !== rows[0].version)
        throw new Error('Missing CAS')
      rows = [
        {
          ...body,
          id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          version: (rows[0]?.version ?? 0) + 1,
          status: 'active',
          created_at: '',
          updated_at: '',
        },
      ]
      return reply(req.method() === 'POST' ? 201 : 200, rows[0])
    }
    if (url.pathname.startsWith('/api/'))
      return route.fulfill({
        status: 200,
        headers: { 'access-control-allow-origin': '*' },
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          email: 'test@example.test',
          name: 'Tester',
          plan: 'free',
          email_verified: true,
        }),
      })
    if (url.origin !== 'http://127.0.0.1:3007') return route.abort()
    return route.continue()
  })
  await page.goto('http://127.0.0.1:3007/agents')
  await page.getByText('暂无 Agent。', { exact: true }).waitFor()
  checks.push('empty')
  await page.getByLabel('名称', { exact: true }).fill('研究员')
  await page.getByLabel('角色指令', { exact: true }).fill('<script>preview</script>')
  await page.getByLabel('搜索本人笔记（只读）').check()
  if ((await page.locator('pre').textContent()) !== '<script>preview</script>')
    throw new Error('Preview mismatch')
  checks.push('safe preview')
  await page.getByRole('button', { name: '保存配置', exact: true }).click()
  await page.getByText('已保存。', { exact: true }).waitFor()
  if (rows[0].tools[0] !== 'search_notes') throw new Error('Tool selection missing')
  checks.push('create + tool')
  await page.getByLabel('名称', { exact: true }).fill('编辑研究员')
  await page.getByRole('button', { name: '保存配置', exact: true }).click()
  await page.getByText('版本 2', { exact: true }).waitFor()
  checks.push('edit CAS')
  conflict = true
  await page.getByRole('button', { name: '保存配置', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '配置已被修改' }).waitFor()
  if (!(await page.getByRole('button', { name: '保存配置', exact: true }).isDisabled()))
    throw new Error('Conflict retry not blocked')
  checks.push('conflict')
  conflict = false
  await page.getByRole('button', { name: '放弃草稿并重新加载' }).click()
  await page.getByRole('button', { name: /编辑研究员/ }).click()
  await page.evaluate(() => {
    window.confirm = () => true
  })
  await page.getByRole('button', { name: '归档 Agent' }).click()
  await page.getByText('已归档。', { exact: true }).waitFor()
  checks.push('archive')
  fail = true
  await page.getByRole('button', { name: '刷新列表' }).click()
  await page.getByRole('alert').waitFor()
  fail = false
  await page.getByRole('button', { name: '刷新列表' }).click()
  await page.getByText('暂无 Agent。', { exact: true }).waitFor()
  checks.push('error retry')
  return { checks, writes, externalProviderCalls: 0 }
}
