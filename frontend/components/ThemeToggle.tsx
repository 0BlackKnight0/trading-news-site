"use client";
import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  try {
    localStorage.setItem("theme", theme);
  } catch {
    // Private browsing / storage disabled — the choice just won't persist.
  }
}

// Reads whichever theme the blocking init script (see layout.tsx) already
// applied to <html> before paint, rather than re-deriving it here — one
// source of truth for "what theme is this" avoids the two ever disagreeing.
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
  }, []);

  if (theme === null) return null;

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  }

  return (
    <button
      onClick={toggle}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      className="text-[10px] font-medium px-2.5 py-1 rounded-full border border-border-default text-text-tertiary hover:text-text-primary hover:border-border-strong transition-colors"
    >
      {theme === "dark" ? "Dark" : "Light"}
    </button>
  );
}
