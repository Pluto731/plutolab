// Run with the Playwright browser_run_code tool against the local server on :3007.
// All APIs and external navigation are intercepted; no live GitHub interaction.
async function reviewSettingsBrowser(page) {
  page.setDefaultTimeout(5000)
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  const parameter = (query, name) =>
    decodeURIComponent(
      (
        query
          .replace(/^\?/, '')
          .split('&')
          .find((part) => part.startsWith(`${name}=`)) ?? '='
      )
        .split('=')
        .slice(1)
        .join('=')
        .replace(/\+/g, ' '),
    )
  const base = 'http://127.0.0.1:3007'
  const passed = []
  const failures = []
  let mode = 'active'
  let version = 1
  let saved = null
  let bindCalls = 0
  let revokeCalls = 0
  let listCalls = 0
  let failList = false
  let conflict = false
  let saveFailure = false
  const requests = []
  const rule = () => ({
    installation_id: '301',
    repo_id: '9',
    repo_name: 'owner/demo',
    enabled: true,
    min_pr_lines: 1,
    max_pr_lines: null,
    skip_paths: ['docs/**'],
    focus_areas: ['security', 'performance', 'quality'],
    rules_version: version,
  })
  await page.route('**/*', async (route) => {
    const request = route.request()
    const parts = /^(https?:\/\/[^/]+)([^?]*)(.*)$/.exec(request.url())
    const url = { origin: parts[1], pathname: parts[2], search: parts[3] }
    if (
      url.origin !== base &&
      !(url.origin === 'http://localhost:8000' && url.pathname.startsWith('/api/'))
    ) {
      // Even successful install initiation never reaches GitHub.
      if (url.origin === 'https://github.com')
        return route.fulfill({ contentType: 'text/html', body: '<p>Mock GitHub installation</p>' })
      return route.abort()
    }
    if (!url.pathname.startsWith('/api/')) return route.continue()
    const body = request.postDataJSON()
    requests.push({ path: url.pathname, query: url.search, method: request.method(), body })
    const json = (data, status = 200) =>
      route.fulfill({
        status,
        contentType: 'application/json',
        headers: {
          'access-control-allow-origin': base,
          'access-control-allow-headers': 'authorization,content-type',
          'access-control-allow-methods': 'GET,POST,PUT,DELETE,OPTIONS',
        },
        body: JSON.stringify(data),
      })
    if (request.method() === 'OPTIONS') return json({})
    if (url.pathname === '/api/v1/auth/me')
      return json({
        id: 'user-one',
        name: 'Fixture User',
        email: 'fixture@local.invalid',
        avatar: null,
        plan: 'free',
        email_verified: true,
      })
    const root = '/api/v1/review/installations'
    if (url.pathname === root) {
      listCalls++
      if (failList) return json({}, 500)
      if (mode === 'loading') await page.waitForTimeout(1200)
      return json({
        github_account_id: '101',
        installations:
          mode === 'uninstalled'
            ? []
            : [
                {
                  installation_id: '301',
                  active: mode !== 'revoked',
                  revoked_at: mode === 'revoked' ? '2026-09-18T00:00:00Z' : null,
                },
              ],
      })
    }
    if (url.pathname === `${root}/start`)
      return json({
        installation_url: `https://github.com/apps/plutolab/installations/new?state=${'s'.repeat(43)}`,
      })
    if (url.pathname === `${root}/callback`) {
      bindCalls++
      mode = 'active'
      return json({ installation_id: '301', active: true, revoked_at: null })
    }
    if (url.pathname === `${root}/301` && request.method() === 'DELETE') {
      revokeCalls++
      mode = 'revoked'
      return json({ installation_id: '301', active: false, revoked_at: '2026-09-18T00:00:00Z' })
    }
    if (url.pathname.endsWith('/settings')) {
      if (request.method() === 'PUT') {
        if (conflict) {
          version = 2
          conflict = false
          return json({}, 409)
        }
        if (saveFailure) return json({ detail: 'secret-state-do-not-render' }, 500)
        saved = body
        version++
        return json({ ...rule(), ...body, rules_version: version })
      }
      return json(rule())
    }
    if (url.pathname.endsWith('/repositories')) {
      const current = Number(parameter(url.search, 'page'))
      const query = parameter(url.search, 'q')
      const empty = mode === 'empty' || query === 'missing'
      return json({
        repositories: empty
          ? []
          : [
              {
                repo_id: '9',
                repo_name: current === 2 ? 'owner/second' : 'owner/demo',
                private: true,
                default_branch: 'main',
                enabled: true,
                rules_version: version,
              },
            ],
        total_count: empty ? 0 : 11,
        page: current,
        per_page: 10,
      })
    }
    return json({ status: 'ok' })
  })
  const check = (condition, message) => {
    if (!condition) throw new Error(message)
  }
  const visible = async (locator) => {
    await locator.waitFor({ state: 'visible', timeout: 10000 })
  }
  const test = async (name, fn) => {
    try {
      await fn()
      passed.push(name)
    } catch (e) {
      failures.push({ name, error: String(e).slice(0, 350) })
    }
  }
  const open = async (nextMode = 'active', suffix = '') => {
    mode = nextMode
    failList = false
    saveFailure = false
    conflict = false
    version = 1
    saved = null
    await page.goto(`${base}/review/settings${suffix}`)
  }
  await page.goto(base)
  await page.evaluate(() => localStorage.clear())
  await test('unauthenticated view', async () => {
    await page.goto(`${base}/review/settings`)
    await visible(page.getByRole('heading', { name: '登录后管理评审设置' }))
  })
  await page.evaluate(() => localStorage.setItem('pl_access', 'fixture-site-token'))
  await test('uninstalled view and account identity', async () => {
    await open('uninstalled')
    await visible(page.getByRole('button', { name: '安装并绑定 GitHub App' }))
    await visible(page.getByText('GitHub 账号 ID：101'))
  })
  await test('loading skeleton', async () => {
    await open('loading')
    await visible(page.getByLabel('正在加载安装'))
    await visible(page.getByRole('button', { name: '配置 owner/demo' }))
  })
  await test('empty repository view', async () => {
    await open('empty')
    await visible(page.getByText('此安装暂无可访问仓库，请检查 GitHub App 的仓库授权。'))
  })
  await test('listing, pagination and keyword search', async () => {
    await open()
    await page.getByRole('button', { name: '下一页' }).click()
    await visible(page.getByRole('button', { name: '配置 owner/second' }))
    await page.getByLabel('搜索仓库').fill('missing')
    await page.getByRole('button', { name: '搜索', exact: true }).click()
    await visible(page.getByText('没有匹配的仓库，请调整关键词。'))
    const last = requests.filter((r) => r.path.endsWith('/repositories')).at(-1)
    check(parameter(last.query, 'page') === '1', 'search must reset page')
  })
  await test('form rejects invalid lines and malformed paths without PUT', async () => {
    await open()
    await page.getByRole('button', { name: '配置 owner/demo' }).click()
    await page.getByLabel('最小 PR 行数').fill('0')
    await page.getByRole('button', { name: '保存规则', exact: true }).click()
    await visible(page.getByRole('region', { name: '仓库评审规则' }).getByRole('alert'))
    check(saved === null, 'invalid form saved')
    await page.getByLabel('最小 PR 行数').fill('1')
    await page.getByLabel('忽略路径（每行一条）').fill('../secret')
    await page.getByRole('button', { name: '保存规则', exact: true }).click()
    check(
      (
        await page.getByRole('region', { name: '仓库评审规则' }).getByRole('alert').innerText()
      ).includes('相对 glob'),
      'glob error missing',
    )
    check(saved === null, 'invalid path saved')
  })
  await test('successful rule save carries expected version and feedback', async () => {
    await page.getByLabel('忽略路径（每行一条）').fill('src/**')
    await page.getByLabel('最大 PR 行数（留空不限）').fill('400')
    await page.getByRole('button', { name: '保存规则', exact: true }).click()
    await visible(page.getByText('规则已保存。'))
    check(saved.expected_rules_version === 1 && saved.max_pr_lines === 400, 'save payload mismatch')
    await visible(page.getByText('当前规则版本 v2；保存时会检查版本。'))
  })
  await test('conflict retains draft and requires explicit version reconciliation', async () => {
    await open()
    await page.getByRole('button', { name: '配置 owner/demo' }).click()
    await page.getByLabel('最小 PR 行数').fill('7')
    conflict = true
    await page.getByRole('button', { name: '保存规则', exact: true }).click()
    await visible(page.getByRole('button', { name: '读取最新版本' }))
    check((await page.getByLabel('最小 PR 行数').inputValue()) === '7', 'draft lost')
    check(
      await page.getByRole('button', { name: '保存规则', exact: true }).isDisabled(),
      'conflict save not disabled',
    )
    await page.getByRole('button', { name: '读取最新版本' }).click()
    await page.getByRole('button', { name: '保留草稿，按新版本再保存' }).click()
    await page.getByRole('button', { name: '保存规则', exact: true }).click()
    await visible(page.getByText('规则已保存。'))
    check(
      saved.expected_rules_version === 2 && saved.min_pr_lines === 7,
      'reconciled save mismatch',
    )
  })
  await test('failed save retains draft, redacts server data, and retries', async () => {
    await open()
    await page.getByRole('button', { name: '配置 owner/demo' }).click()
    await page.getByLabel('最小 PR 行数').fill('8')
    saveFailure = true
    await page.getByRole('button', { name: '保存规则', exact: true }).click()
    await visible(page.getByRole('region', { name: '仓库评审规则' }).getByRole('alert'))
    check((await page.getByLabel('最小 PR 行数').inputValue()) === '8', 'failed save lost draft')
    check(
      !(await page.locator('body').innerText()).includes('secret-state'),
      'server secret leaked',
    )
    saveFailure = false
    await page.getByRole('button', { name: '保存规则', exact: true }).click()
    await visible(page.getByText('规则已保存。'))
  })
  await test('installation error has retry recovery', async () => {
    failList = true
    await page.getByRole('button', { name: '刷新安装状态' }).click()
    await visible(page.getByRole('button', { name: '重试安装状态' }))
    failList = false
    await page.getByRole('button', { name: '重试安装状态' }).click()
    await visible(page.getByRole('button', { name: '配置 owner/demo' }))
  })
  await test('revocation requires confirmation and removes repository controls', async () => {
    await page.getByRole('button', { name: '解绑安装', exact: true }).click()
    check(revokeCalls === 0, 'revoked before confirmation')
    await page.getByRole('button', { name: '取消', exact: true }).click()
    check(revokeCalls === 0, 'cancel mutated installation')
    await page.getByRole('button', { name: '解绑安装', exact: true }).click()
    await page.getByRole('button', { name: '确认解绑', exact: true }).click()
    await visible(page.getByText('安装已停用。历史规则仍保留，新的评审与发布已停止。'))
    check(revokeCalls === 1, 'revoke count mismatch')
    check(
      (await page.getByRole('button', { name: '配置 owner/demo' }).count()) === 0,
      'revoked repo controls present',
    )
  })
  await test('callback query is scrubbed, explicitly confirmed and sent once', async () => {
    await open('uninstalled', `?installation_id=301&state=${'s'.repeat(43)}&user_id=attacker`)
    await visible(page.getByRole('button', { name: '确认绑定', exact: true }))
    check(!page.url().includes('?'), 'state remains in URL')
    check(bindCalls === 0, 'callback auto posted')
    await page.getByRole('button', { name: '确认绑定', exact: true }).click()
    await visible(page.getByText('个人 GitHub 安装已验证并绑定。'))
    check(bindCalls === 1, 'callback not single post')
    const body = requests.find((r) => r.path.endsWith('/callback')).body
    check(!('user_id' in body), 'query user identity forwarded')
  })
  await test('tampered callback rejected without mutation', async () => {
    await open('uninstalled', '?installation_id=301&state=bad')
    await visible(page.getByText('安装回调无效，请重新发起安装。'))
    check(bindCalls === 1, 'tampered callback posted')
  })
  await test('mobile layout and keyboard rule editing', async () => {
    await page.setViewportSize({ width: 390, height: 844 })
    await open()
    await page.getByRole('button', { name: '配置 owner/demo' }).click()
    await page.getByLabel('最小 PR 行数').focus()
    await page.keyboard.press('Tab')
    check(
      await page
        .getByLabel('最大 PR 行数（留空不限）')
        .evaluate((element) => element === document.activeElement),
      'keyboard order incorrect',
    )
    check(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      'mobile horizontal overflow',
    )
    await page.setViewportSize({ width: 1280, height: 900 })
    await open('uninstalled')
  })
  await test('install initiation follows only validated URL into a mocked page', async () => {
    await page.getByRole('button', { name: '安装并绑定 GitHub App' }).click()
    await visible(page.getByText('Mock GitHub installation'))
  })
  return {
    passed: passed.length,
    failed: failures.length,
    cases: passed,
    failures,
    installationReads: listCalls,
  }
}
