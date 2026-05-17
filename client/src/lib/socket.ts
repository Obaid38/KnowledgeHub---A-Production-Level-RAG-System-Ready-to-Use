// src/lib/socket.ts
// Lazy Socket.IO singleton — created once with the current auth token.
import { io, Socket } from "socket.io-client";
import { useAuthStore } from "@/store/authStore";

const SOCKET_URL =
  process.env.NEXT_PUBLIC_SOCKET_URL ??
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:7000/api/v1")
    .replace(/\/api\/v1\/?$/, ""); // strip the /api/v1 path — Socket.IO sits at root

let socket: Socket | null = null;

/**
 * Returns the shared Socket.IO client, creating it on first call.
 * The JWT token is read from the Zustand auth store at creation time.
 */
export function getSocket(): Socket {
  if (!socket) {
    const token = useAuthStore.getState().token;
    socket = io(SOCKET_URL, {
      auth:       { token },
      transports: ["websocket", "polling"],
      autoConnect: false,
    });
  }
  return socket;
}

/** Disconnect and clear the singleton (call on logout). */
export function destroySocket(): void {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}
