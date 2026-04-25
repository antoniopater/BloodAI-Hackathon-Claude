import { useState, useRef, useEffect } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { Activity, Moon, Sun, Monitor, LineChart, Home, User, ClipboardList, LogOut } from 'lucide-react'
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

function UserMenu() {
  const navigate = useNavigate()
  const user = useAppStore((s) => s.user)
  const logout = useAppStore((s) => s.logout)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (!user) {
    return (
      <Link
        to="/login"
        className="inline-flex items-center gap-1.5 rounded-xl border border-primary-700 px-3 py-2 text-sm font-semibold text-primary-700 hover:bg-primary-50 dark:border-primary-400 dark:text-primary-300 dark:hover:bg-primary-900/20 min-h-[40px]"
      >
        <User className="h-4 w-4" aria-hidden="true" />
        Login
      </Link>
    )
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-700 min-h-[40px]"
        aria-haspopup="true"
        aria-expanded={open}
      >
        <User className="h-4 w-4" aria-hidden="true" />
        <span className="hidden sm:block max-w-[120px] truncate">{user.name}</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-44 rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800 z-50">
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-t-xl px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-700"
            onClick={() => { setOpen(false); navigate('/history') }}
          >
            <ClipboardList className="h-4 w-4" aria-hidden="true" />
            My History
          </button>
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-b-xl px-4 py-3 text-sm font-medium text-danger-700 hover:bg-danger-50 dark:text-red-400 dark:hover:bg-red-900/20"
            onClick={() => { setOpen(false); logout() }}
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Log out
          </button>
        </div>
      )}
    </div>
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
          <UserMenu />
        </nav>
      </div>
    </header>
  )
}
