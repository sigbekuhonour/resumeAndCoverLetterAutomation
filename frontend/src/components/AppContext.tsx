"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { usePathname } from "next/navigation";
import { apiJson } from "@/lib/api";

export interface Conversation {
  id: string;
  title: string;
  mode: string;
  status: string;
  created_at: string;
}

interface AppContextValue {
  conversations: Conversation[];
  loading: boolean;
  error: string | null;
  activeConversation: Conversation | null;
  setActiveConversation: (conv: Conversation | null) => void;
  refreshConversations: () => Promise<void>;
}

const AppContext = createContext<AppContextValue>({
  conversations: [],
  loading: true,
  error: null,
  activeConversation: null,
  setActiveConversation: () => {},
  refreshConversations: async () => {},
});

export function useApp() {
  return useContext(AppContext);
}

export default function AppProvider({ children }: { children: React.ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const pathname = usePathname();

  const refreshConversations = useCallback(async () => {
    try {
      setError(null);
      const data = await apiJson<Conversation[]>("/conversations");
      setConversations(data);
    } catch {
      setError("Could not load conversations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshConversations();
  }, [pathname, refreshConversations]);

  return (
    <AppContext.Provider
      value={{
        conversations,
        loading,
        error,
        activeConversation,
        setActiveConversation,
        refreshConversations,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}
