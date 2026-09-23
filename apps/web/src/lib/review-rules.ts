export const focusAreas = ['security', 'performance', 'quality'] as const
export type FocusArea = (typeof focusAreas)[number]

export interface RepositoryRules {
  installation_id: string
  repo_id: string
  repo_name: string
  enabled: boolean
  min_pr_lines: number
  max_pr_lines: number | null
  skip_paths: string[]
  focus_areas: FocusArea[]
  rules_version: number
}

export interface RuleDraft {
  enabled: boolean
  min: string
  max: string
  paths: string
  focus: FocusArea[]
}

export type RulesUpdate = Pick<
  RepositoryRules,
  'enabled' | 'min_pr_lines' | 'max_pr_lines' | 'skip_paths' | 'focus_areas'
> & { expected_rules_version: number }

export function ruleDraft(rules: RepositoryRules): RuleDraft {
  return {
    enabled: rules.enabled,
    min: String(rules.min_pr_lines),
    max: rules.max_pr_lines === null ? '' : String(rules.max_pr_lines),
    paths: rules.skip_paths.join('\n'),
    focus: [...rules.focus_areas],
  }
}

export function validateRules(
  draft: RuleDraft,
  version: number,
): { value: RulesUpdate; error?: never } | { error: string; value?: never } {
  const positive = (s: string) => /^[1-9][0-9]*$/.test(s) && Number(s) <= 2147483647
  if (!positive(draft.min) || (draft.max !== '' && !positive(draft.max))) {
    return { error: '行数必须为 1–2147483647 的整数；最大行数可留空。' }
  }
  if (draft.max !== '' && Number(draft.max) < Number(draft.min)) {
    return { error: '最大行数不能小于最小行数。' }
  }
  const paths = draft.paths === '' ? [] : draft.paths.split('\n')
  if (
    paths.length > 100 ||
    new Set(paths).size !== paths.length ||
    paths.some(
      (p) =>
        [...p].length > 256 ||
        !p ||
        p.trim() !== p ||
        /[\p{C}\p{Zl}\p{Zp}\\:[\]{}!^$()|]/u.test(p) ||
        // Python str.isprintable also rejects non-ASCII separator spaces.
        [...p].some((c) => c !== ' ' && /\p{Zs}/u.test(c)) ||
        p.split('/').some((part) => ['', '.', '..'].includes(part)) ||
        p.split('/').some((part) => part.includes('**') && part !== '**'),
    )
  ) {
    return {
      error:
        '忽略路径最多 100 条，每条 1–256 字符且不重复；仅支持相对 glob（*、**、?），不支持正则、绝对路径或 ..。',
    }
  }
  if (
    draft.focus.length < 1 ||
    draft.focus.length > 3 ||
    new Set(draft.focus).size !== draft.focus.length ||
    draft.focus.some((f) => !focusAreas.includes(f))
  ) {
    return { error: '请至少选择一个评审方向。' }
  }
  return {
    value: {
      enabled: draft.enabled,
      min_pr_lines: Number(draft.min),
      max_pr_lines: draft.max === '' ? null : Number(draft.max),
      skip_paths: paths,
      focus_areas: [...draft.focus],
      expected_rules_version: version,
    },
  }
}

export function validRepositorySearch(query: string): boolean {
  return query.length <= 100 && /^[A-Za-z0-9_. /-]*$/.test(query)
}
