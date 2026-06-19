import { Button, Card, CardBody, CardHeader } from '@/shared/ui/ui'

interface ConfirmDialogProps {
  open: boolean
  title: string
  message?: string
  confirmLabel?: string
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = '확인',
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onCancel}
    >
      <Card
        className="w-full max-w-md"
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
      >
        <CardHeader>
          <h2 className="text-base font-semibold text-fg">{title}</h2>
        </CardHeader>
        <CardBody className="space-y-4">
          {message && <p className="text-sm text-muted">{message}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={onCancel}>
              취소
            </Button>
            <Button
              variant={danger ? 'danger' : 'primary'}
              size="sm"
              onClick={onConfirm}
            >
              {confirmLabel}
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
