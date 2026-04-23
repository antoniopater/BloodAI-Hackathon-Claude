import { create } from 'zustand'

export type ToastKind = 'success' | 'error' | 'info' | 'warning'

export interface Toast {
  id: string
  kind: ToastKind
  message: string
  /** Optional title shown in bold above the message. */
  title?: string
  /** Auto-dismiss after ms; 0 = manual dismiss only. */
  durationMs?: number
}

interface ToastState {
  toasts: Toast[]
  push: (t: Omit<Toast, 'id'>) => string
  dismiss: (id: string) => void
  clear: () => void
}

let toastCounter = 0

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (t) => {
    toastCounter += 1
    const id = `t-${Date.now()}-${toastCounter}`
    const toast: Toast = { id, durationMs: 4000, ...t }
    set((s) => ({ toasts: [...s.toasts, toast] }))
    if (toast.durationMs && toast.durationMs > 0) {
      setTimeout(() => {
        set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) }))
      }, toast.durationMs)
    }
    return id
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clear: () => set({ toasts: [] }),
}))

/** Convenience helpers outside components. */
export const toast = {
  success: (message: string, title?: string) =>
    useToastStore.getState().push({ kind: 'success', message, title }),
  error: (message: string, title?: string) =>
    useToastStore.getState().push({ kind: 'error', message, title, durationMs: 6000 }),
  info: (message: string, title?: string) =>
    useToastStore.getState().push({ kind: 'info', message, title }),
  warning: (message: string, title?: string) =>
    useToastStore.getState().push({ kind: 'warning', message, title, durationMs: 5000 }),
}
