// Lightweight Tailwind UI primitives (no external component lib).
import { forwardRef } from 'react'
import type {
  ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes,
  SelectHTMLAttributes, TextareaHTMLAttributes,
} from 'react'
import { cn } from '@/shared/lib/cn'

type Variant = 'primary' | 'ghost' | 'outline' | 'danger'
type Size = 'sm' | 'md'

const btnVariants: Record<Variant, string> = {
  primary: 'bg-primary text-primary-fg hover:opacity-90',
  ghost: 'hover:bg-surface text-fg',
  outline: 'border border-border hover:bg-surface text-fg',
  danger: 'bg-danger text-white hover:opacity-90',
}
const btnSizes: Record<Size, string> = {
  sm: 'h-8 px-2.5 text-xs',
  md: 'h-9 px-3.5 text-sm',
}

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }
>(({ className, variant = 'outline', size = 'md', ...props }, ref) => (
  <button
    ref={ref}
    className={cn(
      'inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition disabled:opacity-50 disabled:pointer-events-none',
      btnVariants[variant], btnSizes[size], className,
    )}
    {...props}
  />
))
Button.displayName = 'Button'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-lg border border-border bg-surface', className)} {...props} />
}
export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-4 py-3 border-b border-border', className)} {...props} />
}
export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-4', className)} {...props} />
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn('h-9 w-full rounded-md border border-border bg-bg px-3 text-sm outline-none focus:border-primary', className)}
      {...props}
    />
  ),
)
Input.displayName = 'Input'

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn('w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none focus:border-primary mono', className)}
      {...props}
    />
  ),
)
Textarea.displayName = 'Textarea'

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => (
    <select
      ref={ref}
      className={cn('h-9 w-full rounded-md border border-border bg-bg px-2 text-sm outline-none focus:border-primary', className)}
      {...props}
    />
  ),
)
Select.displayName = 'Select'

export function Label({ className, ...props }: HTMLAttributes<HTMLLabelElement>) {
  return <label className={cn('text-xs font-medium text-muted', className)} {...props} />
}

const toneMap: Record<string, string> = {
  queued: 'bg-muted/20 text-muted',
  running: 'bg-primary/15 text-primary',
  succeeded: 'bg-success/15 text-success',
  failed: 'bg-danger/15 text-danger',
  canceled: 'bg-warning/15 text-warning',
  default: 'bg-muted/15 text-muted',
}

export function Badge({ tone = 'default', children, className }: { tone?: string; children: React.ReactNode; className?: string }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium', toneMap[tone] ?? toneMap.default, className)}>
      {children}
    </span>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span className={cn('inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent', className)} />
  )
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="text-center py-10 text-muted">
      <div className="text-sm font-medium">{title}</div>
      {hint && <div className="text-xs mt-1 opacity-80">{hint}</div>}
    </div>
  )
}
