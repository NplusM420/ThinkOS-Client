import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { Button } from '@/components/ui/button';
import { BookOpen, ChevronRight, ExternalLink, FileText, Bookmark, Save, Sparkles, MoreHorizontal, Check, Send, Loader2, Copy, Volume2, VolumeX, Mic, MicOff, Square, ChevronDown, Bot } from 'lucide-react';
import type { ChatMessageData, ChatResponse, SourceMemory, SaveConversationResult, SummarizeChatResult, MemoryData } from '../native-client';

// Agent type for dropdown
interface Agent {
  id: number;
  name: string;
  description: string | null;
  system_prompt: string;
  is_enabled: boolean;
}

// Default Think agent (built-in)
const DEFAULT_AGENT: Agent = {
  id: 0,
  name: 'Think',
  description: 'Your intelligent personal assistant',
  system_prompt: '', // Uses default system prompt
  is_enabled: true,
};

// Helper to send messages via background script
function sendToBackground<T>(type: string, data: unknown): Promise<T> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type, data }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else if (response?.success) {
        resolve(response.result);
      } else {
        reject(new Error(response?.error || 'Unknown error'));
      }
    });
  });
}

// Send chat message via background script (content scripts can't use connectNative)
async function sendChatMessageViaBackground(data: ChatMessageData): Promise<ChatResponse> {
  return sendToBackground('CHAT_MESSAGE', data);
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

// Simple message actions component - only for assistant messages
function MessageActions({ message }: { message: Message }) {
  const [copied, setCopied] = useState(false);

  // Only show for assistant messages
  if (message.role === 'user') {
    return null;
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="absolute -top-2 right-0 flex gap-0.5 z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
      <button
        onClick={handleCopy}
        className="h-6 w-6 flex items-center justify-center rounded bg-background/80 backdrop-blur-sm text-muted-foreground hover:text-primary transition-colors"
        title="Copy message"
      >
        {copied ? (
          <Check className="h-3 w-3 text-green-500" />
        ) : (
          <Copy className="h-3 w-3" />
        )}
      </button>
    </div>
  );
}

interface ChatSidebarProps {
  pageContent: string;
  pageUrl: string;
  pageTitle: string;
  onClose: () => void;
}

// TTS Response type
interface TTSResponse {
  audio_base64: string;
  sample_rate: number;
  duration_seconds: number;
}

// STT Response type
interface STTResponse {
  text: string;
  timestamps?: Array<{ start: number; end: number; text: string }>;
  confidence?: number;
  analysis?: string;
}

export function ChatSidebar({ pageContent, pageUrl, pageTitle, onClose }: ChatSidebarProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceMemory[]>([]);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [showActions, setShowActions] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  // Page summary caching - store summary from first response for subsequent requests
  const [pageSummary, setPageSummary] = useState<string | null>(null);
  // Follow-up suggestions from LLM
  const [followupSuggestions, setFollowupSuggestions] = useState<string[]>([]);
  
  // Agent selection state
  const [agents, setAgents] = useState<Agent[]>([DEFAULT_AGENT]);
  const [selectedAgent, setSelectedAgent] = useState<Agent>(DEFAULT_AGENT);
  const [showAgentDropdown, setShowAgentDropdown] = useState(false);
  
  // Voice state
  const [readingMode, setReadingMode] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const currentAudioSourceRef = useRef<AudioBufferSourceNode | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Fetch available agents on mount
  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const result = await sendToBackground<{ agents: Agent[] }>('LIST_AGENTS', { enabled_only: true });
        if (result.agents && result.agents.length > 0) {
          setAgents([DEFAULT_AGENT, ...result.agents]);
        }
      } catch (err) {
        console.error('Failed to fetch agents:', err);
        // Keep default agent only
      }
    };
    fetchAgents();
  }, []);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setShowAgentDropdown(false);
      setShowActions(false);
    };
    
    if (showAgentDropdown || showActions) {
      // Delay to avoid immediate close on the click that opened it
      const timer = setTimeout(() => {
        document.addEventListener('click', handleClickOutside);
      }, 0);
      return () => {
        clearTimeout(timer);
        document.removeEventListener('click', handleClickOutside);
      };
    }
  }, [showAgentDropdown, showActions]);

  const sendMessage = async (messageText?: string) => {
    const userMessage = (messageText || input).trim();
    if (!userMessage || loading) return;

    setInput('');
    setError(null);
    setFollowupSuggestions([]); // Clear previous follow-ups
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const data: ChatMessageData = {
        message: userMessage,
        page_content: pageContent,
        page_url: pageUrl,
        page_title: pageTitle,
        history: messages,
        // Include cached page summary if available (frontend passback caching)
        ...(pageSummary && { page_summary: pageSummary }),
        // Include agent system prompt if using a custom agent
        ...(selectedAgent.id !== 0 && selectedAgent.system_prompt && { 
          agent_system_prompt: selectedAgent.system_prompt,
          agent_id: selectedAgent.id,
        }),
      };

      const response = await sendChatMessageViaBackground(data);
      setMessages(prev => [...prev, { role: 'assistant', content: response.response }]);

      // Cache page summary for subsequent requests (only returned on first message)
      if (response.page_summary) {
        setPageSummary(response.page_summary);
      }

      // Store follow-up suggestions
      if (response.followups?.length) {
        setFollowupSuggestions(response.followups);
      }

      // Accumulate unique sources
      if (response.sources?.length) {
        setSources(prev => {
          const existingIds = new Set(prev.map(s => s.id));
          const newSources = response.sources!.filter(s => !existingIds.has(s.id));
          return [...prev, ...newSources];
        });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to send message';
      // Check for native app connection errors specifically
      if (message.includes('Think app is not running') || message.includes('Native host')) {
        setError('Please open the Think app first');
      } else if (message.includes('Database not unlocked')) {
        setError('Please unlock the Think app first');
      } else if (message.includes('Connection refused') || message.includes('localhost:11434')) {
        setError('AI service not available. Please start Ollama or configure OpenAI.');
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const showSuccessTemporarily = (action: string) => {
    setActionSuccess(action);
    setTimeout(() => setActionSuccess(null), 2000);
  };

  const handleSaveToApp = async () => {
    if (messages.length === 0 || actionLoading) return;
    setActionLoading('saveToApp');
    try {
      await sendToBackground<SaveConversationResult>('SAVE_CONVERSATION', {
        messages,
        page_title: pageTitle,
        page_url: pageUrl,
      });
      showSuccessTemporarily('saveToApp');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save conversation');
    } finally {
      setActionLoading(null);
      setShowActions(false);
    }
  };

  const handleSavePage = async () => {
    if (actionLoading) return;
    setActionLoading('savePage');
    try {
      await sendToBackground('SAVE_MEMORY', {
        url: pageUrl,
        title: pageTitle,
        content: pageContent,
      });
      showSuccessTemporarily('savePage');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save page');
    } finally {
      setActionLoading(null);
      setShowActions(false);
    }
  };

  const handleSummarize = async () => {
    if (messages.length === 0 || actionLoading) return;
    setActionLoading('summarize');
    try {
      await sendToBackground<SummarizeChatResult>('SUMMARIZE_CHAT', {
        messages,
        page_title: pageTitle,
        page_url: pageUrl,
      });
      showSuccessTemporarily('summarize');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create summary');
    } finally {
      setActionLoading(null);
      setShowActions(false);
    }
  };

  // TTS: Speak text using backend TTS
  const speakText = useCallback(async (text: string) => {
    if (!text || isSpeaking) return;
    
    setIsSpeaking(true);
    try {
      const response = await sendToBackground<TTSResponse>('VOICE_TTS', { text });
      
      // Decode base64 audio and play it
      const audioData = atob(response.audio_base64);
      const audioArray = new Uint8Array(audioData.length);
      for (let i = 0; i < audioData.length; i++) {
        audioArray[i] = audioData.charCodeAt(i);
      }
      
      // Create audio context if needed
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext();
      }
      
      const audioBuffer = await audioContextRef.current.decodeAudioData(audioArray.buffer);
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      currentAudioSourceRef.current = source;
      
      source.onended = () => {
        setIsSpeaking(false);
        currentAudioSourceRef.current = null;
      };
      
      source.start();
    } catch (err) {
      console.error('TTS error:', err);
      setError(err instanceof Error ? err.message : 'Failed to speak');
      setIsSpeaking(false);
    }
  }, [isSpeaking]);

  // Stop speaking
  const stopSpeaking = useCallback(() => {
    if (currentAudioSourceRef.current) {
      currentAudioSourceRef.current.stop();
      currentAudioSourceRef.current = null;
    }
    setIsSpeaking(false);
  }, []);

  // STT: Start recording
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach(track => track.stop());
        
        // Convert to base64
        const reader = new FileReader();
        reader.onloadend = async () => {
          const base64 = (reader.result as string).split(',')[1];
          
          try {
            const response = await sendToBackground<STTResponse>('VOICE_STT', { 
              audio_base64: base64 
            });
            
            if (response.text) {
              setInput(prev => prev + (prev ? ' ' : '') + response.text);
              inputRef.current?.focus();
            }
          } catch (err) {
            console.error('STT error:', err);
            setError(err instanceof Error ? err.message : 'Failed to transcribe');
          }
        };
        reader.readAsDataURL(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Recording error:', err);
      setError('Microphone access denied');
    }
  }, []);

  // STT: Stop recording
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, [isRecording]);

  // Toggle recording
  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  // Auto-speak new assistant messages when reading mode is on
  useEffect(() => {
    if (readingMode && messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.role === 'assistant' && !loading) {
        speakText(lastMessage.content);
      }
    }
  }, [messages, readingMode, loading, speakText]);

  // Cleanup audio context on unmount
  useEffect(() => {
    return () => {
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  return (
    <div className="flex flex-col h-full bg-background text-foreground">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border">
        <div className="flex items-center gap-2">
          {/* Agent selector dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowAgentDropdown(!showAgentDropdown)}
              className="flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-secondary transition-colors text-sm"
              title={selectedAgent.description || selectedAgent.name}
            >
              <Bot className="w-4 h-4 text-primary" />
              <span className="font-medium max-w-[120px] truncate">{selectedAgent.name}</span>
              <ChevronDown className="w-3 h-3 text-muted-foreground" />
            </button>
            {showAgentDropdown && (
              <div className="absolute left-0 top-full mt-1 w-56 bg-white/70 dark:bg-white/5 backdrop-blur-xl border border-white/60 dark:border-white/10 rounded-lg shadow-lg shadow-black/10 dark:shadow-black/30 z-20 py-1 max-h-64 overflow-y-auto">
                {agents.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => {
                      setSelectedAgent(agent);
                      setShowAgentDropdown(false);
                    }}
                    className={`w-full flex flex-col items-start px-3 py-2 text-sm hover:bg-secondary transition-colors ${
                      selectedAgent.id === agent.id ? 'bg-primary/10' : ''
                    }`}
                  >
                    <span className="font-medium">{agent.name}</span>
                    {agent.description && (
                      <span className="text-xs text-muted-foreground truncate w-full text-left">
                        {agent.description}
                      </span>
                    )}
                  </button>
                ))}
                {agents.length === 1 && (
                  <div className="px-3 py-2 text-xs text-muted-foreground">
                    Create agents in the Think app
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          {/* Reading mode toggle */}
          <button
            onClick={() => {
              if (isSpeaking) stopSpeaking();
              setReadingMode(!readingMode);
            }}
            className={`p-1.5 rounded transition-colors ${readingMode ? 'bg-primary/20 text-primary' : 'hover:bg-secondary'}`}
            aria-label={readingMode ? 'Disable reading mode' : 'Enable reading mode'}
            title={readingMode ? 'Reading mode ON - AI responses will be spoken' : 'Enable reading mode'}
          >
            {isSpeaking ? (
              <Square className="w-4 h-4" />
            ) : readingMode ? (
              <Volume2 className="w-4 h-4" />
            ) : (
              <VolumeX className="w-4 h-4" />
            )}
          </button>
          
          {/* Actions menu */}
          <div className="relative">
            <button
              onClick={() => setShowActions(!showActions)}
              className="p-1.5 rounded hover:bg-secondary transition-colors"
              aria-label="Actions"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
            {showActions && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-white/70 dark:bg-white/5 backdrop-blur-xl border border-white/60 dark:border-white/10 rounded-lg shadow-lg shadow-black/10 dark:shadow-black/30 z-10 py-1">
                <button
                  onClick={handleSavePage}
                  disabled={!!actionLoading}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-secondary transition-colors disabled:opacity-50"
                >
                  {actionLoading === 'savePage' ? (
                    <div className="w-4 h-4 border-2 border-muted-foreground/30 border-t-muted-foreground rounded-full animate-spin" />
                  ) : actionSuccess === 'savePage' ? (
                    <Check className="w-4 h-4 text-green-500" />
                  ) : (
                    <Bookmark className="w-4 h-4" />
                  )}
                  <span>Save Page</span>
                </button>
                <button
                  onClick={handleSaveToApp}
                  disabled={messages.length === 0 || !!actionLoading}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-secondary transition-colors disabled:opacity-50"
                >
                  {actionLoading === 'saveToApp' ? (
                    <div className="w-4 h-4 border-2 border-muted-foreground/30 border-t-muted-foreground rounded-full animate-spin" />
                  ) : actionSuccess === 'saveToApp' ? (
                    <Check className="w-4 h-4 text-green-500" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  <span>Save Chat to App</span>
                </button>
                <button
                  onClick={handleSummarize}
                  disabled={messages.length === 0 || !!actionLoading}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-secondary transition-colors disabled:opacity-50"
                >
                  {actionLoading === 'summarize' ? (
                    <div className="w-4 h-4 border-2 border-muted-foreground/30 border-t-muted-foreground rounded-full animate-spin" />
                  ) : actionSuccess === 'summarize' ? (
                    <Check className="w-4 h-4 text-green-500" />
                  ) : (
                    <Sparkles className="w-4 h-4" />
                  )}
                  <span>Summarize & Save</span>
                </button>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-secondary transition-colors"
            aria-label="Close sidebar"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      {/* Page context indicator */}
      <div className="px-3 py-2 text-xs text-muted-foreground border-b border-border truncate">
        Chatting about: {pageTitle || pageUrl}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-muted-foreground text-sm py-8">
            Ask me anything about this page or your saved memories
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`group flex animate-slide-up ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className="relative max-w-[80%]">
              {/* Message actions */}
              <MessageActions message={msg} />

              {/* Message bubble */}
              <div
                className={`rounded-2xl p-4 ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-white/70 dark:bg-white/5 backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm shadow-black/5 dark:shadow-black/20 hover:shadow-lg hover:scale-[1.01] hover:-translate-y-0.5 transition-all duration-200'
                }`}
              >
                {msg.role === 'user' ? (
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                ) : (
                  <div className="chat-prose text-sm">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start animate-slide-up">
            <div className="bg-white/70 dark:bg-white/5 backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm shadow-black/5 dark:shadow-black/20 p-4 rounded-2xl">
              <span className="inline-block w-2 h-4 bg-current animate-pulse" />
            </div>
          </div>
        )}
        {error && (
          <div className="text-sm p-2 rounded-md text-center bg-destructive/10 text-destructive">
            {error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Sources panel */}
      {sources.length > 0 && (
        <div className="px-4 py-3 border-t border-border">
          <button
            onClick={() => setSourcesExpanded(!sourcesExpanded)}
            className="flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            <ChevronRight
              className={`h-3.5 w-3.5 transition-transform duration-200 ${sourcesExpanded ? "rotate-90" : ""}`}
            />
            <BookOpen className="h-3.5 w-3.5" />
            <span>Sources ({sources.length})</span>
          </button>
          <div
            className={`grid transition-[grid-template-rows] duration-200 ease-out ${sourcesExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
          >
            <div className="overflow-hidden">
              <div className="flex flex-wrap gap-2 pt-2">
                {sources.map((source) => (
                  <a
                    key={source.id}
                    href={source.url || `think://memories/${source.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-background rounded-md border hover:bg-accent transition-colors group"
                    title={source.title}
                  >
                    {source.url ? (
                      <ExternalLink className="h-3 w-3 text-muted-foreground group-hover:text-foreground transition-colors" />
                    ) : (
                      <FileText className="h-3 w-3 text-muted-foreground group-hover:text-foreground transition-colors" />
                    )}
                    <span className="truncate max-w-[200px]">{source.title}</span>
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Follow-up suggestions */}
      {followupSuggestions.length > 0 && !loading && (
        <div className="px-4 py-2 border-t border-border">
          <div className="flex flex-wrap gap-2">
            {followupSuggestions.map((suggestion, index) => (
              <button
                key={index}
                onClick={() => sendMessage(suggestion)}
                className="px-3 py-1.5 text-xs bg-white/70 dark:bg-white/5 backdrop-blur-md border border-white/60 dark:border-white/10 rounded-full hover:bg-accent hover:border-primary/30 transition-all duration-200 text-left max-w-full truncate"
                title={suggestion}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-border">
        <div className="relative flex items-center gap-2 p-2 rounded-full bg-white/70 dark:bg-white/5 backdrop-blur-xl border border-white/60 dark:border-white/10 shadow-lg shadow-black/5 dark:shadow-black/20">
          {/* Mic button */}
          <button
            onClick={toggleRecording}
            disabled={loading}
            className={`h-10 w-10 flex items-center justify-center rounded-full shrink-0 transition-colors ${
              isRecording 
                ? 'bg-destructive text-destructive-foreground animate-pulse' 
                : 'hover:bg-secondary text-muted-foreground hover:text-foreground'
            }`}
            aria-label={isRecording ? 'Stop recording' : 'Start voice input'}
            title={isRecording ? 'Stop recording' : 'Voice input'}
          >
            {isRecording ? (
              <MicOff className="h-4 w-4" />
            ) : (
              <Mic className="h-4 w-4" />
            )}
          </button>
          
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isRecording ? "Listening..." : "Ask about this page..."}
            disabled={loading || isRecording}
            className="flex-1 bg-transparent px-2 py-2 text-base placeholder:text-muted-foreground/60 focus:outline-none disabled:opacity-50"
          />
          <Button
            size="icon"
            className="h-10 w-10 rounded-full shrink-0"
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
