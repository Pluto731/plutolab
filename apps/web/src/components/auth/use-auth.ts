"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { type AuthUser, clearTokens, fetchMe, getAccessToken } from "@/lib/auth";

/**
 * Current-user state for the navbar etc. Reads the token only on the client
 * (after mount) to avoid SSR hydration mismatches, then fetches /auth/me.
 */
export function useAuthUser() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setToken(getAccessToken());
    setMounted(true);
  }, []);

  const { data, isLoading } = useQuery<AuthUser>({
    queryKey: ["auth-me", token],
    queryFn: fetchMe,
    enabled: mounted && !!token,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const logout = () => {
    clearTokens();
    setToken(null);
    queryClient.removeQueries({ queryKey: ["auth-me"] });
  };

  return {
    user: data ?? null,
    loading: !mounted || (!!token && isLoading),
    mounted,
    logout,
  };
}
