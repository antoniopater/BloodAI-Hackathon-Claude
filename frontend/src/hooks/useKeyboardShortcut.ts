import { useEffect } from 'react'

/**
 * Binds a handler to a keydown event. `keys` accepts single keys like "Escape",
 * or combos like "meta+k" (also matches ctrl on non-mac).
 */
export function useKeyboardShortcut(
  keys: string | string[],
  handler: (e: KeyboardEvent) => void,
  deps: React.DependencyList = [],
): void {
  useEffect(() => {
    const list = Array.isArray(keys) ? keys : [keys]
    const parsed = list.map((k) => {
      const parts = k.toLowerCase().split('+')
      return {
        key: parts[parts.length - 1],
        meta: parts.includes('meta') || parts.includes('cmd'),
        ctrl: parts.includes('ctrl'),
        shift: parts.includes('shift'),
        alt: parts.includes('alt'),
      }
    })

    const onKeyDown = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase()
      for (const p of parsed) {
        if (p.key !== key) continue
        if (p.meta && !(e.metaKey || e.ctrlKey)) continue
        if (p.ctrl && !e.ctrlKey) continue
        if (p.shift && !e.shiftKey) continue
        if (p.alt && !e.altKey) continue
        handler(e)
        return
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}
