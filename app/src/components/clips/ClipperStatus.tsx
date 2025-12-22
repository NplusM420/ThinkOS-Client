/**
 * ClipperStatus component - displays Clipper connection status and credit balance.
 */

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  Coins,
  RefreshCw,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/constants";

interface ClipperHealth {
  connected: boolean;
  api_url: string;
  api_key_configured: boolean;
  api_key_name?: string;
  auto_save_clips?: boolean;
  account?: {
    credit_balance: number;
    minimum_required: number;
    can_generate_clips: boolean;
  };
  features?: {
    platforms: string[];
    max_clips: number;
    include_captions: boolean;
    webhooks: boolean;
  };
  service_version?: string;
}

interface ClipperStatusProps {
  className?: string;
  onStatusChange?: (connected: boolean) => void;
}

export function ClipperStatus({ className, onStatusChange }: ClipperStatusProps) {
  const [status, setStatus] = useState<ClipperHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async (refresh = false) => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE_URL}/api/plugins/clippy-integration/tools/clippy_status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ params: { refresh } }),
      });

      if (!response.ok) {
        throw new Error("Failed to check Clipper status");
      }

      const data = await response.json();
      
      if (data.success) {
        setStatus(data.result);
        onStatusChange?.(data.result.connected);
      } else {
        setError(data.error || "Unknown error");
        setStatus(data.result || null);
        onStatusChange?.(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
      onStatusChange?.(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  if (loading && !status) {
    return (
      <div className={cn("flex items-center gap-2 text-sm text-muted-foreground", className)}>
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Checking Clipper connection...</span>
      </div>
    );
  }

  if (error && !status?.api_key_configured) {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <AlertCircle className="h-4 w-4 text-amber-500" />
          <span className="text-sm text-amber-600 dark:text-amber-400">
            Clipper not configured
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={() => window.location.href = "/settings?tab=plugins&plugin=clippy-integration"}
          >
            Configure
            <ExternalLink className="h-3 w-3 ml-1" />
          </Button>
        </div>
      </div>
    );
  }

  if (error || !status?.connected) {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20">
          <XCircle className="h-4 w-4 text-red-500" />
          <span className="text-sm text-red-600 dark:text-red-400">
            {error || "Disconnected"}
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2"
            onClick={() => fetchStatus(true)}
            disabled={loading}
          >
            <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
          </Button>
        </div>
      </div>
    );
  }

  const account = status.account;
  const canGenerate = account?.can_generate_clips ?? false;
  const balance = account?.credit_balance ?? 0;
  const minRequired = account?.minimum_required ?? 100;

  return (
    <div className={cn("flex items-center gap-3", className)}>
      {/* Connection status */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-500/10 border border-green-500/20">
        <CheckCircle2 className="h-4 w-4 text-green-500" />
        <span className="text-sm text-green-600 dark:text-green-400">
          Connected
        </span>
        {status.api_key_name && (
          <span className="text-xs text-muted-foreground">
            as {status.api_key_name}
          </span>
        )}
      </div>

      {/* Credit balance */}
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-lg border",
          canGenerate
            ? "bg-primary/10 border-primary/20"
            : "bg-amber-500/10 border-amber-500/20"
        )}
      >
        <Coins className={cn("h-4 w-4", canGenerate ? "text-primary" : "text-amber-500")} />
        <span
          className={cn(
            "text-sm font-medium",
            canGenerate ? "text-primary" : "text-amber-600 dark:text-amber-400"
          )}
        >
          {balance.toLocaleString()} credits
        </span>
        {!canGenerate && (
          <>
            <span className="text-xs text-muted-foreground">
              (need {minRequired})
            </span>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs text-amber-600 hover:text-amber-700"
              onClick={() => {
                // Open Clipper credits page
                const clipperUrl = status.api_url || "http://localhost:5000";
                window.open(`${clipperUrl}/settings?tab=credits`, "_blank");
              }}
            >
              Add Credits
              <ExternalLink className="h-3 w-3 ml-1" />
            </Button>
          </>
        )}
      </div>

      {/* Refresh button */}
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={() => fetchStatus(true)}
        disabled={loading}
        title="Refresh status"
      >
        <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
      </Button>
    </div>
  );
}

export default ClipperStatus;
