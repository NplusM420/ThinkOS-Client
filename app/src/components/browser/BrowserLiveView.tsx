import { useState, useEffect, useRef, useCallback } from "react";
import {
  Globe,
  MousePointer,
  Type,
  Camera,
  Play,
  Square,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  Loader2,
  AlertCircle,
  CheckCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface PageElement {
  selector: string;
  tag: string;
  text: string | null;
  is_clickable: boolean;
  bounding_box?: { x: number; y: number; width: number; height: number } | null;
}

interface BrowserState {
  url: string;
  title: string;
  status: 'idle' | 'running' | 'failed';
  elements: PageElement[];
  screenshotPath?: string;
}

interface AgentStep {
  step_number: number;
  reasoning: string;
  action: string;
  params: Record<string, unknown>;
  result?: Record<string, unknown>;
  screenshot_path?: string;
  timestamp: string;
}

interface BrowserLiveViewProps {
  sessionId?: string;
  onClose?: () => void;
}

export function BrowserLiveView({ sessionId, onClose }: BrowserLiveViewProps) {
  const [browserState, setBrowserState] = useState<BrowserState | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [urlInput, setUrlInput] = useState('');
  const [agentTask, setAgentTask] = useState('');
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
  const [isAgentRunning, setIsAgentRunning] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const stepsEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    stepsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [agentSteps, scrollToBottom]);

  const connectToSession = useCallback((sid: string) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket(`ws://localhost:8765/ws/browser/${sid}`);
    
    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
      ws.send(JSON.stringify({ type: 'get_state' }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'page_state') {
        setBrowserState({
          url: data.url,
          title: data.title,
          status: 'idle',
          elements: data.elements || [],
        });
      } else if (data.type === 'session_status') {
        setBrowserState((prev) => prev ? {
          ...prev,
          url: data.url || prev.url,
          title: data.title || prev.title,
          status: data.status,
        } : null);
      } else if (data.type === 'action_result') {
        setIsLoading(false);
        if (!data.success) {
          setError(data.error || 'Action failed');
        }
      } else if (data.type === 'error') {
        setError(data.error);
        setIsLoading(false);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    ws.onerror = () => {
      setError('WebSocket connection failed');
      setIsConnected(false);
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    if (sessionId) {
      connectToSession(sessionId);
    }

    return () => {
      wsRef.current?.close();
    };
  }, [sessionId, connectToSession]);

  const sendAction = (action: string, params: Record<string, unknown> = {}) => {
    if (!wsRef.current || !isConnected) return;
    
    setIsLoading(true);
    setError(null);
    wsRef.current.send(JSON.stringify({
      type: 'action',
      action,
      ...params,
    }));
  };

  const handleNavigate = () => {
    if (!urlInput) return;
    sendAction('navigate', { url: urlInput });
  };

  const handleRefresh = () => {
    if (browserState?.url) {
      sendAction('navigate', { url: browserState.url });
    }
  };

  const handleScreenshot = () => {
    sendAction('screenshot');
  };

  const handleElementClick = (selector: string) => {
    sendAction('click', { selector, screenshot: true });
  };

  const startAgentTask = async () => {
    if (!agentTask.trim()) return;
    
    setIsAgentRunning(true);
    setAgentSteps([]);
    setError(null);

    const taskId = Date.now().toString();
    const ws = new WebSocket(`ws://localhost:8765/ws/browser-agent/${taskId}`);

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'start',
        task: agentTask,
        start_url: browserState?.url,
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'step') {
        setAgentSteps((prev) => [...prev, data as AgentStep]);
      } else if (data.type === 'complete') {
        setIsAgentRunning(false);
        ws.close();
      } else if (data.type === 'error') {
        setError(data.error);
        setIsAgentRunning(false);
        ws.close();
      }
    };

    ws.onerror = () => {
      setError('Agent connection failed');
      setIsAgentRunning(false);
    };

    ws.onclose = () => {
      setIsAgentRunning(false);
    };
  };

  const stopAgent = () => {
    setIsAgentRunning(false);
  };

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b">
        <Globe className="h-5 w-5 text-muted-foreground" />
        <h2 className="font-semibold">Browser Live View</h2>
        <div className="flex-1" />
        <div className={cn(
          "h-2 w-2 rounded-full",
          isConnected ? "bg-green-500" : "bg-red-500"
        )} />
        <span className="text-xs text-muted-foreground">
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {/* URL Bar */}
      <div className="flex items-center gap-2 p-2 border-b bg-muted/30">
        <Button
          variant="ghost"
          size="icon"
          onClick={handleRefresh}
          disabled={!isConnected || isLoading}
        >
          <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
        </Button>
        <Input
          value={urlInput || browserState?.url || ''}
          onChange={(e) => setUrlInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleNavigate()}
          placeholder="Enter URL..."
          className="flex-1 h-8"
        />
        <Button
          variant="ghost"
          size="icon"
          onClick={handleNavigate}
          disabled={!isConnected || !urlInput}
        >
          <ExternalLink className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleScreenshot}
          disabled={!isConnected}
        >
          <Camera className="h-4 w-4" />
        </Button>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Page Elements Panel */}
        <div className="w-64 border-r overflow-y-auto">
          <div className="p-2 border-b bg-muted/30">
            <h3 className="text-sm font-medium flex items-center gap-2">
              <MousePointer className="h-4 w-4" />
              Interactive Elements
            </h3>
          </div>
          <div className="p-2 space-y-1">
            {browserState?.elements.map((el, i) => (
              <button
                key={i}
                onClick={() => handleElementClick(el.selector)}
                className="w-full text-left p-2 rounded hover:bg-muted text-xs group"
                disabled={!isConnected}
              >
                <div className="flex items-center gap-1">
                  <span className="text-muted-foreground">&lt;{el.tag}&gt;</span>
                  {el.is_clickable && (
                    <MousePointer className="h-3 w-3 text-blue-500" />
                  )}
                </div>
                {el.text && (
                  <div className="truncate text-foreground mt-0.5">
                    {el.text}
                  </div>
                )}
                <div className="text-muted-foreground truncate opacity-0 group-hover:opacity-100 transition-opacity">
                  {el.selector}
                </div>
              </button>
            ))}
            {(!browserState?.elements || browserState.elements.length === 0) && (
              <div className="text-center text-muted-foreground text-sm py-4">
                No elements detected
              </div>
            )}
          </div>
        </div>

        {/* Agent Panel */}
        <div className="flex-1 flex flex-col">
          {/* Agent Task Input */}
          <div className="p-3 border-b">
            <div className="flex items-center gap-2">
              <Input
                value={agentTask}
                onChange={(e) => setAgentTask(e.target.value)}
                placeholder="Describe what you want the browser to do..."
                className="flex-1"
                disabled={isAgentRunning}
              />
              {isAgentRunning ? (
                <Button variant="outline" size="sm" onClick={stopAgent} className="text-red-500 border-red-500 hover:bg-red-500/10">
                  <Square className="h-4 w-4 mr-1" />
                  Stop
                </Button>
              ) : (
                <Button size="sm" onClick={startAgentTask} disabled={!agentTask.trim()}>
                  <Play className="h-4 w-4 mr-1" />
                  Run Agent
                </Button>
              )}
            </div>
          </div>

          {/* Agent Steps */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {agentSteps.map((step, i) => (
              <div
                key={i}
                className={cn(
                  "rounded-lg border p-3",
                  step.action === 'done' && "border-green-500/50 bg-green-500/5",
                  step.action === 'fail' && "border-red-500/50 bg-red-500/5"
                )}
              >
                <div className="flex items-center gap-2 mb-2">
                  <div className="h-6 w-6 rounded-full bg-primary/10 flex items-center justify-center text-xs font-medium">
                    {step.step_number}
                  </div>
                  <span className="font-medium capitalize">{step.action}</span>
                  {step.action === 'done' && <CheckCircle className="h-4 w-4 text-green-500" />}
                  {step.action === 'fail' && <AlertCircle className="h-4 w-4 text-red-500" />}
                  <span className="text-xs text-muted-foreground ml-auto">
                    {new Date(step.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                
                {step.reasoning && (
                  <div className="text-sm text-muted-foreground mb-2">
                    <ChevronRight className="h-3 w-3 inline mr-1" />
                    {step.reasoning}
                  </div>
                )}

                {Object.keys(step.params).length > 0 && (
                  <div className="text-xs bg-muted/50 rounded p-2 font-mono">
                    {JSON.stringify(step.params, null, 2)}
                  </div>
                )}

                {step.result && (
                  <div className="mt-2 text-xs">
                    <span className="text-muted-foreground">Result: </span>
                    {step.result.success ? (
                      <span className="text-green-600">Success</span>
                    ) : (
                      <span className="text-red-600">{String(step.result.error)}</span>
                    )}
                  </div>
                )}
              </div>
            ))}

            {isAgentRunning && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">Agent is working...</span>
              </div>
            )}

            {agentSteps.length === 0 && !isAgentRunning && (
              <div className="text-center text-muted-foreground py-8">
                <Type className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>Enter a task above to start the browser agent</p>
                <p className="text-xs mt-1">
                  Example: "Search for the latest news about AI"
                </p>
              </div>
            )}

            <div ref={stepsEndRef} />
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-2 bg-destructive/10 border-t border-destructive/20 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-destructive" />
          <span className="text-sm text-destructive">{error}</span>
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={() => setError(null)}
          >
            Dismiss
          </Button>
        </div>
      )}

      {/* Status Bar */}
      <div className="flex items-center gap-4 px-3 py-1.5 border-t bg-muted/30 text-xs text-muted-foreground">
        <span>{browserState?.title || 'No page loaded'}</span>
        <span className="ml-auto">{browserState?.url || ''}</span>
      </div>
    </div>
  );
}

export default BrowserLiveView;
