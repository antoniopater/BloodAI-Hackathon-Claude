import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { UserCheck, Eye } from 'lucide-react'
import { Card } from '../UI/Card'
import { Button } from '../UI/Button'
import { Input } from '../UI/Input'
import { useAppStore } from '../../store/useAppStore'

export function LoginScreen() {
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const user = useAppStore((s) => s.user)
  const login = useAppStore((s) => s.login)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [errors, setErrors] = useState<{ name?: string; email?: string }>({})

  if (user) {
    navigate(from, { replace: true })
    return null
  }

  const handleGuest = () => navigate(from, { replace: true })

  const handleLogin = () => {
    const errs: { name?: string; email?: string } = {}
    if (!name.trim()) errs.name = 'Name is required'
    if (!email.trim() || !email.includes('@')) errs.email = 'Enter a valid email'
    if (Object.keys(errs).length) {
      setErrors(errs)
      return
    }
    login(name.trim(), email.trim())
    navigate(from, { replace: true })
  }

  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center py-10">
      <div className="w-full max-w-2xl space-y-6">
        <header className="text-center">
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-50">
            Welcome to BloodAI
          </h1>
          <p className="mt-2 text-base text-slate-600 dark:text-slate-300">
            Check your blood results instantly — or sign in to track them over time.
          </p>
        </header>

        <div className="grid gap-4 sm:grid-cols-2">
          {/* Guest card */}
          <Card padding="lg" className="flex flex-col gap-5">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-700">
              <Eye className="h-6 w-6 text-slate-600 dark:text-slate-300" aria-hidden="true" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">Quick Check</h2>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                Analyse your results now without saving. No account needed.
              </p>
            </div>
            <div className="mt-auto">
              <Button variant="secondary" fullWidth onClick={handleGuest}>
                Continue as Guest
              </Button>
            </div>
          </Card>

          {/* Account card */}
          <Card padding="lg" className="flex flex-col gap-5">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50 dark:bg-primary-800/30">
              <UserCheck className="h-6 w-6 text-primary-700 dark:text-primary-100" aria-hidden="true" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">My Account</h2>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                Save results and view your history over time.
              </p>
            </div>
            <div className="space-y-3">
              <Input
                label="Your name"
                placeholder="e.g. Anna Kowalska"
                value={name}
                onChange={(e) => { setName(e.target.value); setErrors((p) => ({ ...p, name: undefined })) }}
                error={errors.name}
                autoComplete="name"
              />
              <Input
                label="Email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setErrors((p) => ({ ...p, email: undefined })) }}
                error={errors.email}
                autoComplete="email"
                onKeyDown={(e) => { if (e.key === 'Enter') handleLogin() }}
              />
            </div>
            <div className="mt-auto">
              <Button fullWidth onClick={handleLogin}>
                Enter
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
