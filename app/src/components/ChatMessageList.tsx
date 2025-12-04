import { useEffect, useRef } from "react";
import { Loader2, Search } from "lucide-react";
import { ChatMessage } from "./ChatMessage";
import type { ChatMessage as ChatMessageType } from "@/types/chat";

interface ChatMessageListProps {
  messages: ChatMessageType[];
  isLoading?: boolean;
}

export function ChatMessageList({ messages, isLoading }: ChatMessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Check if any message is currently streaming
  const hasStreamingMessage = messages.some((m) => m.isStreaming);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, isLoading]);

  // Only show loading indicator before streaming starts
  const showLoading = isLoading && !hasStreamingMessage;

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto p-4 space-y-4"
    >
      {messages.map((message) => (
        <ChatMessage key={message.id} message={message} />
      ))}
      {showLoading && (
        <div className="flex justify-start animate-slide-up">
          <div className="bg-muted p-3 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Search className="h-3 w-3" />
              <span>Searching memories...</span>
              <Loader2 className="h-3 w-3 animate-spin" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
