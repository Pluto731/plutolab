'use client'

import { AlertCircle, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ErrorNotice({
  message,
  onDismiss,
}: {
  message: string | null
  onDismiss?: () => void
}) {
  if (!message) return null
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0" />
      <span className="min-w-0 flex-1 break-words">{message}</span>
      {onDismiss && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-6 shrink-0"
          aria-label="关闭错误提示"
          onClick={onDismiss}
        >
          <X className="size-4" />
        </Button>
      )}
    </div>
  )
}
