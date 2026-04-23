import { Link, NavLink } from 'react-router-dom'
import { Activity, Moon, Sun, Monitor, LineChart, Home } from 'lucide-react'
import { useAppStore } from '../../store/useAppStore'
import { cn } from '../../utils/cn'

function ThemeToggle() {
  const theme = useAppStore((s) => s.theme)
  const setTheme = useAppStore((s) => s.setTheme)

  const next = theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system'
  const icon =
    theme === 'dark' ? <Moon className="h-5 w-5" /> :
    theme === 'light' ? <Sun className="h-5 w-5" /> :
    <Monitor className="h-5 w-5" />

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={`Theme: ${theme}. Switch to ${next}.`}
      title={`Theme: ${theme}`}
      className="inline-flex items-center justify-center rounded-lg p-2 min-h-[44px] min-w-[44px] text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
    >
      {icon}
    </button>
  )
}

export function Header() {
  return (
    <header
      role="banner"
      className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-900/90"
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link to="/" className="flex items-center gap-2" aria-label="BloodAI home">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-primary-700 text-white shadow-sm">
            <Activity className="h-6 w-6" aria-hidden="true" />
          </span>
          <span className="flex flex-col leading-tight">
            <span className="text-lg font-extrabold text-slate-900 dark:text-slate-50">BloodAI</span>
            <span className="text-xs text-slate-500 dark:text-slate-400">Your Health Advisor</span>
          </span>
        </Link>

        <nav aria-label="Primary" className="flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              cn(
                'hidden sm:inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold min-h-[40px]',
                isActive ? 'text-primary-800 dark:text-primary-100' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
              )
            }
          >
            <Home className="h-4 w-4" /> Home
          </NavLink>
          <NavLink
            to="/trends"
            className={({ isActive }) =>
              cn(
                'hidden sm:inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold min-h-[40px]',
                isActive ? 'text-primary-800 dark:text-primary-100' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
              )
            }
          >
            <LineChart className="h-4 w-4" /> Trends
          </NavLink>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  )
}
