"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { apiJson } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

interface Conversation {
  id: string;
  title: string;
  mode: string;
  created_at: string;
}

export default function Sidebar() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [mode, setMode] = useState<"job_to_resume" | "find_jobs">(
    "job_to_resume"
  );
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    apiJson<Conversation[]>("/conversations").then(setConversations).catch(console.error);
  }, [pathname]);

  const handleNew = async () => {
    const conv = await apiJson<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({ mode }),
    });
    router.push(`/chat/${conv.id}`);
  };

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  };

  return (
    <aside className="w-64 bg-surface-dark text-content-inverse flex flex-col h-screen">
      <div className="p-4 border-b border-border-dark">
        <h1 className="text-lg font-bold">Resume AI</h1>
      </div>

      <div className="p-3">
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as typeof mode)}
          className="w-full p-2 bg-gray-800 rounded text-sm"
        >
          <option value="job_to_resume">Job &rarr; Resume</option>
          <option value="find_jobs">Find Jobs</option>
        </select>
        <button
          onClick={handleNew}
          className="w-full mt-2 p-2 bg-primary rounded hover:bg-primary-hover transition text-sm"
        >
          + New Chat
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-2 space-y-1">
        {conversations.map((c) => (
          <button
            key={c.id}
            onClick={() => router.push(`/chat/${c.id}`)}
            className={`w-full text-left p-2 rounded text-sm truncate hover:bg-gray-800 transition ${
              pathname === `/chat/${c.id}` ? "bg-gray-800" : ""
            }`}
          >
            {c.title}
          </button>
        ))}
      </nav>

      <div className="p-3 border-t border-border-dark">
        <button
          onClick={() => router.push("/history")}
          className="w-full p-2 text-sm text-content-secondary hover:text-content-inverse transition"
        >
          History
        </button>
        <button
          onClick={handleSignOut}
          className="w-full p-2 text-sm text-content-secondary hover:text-content-inverse transition"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
