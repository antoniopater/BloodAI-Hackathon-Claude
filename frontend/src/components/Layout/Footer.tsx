import { ShieldCheck, Github } from 'lucide-react'

export function Footer() {
  return (
    <footer
      role="contentinfo"
      className="mt-16 border-t border-slate-200 bg-white py-8 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="mx-auto flex max-w-6xl flex-col items-start gap-4 px-4 sm:px-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
          <ShieldCheck className="h-5 w-5 text-primary-700" aria-hidden="true" />
          <span>
            Educational tool. Always consult a qualified physician before making medical decisions.
          </span>
        </div>
        <div className="flex items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
          <a
            href="https://github.com/"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 hover:text-primary-800 dark:hover:text-primary-100"
          >
            <Github className="h-4 w-4" aria-hidden="true" /> Open source (MIT)
          </a>
          <span>&copy; {new Date().getFullYear()} BloodAI</span>
        </div>
      </div>
    </footer>
  )
}
