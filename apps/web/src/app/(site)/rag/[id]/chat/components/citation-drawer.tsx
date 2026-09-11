'use client'

import * as Dialog from '@radix-ui/react-dialog'
import { Check, ChevronLeft, ChevronRight, Copy, FileText, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { ErrorNotice } from '@/components/ui/error-notice'
import type { CitationItem } from '@/lib/rag'

interface CitationDrawerProps {
  open: boolean
  onClose: () => void
  citations: CitationItem[]
  currentIndex: number
  onNavigate: (index: number) => void
}

export function CitationDrawer({
  open,
  onClose,
  citations,
  currentIndex,
  onNavigate,
}: CitationDrawerProps) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const opener = useRef<HTMLElement | null>(null)
  const currentItem = citations[currentIndex]

  useEffect(() => {
    setCopied(false)
    setError(null)
  }, [currentItem?.chunk_id, open])
  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(timer)
  }, [copied])

  const copy = async () => {
    if (!currentItem) return
    try {
      await navigator.clipboard.writeText(currentItem.content)
      setCopied(true)
      setError(null)
    } catch {
      setError('无法访问剪贴板，请选中原文手动复制。')
    }
  }
  const page = currentItem?.metadata.page
  return (
    <Dialog.Root
      open={open && !!currentItem}
      onOpenChange={(value) => {
        if (!value) onClose()
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30 backdrop-blur-xs data-[state=open]:animate-in data-[state=closed]:animate-out fade-in-0 fade-out-0 motion-reduce:animate-none" />
        <Dialog.Content
          onOpenAutoFocus={() => {
            opener.current =
              document.activeElement instanceof HTMLElement ? document.activeElement : null
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault()
            opener.current?.focus()
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowLeft' && currentIndex > 0) {
              event.preventDefault()
              onNavigate(currentIndex - 1)
            }
            if (event.key === 'ArrowRight' && currentIndex + 1 < citations.length) {
              event.preventDefault()
              onNavigate(currentIndex + 1)
            }
          }}
          className="fixed inset-y-0 right-0 z-50 flex h-dvh w-full max-w-lg flex-col border-l border-border bg-background shadow-2xl data-[state=open]:animate-in slide-in-from-right duration-200 motion-reduce:animate-none"
        >
          <header className="flex items-center justify-between gap-3 border-b border-border bg-muted/30 p-5">
            <div>
              <Dialog.Title className="text-base font-semibold">参考原文</Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-muted-foreground">
                查看回答引用的文档内容。
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label="关闭原文">
                <X className="size-4" />
              </Button>
            </Dialog.Close>
          </header>
          {currentItem && (
            <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
              <div className="rounded-2xl border border-border bg-card p-4">
                <p className="flex items-start gap-2 break-all text-sm font-medium">
                  <FileText className="mt-0.5 size-4 shrink-0 text-primary" />
                  {currentItem.filename}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {typeof page === 'number' && `第 ${page} 页 · `}
                  {currentItem.content.length} 字符
                </p>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">引用片段</span>
                <Button variant="ghost" size="sm" onClick={copy}>
                  {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                  {copied ? '已复制' : '复制原文'}
                </Button>
              </div>
              <ErrorNotice message={error} onDismiss={() => setError(null)} />
              <blockquote className="whitespace-pre-wrap break-words rounded-xl border-l-2 border-primary bg-muted/30 p-4 text-sm leading-7">
                {currentItem.content}
              </blockquote>
            </div>
          )}
          <footer className="flex items-center justify-between border-t border-border p-4">
            <Button
              variant="outline"
              size="sm"
              disabled={currentIndex <= 0}
              onClick={() => onNavigate(currentIndex - 1)}
              aria-label="上一个引用"
            >
              <ChevronLeft className="size-4" />
              上一个
            </Button>
            <span aria-live="polite" className="text-xs tabular-nums text-muted-foreground">
              {currentIndex + 1} / {citations.length}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={currentIndex >= citations.length - 1}
              onClick={() => onNavigate(currentIndex + 1)}
              aria-label="下一个引用"
            >
              下一个
              <ChevronRight className="size-4" />
            </Button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
