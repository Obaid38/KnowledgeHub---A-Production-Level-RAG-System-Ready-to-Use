"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { getProfileApi } from "@/services/auth.service";

export function AuthInitializer() {
  const { token, setUser, logout, setProfileReady } = useAuthStore();

  const { data: profile, isError } = useQuery({
    queryKey:  ["auth", "me", token],
    queryFn:   getProfileApi,
    enabled:   !!token,
    staleTime: 5 * 60 * 1000,
    retry:     false,     
  });

  useEffect(() => {
    const markReadyIfNoToken = (state: { token: string | null }) => {
      if (!state.token) setProfileReady();
    };

    if (useAuthStore.persist.hasHydrated()) {
      markReadyIfNoToken(useAuthStore.getState());
    } else {
      return useAuthStore.persist.onFinishHydration(markReadyIfNoToken);
    }
  }, []); 

  useEffect(() => {
    if (profile && token) {
      setUser(profile, token);
    }
  }, [profile, token, setUser]);

  useEffect(() => {
    if (isError) logout();
  }, [isError, logout]);

  return null;
}
