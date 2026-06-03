"use client";
import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { NewsFeed } from "@/components/NewsFeed";

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <NewsFeed onToggleSidebar={() => setSidebarOpen((v) => !v)} />
    </div>
  );
}
