/**
 * Voice button component for recording and transcribing audio.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Mic, MicOff, Loader2, Square, AlertCircle, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAudioRecorder, formatDuration } from "@/hooks/useAudioRecorder";
import { transcribeAudio, executeVoiceCommand, synthesizeSpeech } from "@/lib/api/voice";
import type { VoiceCommandResponse } from "@/lib/api/voice";

export interface VoiceButtonProps {
  onTranscription: (text: string) => void;
  onError?: (error: string) => void;
  disabled?: boolean;
  className?: string;
  size?: "sm" | "default" | "lg";
}

export function VoiceButton({
  onTranscription,
  onError,
  disabled = false,
  className,
  size = "default",
}: VoiceButtonProps) {
  const [recorderState, controls] = useAudioRecorder();
  const [isTranscribing, setIsTranscribing] = useState(false);

  const { isRecording, duration, error: recorderError } = recorderState;

  // Handle recorder errors
  useEffect(() => {
    if (recorderError) {
      onError?.(recorderError);
    }
  }, [recorderError, onError]);

  const handleClick = async () => {
    if (isRecording) {
      // Stop recording and transcribe
      const blob = await controls.stopRecording();
      if (blob) {
        await handleTranscribe();
      }
    } else {
      // Start recording
      await controls.startRecording();
    }
  };

  const handleTranscribe = async () => {
    setIsTranscribing(true);
    try {
      const audioBase64 = await controls.getAudioBase64();
      if (!audioBase64) {
        onError?.("No audio recorded");
        return;
      }

      const response = await transcribeAudio({
        audio_base64: audioBase64,
      });

      onTranscription(response.text);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Transcription failed";
      onError?.(message);
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleCancel = () => {
    controls.cancelRecording();
  };

  const iconSize = size === "sm" ? "h-4 w-4" : size === "lg" ? "h-6 w-6" : "h-5 w-5";
  const buttonSize = size === "sm" ? "h-8 w-8" : size === "lg" ? "h-12 w-12" : "h-10 w-10";

  if (isTranscribing) {
    return (
      <Button
        variant="outline"
        size="icon"
        disabled
        className={cn(buttonSize, "rounded-full", className)}
      >
        <Loader2 className={cn(iconSize, "animate-spin")} />
      </Button>
    );
  }

  if (isRecording) {
    return (
      <div className="flex items-center gap-2">
        <Button
          variant="default"
          size="icon"
          onClick={handleClick}
          className={cn(buttonSize, "rounded-full animate-pulse bg-red-500 hover:bg-red-600", className)}
        >
          <Square className={iconSize} />
        </Button>
        <span className="text-sm font-mono text-muted-foreground">
          {formatDuration(duration)}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCancel}
          className="text-xs"
        >
          Cancel
        </Button>
      </div>
    );
  }

  return (
    <Button
      variant="outline"
      size="icon"
      onClick={handleClick}
      disabled={disabled}
      className={cn(
        buttonSize,
        "rounded-full hover:bg-primary hover:text-primary-foreground transition-colors",
        className
      )}
    >
      <Mic className={iconSize} />
    </Button>
  );
}

/**
 * Compact voice input that shows inline with text input.
 */
