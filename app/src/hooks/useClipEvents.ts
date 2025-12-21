/**
 * Hook for subscribing to real-time clip events via SSE.
 */

import { useEffect, useRef } from "react";
import { API_BASE_URL } from "@/constants";
import { getAppToken } from "@/lib/api";

interface ClipEventCallbacks {
  onClipCreated?: (clipId: number, data: unknown) => void;
  onClipUpdated?: (clipId: number, data: unknown) => void;
  onClipDeleted?: (clipId: number) => void;
}

export function useClipEvents(callbacks: ClipEventCallbacks) {
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  useEffect(() => {
    const token = getAppToken();
    const url = `${API_BASE_URL}/api/events${token ? `?token=${token}` : ""}`;

    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case "clip_created":
            callbacksRef.current.onClipCreated?.(data.memory_id, data.data);
            break;
          case "clip_updated":
            callbacksRef.current.onClipUpdated?.(data.memory_id, data.data);
            break;
          case "clip_deleted":
            callbacksRef.current.onClipDeleted?.(data.memory_id);
            break;
        }
      } catch (e) {
        console.error("Failed to parse clip event:", e);
      }
    };

    eventSource.onerror = () => {
      // EventSource will automatically reconnect
    };

    return () => {
      eventSource.close();
    };
  }, []);
}
