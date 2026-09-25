import Link from 'next/link'
import { Activity, Bot, Workflow } from 'lucide-react'

const sections = [
  { label: 'Agents', href: '/agents', hint: '成员配置', icon: Bot },
  { label: 'Workflows', href: '/agents/workflows', hint: '流程编排', icon: Workflow },
  { label: '运行监控', href: '/agents/runs', hint: '执行记录', icon: Activity },
] as const

export function Phase6Navigation({ active }: { active: (typeof sections)[number]['href'] }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
        <span className="grid size-6 place-items-center rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-sm">
          <Workflow className="size-3.5" />
        </span>
        <span>PLUTOLAB</span>
        <span className="text-border">/</span>
        <span className="text-violet-600 dark:text-violet-300">AGENT STUDIO</span>
      </div>
      <nav
        aria-label="Phase 6 工作区"
        className="flex gap-6 overflow-x-auto border-b border-border/70"
      >
        {sections.map((section) => {
          const selected = section.href === active
          const Icon = section.icon
          return (
            <Link
              key={section.href}
              href={section.href}
              aria-current={selected ? 'page' : undefined}
              className={`group relative flex shrink-0 items-center gap-2.5 py-3 text-sm transition-colors ${
                selected
                  ? 'font-semibold text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icon
                className={`size-4 ${selected ? 'text-violet-600 dark:text-violet-300' : ''}`}
              />
              <span>{section.label}</span>
              <span className="hidden text-xs font-normal text-muted-foreground sm:inline">
                {section.hint}
              </span>
              {selected && (
                <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500" />
              )}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
