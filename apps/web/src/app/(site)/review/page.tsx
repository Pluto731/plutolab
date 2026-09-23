import type { Metadata } from 'next'
import Link from 'next/link'
import { Button } from '@/components/ui/button'

export const metadata: Metadata = {
  title: 'AI 代码评审 · PlutoLab',
  description: 'GitHub App 安装与仓库评审设置',
}

export default function ReviewPage() {
  return (
    <main className="mx-auto max-w-4xl space-y-6 px-4 py-10">
      <h1 className="text-3xl font-semibold">AI 代码评审</h1>
      <p className="text-muted-foreground">管理 GitHub App 安装，为仓库配置评审规则。</p>
      <Button asChild>
        <Link href="/review/settings">安装与评审设置</Link>
      </Button>
    </main>
  )
}
