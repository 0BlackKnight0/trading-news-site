// frontend/app/layout.tsx
import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Since",
  description: "What changed since you last checked",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${dmSans.className} bg-[#0a0a0a] text-[#e5e5e5] antialiased`}>
        {children}
      </body>
    </html>
  );
}
