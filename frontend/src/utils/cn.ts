/** Tiny classnames helper. Accepts strings, arrays, or {class: bool} maps. */
type ClassInput = string | number | null | undefined | false | ClassInput[] | Record<string, boolean>

export function cn(...inputs: ClassInput[]): string {
  const out: string[] = []
  const visit = (v: ClassInput) => {
    if (!v) return
    if (typeof v === 'string' || typeof v === 'number') {
      out.push(String(v))
      return
    }
    if (Array.isArray(v)) {
      for (const item of v) visit(item)
      return
    }
    if (typeof v === 'object') {
      for (const [k, enabled] of Object.entries(v)) {
        if (enabled) out.push(k)
      }
    }
  }
  for (const input of inputs) visit(input)
  return out.join(' ')
}
