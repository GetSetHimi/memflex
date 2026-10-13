export const metadata = {
  title: 'Memflex console — what your agent remembers vs what it pays for',
  description:
    'Observability console for Memflex: every LLM call vs every reflex answer, stored memories with confidence, calibration, and verification.',
  metadataBase: new URL('https://memflex.dev'),
  openGraph: {
    title: 'Memflex console',
    description: 'Every LLM call vs every reflex answer — live.',
    type: 'website',
  },
  robots: { index: false, follow: false },
};

export const viewport = { width: 'device-width', initialScale: 1 };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
