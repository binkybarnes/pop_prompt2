import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        bg: '#fafafa',
        surface: '#ffffff',
        border: '#e5e7eb',
        fg: '#111827',
        muted: '#6b7280',
        brand: '#1b2a4a',
        alert: '#dc2626',
        warn: '#f59e0b',
        ok: '#16a34a',
      },
    },
  },
  plugins: [],
};

export default config;
