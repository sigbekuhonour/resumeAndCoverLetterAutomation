"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/components/AppContext";
import { apiJson } from "@/lib/api";

type ModeFilter = "all" | "job_to_resume" | "find_jobs";
type StatusFilter = "all" | "active" | "completed";

export default function HistoryPage() {
  const { conversations, loading, refreshConversations } = useApp();
  const [modeFilter, setModeFilter] = useState<ModeFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const router = useRouter();

  const filtered = conversations.filter((c) => {
    const matchesMode = modeFilter === "all" || c.mode === modeFilter;
    const matchesStatus = statusFilter === "all" || c.status === statusFilter;
    return matchesMode && matchesStatus;
  });

  const handleNew = async () => {
    const conv = await apiJson<{ id: string }>("/conversations", {
      method: "POST",
      body: JSON.stringify({ mode: "job_to_resume" }),
    });
    await refreshConversations();
    router.push(`/chat/${conv.id}`);
  };

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      <div className="max-w-3xl mx-auto">
        {/* Filters */}
        <div className="flex gap-1.5 mb-6 flex-wrap">
          {(["all", "job_to_resume", "find_jobs"] as ModeFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setModeFilter(f)}
              className={`px-3 py-1 rounded-full text-xs transition ${
                modeFilter === f
                  ? "bg-accent-muted text-accent border border-accent/20"
                  : "bg-bg-secondary text-text-secondary border border-border hover:text-text-primary"
              }`}
            >
              {f === "all" ? "All modes" : f === "job_to_resume" ? "Job → Resume" : "Find Jobs"}
            </button>
          ))}
          <div className="w-px h-5 bg-border self-center mx-1" />
          {(["all", "active", "completed"] as StatusFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setStatusFilter(f)}
              className={`px-3 py-1 rounded-full text-xs transition ${
                statusFilter === f
                  ? "bg-accent-muted text-accent border border-accent/20"
                  : "bg-bg-secondary text-text-secondary border border-border hover:text-text-primary"
              }`}
            >
              {f === "all" ? "All status" : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        {/* List */}
        {loading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 rounded-lg bg-bg-secondary animate-pulse" />
            ))}
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="w-12 h-12 rounded-xl bg-bg-secondary border border-border flex items-center justify-center mb-4">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <h3 className="text-sm font-medium text-text-primary mb-1">No conversations yet</h3>
            <p className="text-xs text-text-tertiary mb-4">Start a new chat to generate your first tailored resume.</p>
            <button
              onClick={handleNew}
              className="px-4 py-1.5 text-xs font-medium bg-accent text-white rounded-md hover:bg-accent-hover transition"
            >
              New Chat
            </button>
          </div>
        )}

        {!loading && filtered.length > 0 && (
          <div className="space-y-1">
            {filtered.map((c) => (
              <button
                key={c.id}
                onClick={() => router.push(`/chat/${c.id}`)}
                className="w-full text-left px-4 py-3 bg-bg-secondary border border-border rounded-lg hover:border-accent/30 transition flex items-center justify-between group"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text-primary truncate group-hover:text-accent transition">{c.title}</p>
                  <p className="text-[11px] text-text-tertiary mt-0.5">
                    {c.mode === "job_to_resume" ? "Job → Resume" : "Find Jobs"} ·{" "}
                    {new Date(c.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span
                  className={`text-[10px] px-2 py-0.5 rounded-full flex-shrink-0 ml-3 ${
                    c.status === "active"
                      ? "bg-accent-muted text-accent"
                      : "bg-bg-tertiary text-text-secondary"
                  }`}
                >
                  {c.status === "active" ? "Active" : "Completed"}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
