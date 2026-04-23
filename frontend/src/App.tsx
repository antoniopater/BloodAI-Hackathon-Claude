import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout/Layout'
import { HomeScreen } from './components/Screens/HomeScreen'
import { ScanScreen } from './components/Screens/ScanScreen'
import { InputScreen } from './components/Screens/InputScreen'
import { TriageScreen } from './components/Screens/TriageScreen'
import { DoctorFinderScreen } from './components/Screens/DoctorFinderScreen'
import { TrendsScreen } from './components/Screens/TrendsScreen'
import { ToastHost } from './components/UI/Toast'
import { useAppStore } from './store/useAppStore'

export default function App() {
  const theme = useAppStore((s) => s.theme)

  // Apply theme class on <html> for tailwind darkMode: 'class'
  useEffect(() => {
    const root = document.documentElement
    const apply = (mode: 'light' | 'dark') => {
      root.classList.toggle('dark', mode === 'dark')
    }
    if (theme === 'system') {
      const mql = window.matchMedia('(prefers-color-scheme: dark)')
      apply(mql.matches ? 'dark' : 'light')
      const handler = (e: MediaQueryListEvent) => apply(e.matches ? 'dark' : 'light')
      mql.addEventListener('change', handler)
      return () => mql.removeEventListener('change', handler)
    }
    apply(theme)
    return
  }, [theme])

  return (
    <>
      <Layout>
        <Routes>
          <Route path="/" element={<HomeScreen />} />
          <Route path="/scan" element={<ScanScreen />} />
          <Route path="/input" element={<InputScreen />} />
          <Route path="/triage" element={<TriageScreen />} />
          <Route path="/doctors" element={<DoctorFinderScreen />} />
          <Route path="/trends" element={<TrendsScreen />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
      <ToastHost />
    </>
  )
}
