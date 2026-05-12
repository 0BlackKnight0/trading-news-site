// frontend/app/page.tsx
import { Sidebar } from "@/components/Sidebar";
import { NewsFeed } from "@/components/NewsFeed";

export default function Home() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <NewsFeed />
    </div>
  );
}
