import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#EFF6FF',
          100: '#DBEAFE',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#1E3A8A',
        },
        success: { 50: '#ECFDF5', 500: '#10B981', 700: '#047857' },
        warning: { 50: '#FFFBEB', 500: '#F59E0B', 700: '#B45309' },
        danger:  { 50: '#FEF2F2', 500: '#EF4444', 700: '#B91C1C' },
      },
      fontSize: {
        'base': ['16px', '1.6'],
        'lg':   ['18px', '1.6'],
        'xl':   ['20px', '1.5'],
        '2xl':  ['24px', '1.4'],
        '3xl':  ['32px', '1.3'],
      },
      minHeight: { touch: '48px' },
      minWidth:  { touch: '48px' },
    },
  },
  plugins: [],
} satisfies Config
