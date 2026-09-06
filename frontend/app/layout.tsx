// frontend/app/layout.tsx
import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Market Dashboard",
  description: "Personal trading news and market data dashboard",
};

// Applies the stored theme to <html> before first paint, so switching
// themes doesn't flash the wrong one on reload. Defaults to dark — this
// app's original look — when no choice has been made yet.
const THEME_INIT_SCRIPT = `
(function() {
  try {
    var stored = localStorage.getItem('theme');
    var dark = stored ? stored === 'dark' : true;
    document.documentElement.classList.toggle('dark', dark);
  } catch (e) {
    document.documentElement.classList.add('dark');
  }
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // The init script below sets the `dark` class before React hydrates —
    // exactly one attribute on exactly this element is expected to differ
    // between server and client, so this is the correct scope for the
    // warning suppression rather than turning it off tree-wide.
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className={`${dmSans.className} bg-app text-text-primary antialiased`}>
        {children}
      </body>
    </html>
  );
}
