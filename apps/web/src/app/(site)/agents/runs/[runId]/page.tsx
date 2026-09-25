import { RunMonitor } from '@/components/agents/run-monitor'

export default async function RunDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params
  return <RunMonitor initialRunId={runId} />
}
