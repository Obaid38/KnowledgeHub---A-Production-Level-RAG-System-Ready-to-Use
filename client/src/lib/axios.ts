// src/lib/axios.ts
import axios, { AxiosResponse } from "axios";
import { useAuthStore } from "@/store/authStore";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:7000/api/v1";


function unwrapEnvelope(response: AxiosResponse): AxiosResponse {
  const d = response.data;
  if (d && typeof d === "object" && "success" in d && "data" in d) {
    response.data = d.data;
  }
  return response;
}

function extractErrorMessage(error: unknown): string {
  const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
  if (!data) return "An unexpected error occurred.";
  const inner = data.error as Record<string, unknown> | undefined;
  return (
    (inner?.message as string) ??
    (data.message as string) ??
    "An unexpected error occurred."
  );
}

export const publicAxios = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

publicAxios.interceptors.request.use(
  (config) => config,
  (error)  => Promise.reject(error),
);

publicAxios.interceptors.response.use(
  (response) => unwrapEnvelope(response),
  (error)    => Promise.reject(new Error(extractErrorMessage(error))),
);

export const privateAxios = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

privateAxios.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error),
);

privateAxios.interceptors.response.use(
  (response) => unwrapEnvelope(response),
  (error) => {
    if (error?.response?.status === 401) {
      useAuthStore.getState().logout();
      if (typeof window !== "undefined") {
        const locale = window.location.pathname.split("/")[1] || "en";
        window.location.href = `/${locale}/signin`;
      }
    }
    return Promise.reject(new Error(extractErrorMessage(error)));
  },
);
