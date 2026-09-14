import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppWrappers from './AppWrappers';
import './globals.css';

export const metadata: Metadata = {
  title: 'YZU Student Assistant',
  description: 'Find and understand YZU university information.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
      </head>
      <body><AppWrappers>{children}</AppWrappers></body>
    </html>
  );
}