export interface VoiceInputProps {
  onTranscription: (text: string) => void;
  onError?: (error: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function VoiceInput({
  onTranscription,
  onError,
  disabled = false,
  placeholder = "Click to speak...",
}: VoiceInputProps) {
  const [recorderState, controls] = useAudioRecorder();
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcribedText, setTranscribedText] = useState("");

  const { isRecording, duration, error: recorderError } = recorderState;

  useEffect(() => {
    if (recorderError) {
      onError?.(recorderError);
    }
  }, [recorderError, onError]);

  const handleStartRecording = async () => {
    setTranscribedText("");
    await controls.startRecording();
  };

  const handleStopRecording = async () => {
    const blob = await controls.stopRecording();
    if (blob) {
      setIsTranscribing(true);
      try {
        const audioBase64 = await controls.getAudioBase64();
        if (audioBase64) {
          const response = await transcribeAudio({
            audio_base64: audioBase64,
          });
          setTranscribedText(response.text);
          onTranscription(response.text);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Transcription failed";
        onError?.(message);
      } finally {
        setIsTranscribing(false);
      }
    }
  };

  return (
    <div
      className={cn(
        "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
        isRecording
          ? "bg-destructive/10 border-destructive"
          : "bg-muted/50 hover:bg-muted",
        disabled && "opacity-50 cursor-not-allowed"
      )}
      onClick={disabled ? undefined : isRecording ? handleStopRecording : handleStartRecording}
    >
      <div
        className={cn(
          "flex items-center justify-center w-10 h-10 rounded-full",
          isRecording
            ? "bg-destructive text-destructive-foreground animate-pulse"
            : "bg-primary/10 text-primary"
        )}
      >
        {isTranscribing ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : isRecording ? (
          <Square className="h-5 w-5" />
        ) : (
          <Mic className="h-5 w-5" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        {isTranscribing ? (
          <p className="text-sm text-muted-foreground">Transcribing...</p>
        ) : isRecording ? (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Recording</span>
            <span className="text-sm font-mono text-muted-foreground">
              {formatDuration(duration)}
            </span>
          </div>
        ) : transcribedText ? (
          <p className="text-sm truncate">{transcribedText}</p>
        ) : (
          <p className="text-sm text-muted-foreground">{placeholder}</p>
        )}
      </div>

      {recorderError && (
        <AlertCircle className="h-4 w-4 text-destructive flex-shrink-0" />
      )}
    </div>
  );
}

/**
 * Voice command button that records, transcribes, executes commands, and speaks responses.
 */
export interface VoiceCommandButtonProps {
  onCommandResult?: (result: VoiceCommandResponse) => void;
  onError?: (error: string) => void;
  speakResponse?: boolean;
  disabled?: boolean;
  className?: string;
  size?: "sm" | "default" | "lg";
}

export function VoiceCommandButton({
  onCommandResult,
  onError,
  speakResponse = true,
  disabled = false,
  className,
  size = "default",
}: VoiceCommandButtonProps) {
  const navigate = useNavigate();
  const [recorderState, controls] = useAudioRecorder();
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [lastResponse, setLastResponse] = useState<string | null>(null);

  const { isRecording, duration, error: recorderError } = recorderState;

  useEffect(() => {
    if (recorderError) {
      onError?.(recorderError);
    }
  }, [recorderError, onError]);

  const handleClick = async () => {
    if (isRecording) {
      const blob = await controls.stopRecording();
      if (blob) {
        await handleCommand();
      }
    } else {
      setLastResponse(null);
      await controls.startRecording();
    }
  };

  const handleCommand = async () => {
    setIsProcessing(true);
    try {
      const audioBase64 = await controls.getAudioBase64();
      if (!audioBase64) {
        onError?.("No audio recorded");
        return;
      }

      // Execute voice command (transcribes + executes)
      const result = await executeVoiceCommand({
        text: "",
        audio_base64: audioBase64,
      });

      setLastResponse(result.speak_response || result.message);
      onCommandResult?.(result);

      // Handle navigation if needed
      if (result.navigate_to) {
        navigate(result.navigate_to);
      }

      // Speak response if enabled
      if (speakResponse && result.speak_response) {
        await speakText(result.speak_response);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Command failed";
      onError?.(message);
      setLastResponse(message);
    } finally {
      setIsProcessing(false);
    }
  };

  const speakText = async (text: string) => {
    setIsSpeaking(true);
    try {
      const response = await synthesizeSpeech({ text });
      
      // Play audio
      const audioData = `data:audio/wav;base64,${response.audio_base64}`;
      const audio = new Audio(audioData);
      await audio.play();
      
      // Wait for audio to finish
      await new Promise((resolve) => {
        audio.onended = resolve;
      });
    } catch (err) {
      console.error("TTS failed:", err);
    } finally {
      setIsSpeaking(false);
    }
  };

  const handleCancel = () => {
    controls.cancelRecording();
  };

  const iconSize = size === "sm" ? "h-4 w-4" : size === "lg" ? "h-6 w-6" : "h-5 w-5";
  const buttonSize = size === "sm" ? "h-8 w-8" : size === "lg" ? "h-12 w-12" : "h-10 w-10";

  if (isProcessing) {
    return (
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="icon"
          disabled
          className={cn(buttonSize, "rounded-full", className)}
        >
          <Loader2 className={cn(iconSize, "animate-spin")} />
        </Button>
        <span className="text-sm text-muted-foreground">Processing...</span>
      </div>
    );
  }

  if (isSpeaking) {
    return (
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="icon"
          disabled
          className={cn(buttonSize, "rounded-full", className)}
        >
          <Volume2 className={cn(iconSize, "animate-pulse")} />
        </Button>
        <span className="text-sm text-muted-foreground">Speaking...</span>
      </div>
    );
  }

  if (isRecording) {
    return (
      <div className="flex items-center gap-2">
        <Button
          variant="default"
          size="icon"
          onClick={handleClick}
          className={cn(buttonSize, "rounded-full animate-pulse bg-red-500 hover:bg-red-600", className)}
        >
          <Square className={iconSize} />
        </Button>
        <span className="text-sm font-mono text-muted-foreground">
          {formatDuration(duration)}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCancel}
          className="text-xs"
        >
          Cancel
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="icon"
        onClick={handleClick}
        disabled={disabled}
        className={cn(
          buttonSize,
          "rounded-full hover:bg-primary hover:text-primary-foreground transition-colors",
          className
        )}
      >
        <Mic className={iconSize} />
      </Button>
      {lastResponse && (
        <span className="text-sm text-muted-foreground truncate max-w-[200px]">
          {lastResponse}
        </span>
      )}
    </div>
  );
}
