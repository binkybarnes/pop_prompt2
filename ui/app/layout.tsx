import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'POP Reorder Intelligence',
  description: 'Hack the Coast 2026 — F1 reorder alert UI',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
