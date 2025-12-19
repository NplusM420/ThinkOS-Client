/**
 * Memory viewer component for displaying different content types.
 */

import { useState } from "react";
import {
  FileImage,
  FileAudio,
  FileVideo,
  FileText,
  File,
  Download,
  ExternalLink,
  Play,
  Pause,
  Volume2,
  Maximize2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Attachment } from "@/types/attachment";
import { getAttachmentType, formatFileSize, formatDuration } from "@/types/attachment";

export interface MemoryViewerProps {
  attachment: Attachment;
  className?: string;
  showControls?: boolean;
  onClose?: () => void;
}

export function MemoryViewer({
  attachment,
  className,
  showControls = true,
  onClose,
}: MemoryViewerProps) {
  const type = getAttachmentType(attachment.mime_type);

  return (
    <div className={cn("relative", className)}>
      {showControls && onClose && (
        <Button
          variant="ghost"
          size="icon"
          className="absolute top-2 right-2 z-10 bg-background/80 backdrop-blur-sm"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      )}

      {type === "image" && <ImageViewer attachment={attachment} />}
      {type === "audio" && <AudioViewer attachment={attachment} />}
      {type === "video" && <VideoViewer attachment={attachment} />}
      {type === "pdf" && <PDFViewer attachment={attachment} />}
      {(type === "document" || type === "other") && (
        <DocumentViewer attachment={attachment} />
      )}

      {showControls && (
        <div className="flex items-center justify-between mt-2 px-1">
          <div className="text-sm text-muted-foreground">
            {attachment.filename} • {formatFileSize(attachment.size_bytes)}
          </div>
          <a 
            href={attachment.url} 
            download={attachment.filename}
            className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:bg-accent hover:text-accent-foreground h-9 px-3"
          >
            <Download className="h-4 w-4 mr-1" />
            Download
          </a>
        </div>
      )}
    </div>
  );
}

/**
 * Image viewer with zoom and fullscreen.
 */
function ImageViewer({ attachment }: { attachment: Attachment }) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  return (
    <>
      <div className="relative group">
        <img
          src={attachment.url}
          alt={attachment.filename}
          className="w-full h-auto rounded-lg object-contain max-h-[500px]"
        />
        <Button
          variant="ghost"
          size="icon"
          className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-background/80 backdrop-blur-sm"
          onClick={() => setIsFullscreen(true)}
        >
          <Maximize2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
          onClick={() => setIsFullscreen(false)}
        >
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-4 right-4 text-white hover:bg-white/20"
            onClick={() => setIsFullscreen(false)}
          >
            <X className="h-6 w-6" />
          </Button>
          <img
            src={attachment.url}
            alt={attachment.filename}
            className="max-w-[90vw] max-h-[90vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* Description/OCR text */}
      {(attachment.description || attachment.extracted_text) && (
        <div className="mt-3 p-3 rounded-lg bg-muted/50 text-sm">
          {attachment.description && (
            <p className="text-muted-foreground">{attachment.description}</p>
          )}
          {attachment.extracted_text && (
            <div className="mt-2">
              <p className="text-xs font-medium text-muted-foreground mb-1">
                Extracted Text:
              </p>
              <p className="whitespace-pre-wrap">{attachment.extracted_text}</p>
            </div>
          )}
        </div>
      )}
    </>
  );
}

/**
 * Audio player with waveform visualization.
 */
function AudioViewer({ attachment }: { attachment: Attachment }) {
  const [isPlaying, setIsPlaying] = useState(false);

  return (
    <div className="p-4 rounded-lg bg-muted/30">
      <div className="flex items-center gap-4">
        {attachment.thumbnail_url ? (
          <img
            src={attachment.thumbnail_url}
            alt="Waveform"
            className="w-full h-16 rounded object-cover"
          />
        ) : (
          <div className="flex items-center justify-center w-16 h-16 rounded-lg bg-primary/10">
            <FileAudio className="h-8 w-8 text-primary" />
          </div>
        )}
      </div>

      <audio
        src={attachment.url}
        controls
        className="w-full mt-3"
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />

      {attachment.duration_seconds && (
        <p className="text-xs text-muted-foreground mt-2">
          Duration: {formatDuration(attachment.duration_seconds)}
        </p>
      )}

      {/* Transcription */}
      {attachment.extracted_text && (
        <div className="mt-3 p-3 rounded-lg bg-background text-sm">
          <p className="text-xs font-medium text-muted-foreground mb-1">
            Transcription:
          </p>
          <p className="whitespace-pre-wrap">{attachment.extracted_text}</p>
        </div>
      )}
    </div>
  );
}

/**
 * Video player.
 */
function VideoViewer({ attachment }: { attachment: Attachment }) {
  return (
    <div>
      <video
        src={attachment.url}
        controls
        className="w-full rounded-lg max-h-[500px]"
        poster={attachment.thumbnail_url || undefined}
      />

      {attachment.duration_seconds && (
        <p className="text-xs text-muted-foreground mt-2">
          Duration: {formatDuration(attachment.duration_seconds)}
        </p>
      )}
    </div>
  );
}

/**
 * PDF viewer with embedded preview.
 */
function PDFViewer({ attachment }: { attachment: Attachment }) {
  const [showFullPDF, setShowFullPDF] = useState(false);

  return (
    <div>
      {/* Thumbnail preview */}
      <div
        className="relative cursor-pointer group"
        onClick={() => setShowFullPDF(true)}
      >
        {attachment.thumbnail_url ? (
          <img
            src={attachment.thumbnail_url}
            alt="PDF preview"
            className="w-full h-auto rounded-lg border"
          />
        ) : (
          <div className="flex items-center justify-center h-48 rounded-lg bg-muted/50 border">
            <FileText className="h-16 w-16 text-muted-foreground" />
          </div>
        )}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/50 rounded-lg">
          <Button variant="secondary">
            <ExternalLink className="h-4 w-4 mr-2" />
            View PDF
          </Button>
        </div>
      </div>

      {attachment.description && (
        <p className="text-sm text-muted-foreground mt-2">
          {attachment.description}
        </p>
      )}

      {/* Extracted text preview */}
      {attachment.extracted_text && (
        <div className="mt-3 p-3 rounded-lg bg-muted/50 text-sm max-h-[300px] overflow-y-auto">
          <p className="text-xs font-medium text-muted-foreground mb-1">
            Extracted Text:
          </p>
          <p className="whitespace-pre-wrap">{attachment.extracted_text}</p>
        </div>
      )}

      {/* Full PDF Modal */}
      {showFullPDF && (
        <div className="fixed inset-0 z-50 bg-black/90 flex flex-col">
          <div className="flex items-center justify-between p-4 bg-background/80 backdrop-blur-sm">
            <span className="font-medium">{attachment.filename}</span>
            <div className="flex gap-2">
              <a 
                href={attachment.url} 
                download={attachment.filename}
                className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-9 px-3"
              >
                <Download className="h-4 w-4 mr-1" />
                Download
              </a>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowFullPDF(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <iframe
            src={attachment.url}
            className="flex-1 w-full"
            title={attachment.filename}
          />
        </div>
      )}
    </div>
  );
}

/**
 * Generic document/file viewer.
 */
function DocumentViewer({ attachment }: { attachment: Attachment }) {
  return (
    <div className="p-6 rounded-lg bg-muted/30 text-center">
      <File className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
      <p className="font-medium">{attachment.filename}</p>
      <p className="text-sm text-muted-foreground mt-1">
        {attachment.mime_type} • {formatFileSize(attachment.size_bytes)}
      </p>

      {attachment.extracted_text && (
        <div className="mt-4 p-3 rounded-lg bg-background text-sm text-left max-h-[300px] overflow-y-auto">
          <p className="whitespace-pre-wrap">{attachment.extracted_text}</p>
        </div>
      )}

      <a 
        href={attachment.url} 
        download={attachment.filename}
        className="mt-4 inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2"
      >
        <Download className="h-4 w-4 mr-2" />
        Download File
      </a>
    </div>
  );
}

/**
 * Compact attachment card for lists.
 */
export interface AttachmentCardProps {
  attachment: Attachment;
  onClick?: () => void;
  onDelete?: () => void;
  className?: string;
}

export function AttachmentCard({
  attachment,
  onClick,
  onDelete,
  className,
}: AttachmentCardProps) {
  const type = getAttachmentType(attachment.mime_type);

  const getIcon = () => {
    switch (type) {
      case "image":
        return FileImage;
      case "audio":
        return FileAudio;
      case "video":
        return FileVideo;
      case "pdf":
      case "document":
        return FileText;
      default:
        return File;
    }
  };

  const Icon = getIcon();

  return (
    <div
      className={cn(
        "flex items-center gap-3 p-3 rounded-lg border bg-card hover:bg-muted/50 transition-colors cursor-pointer",
        className
      )}
      onClick={onClick}
    >
      {/* Thumbnail or Icon */}
      {attachment.thumbnail_url ? (
        <img
          src={attachment.thumbnail_url}
          alt={attachment.filename}
          className="w-12 h-12 rounded object-cover"
        />
      ) : (
        <div className="flex items-center justify-center w-12 h-12 rounded bg-muted">
          <Icon className="h-6 w-6 text-muted-foreground" />
        </div>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{attachment.filename}</p>
        <p className="text-xs text-muted-foreground">
          {formatFileSize(attachment.size_bytes)}
          {attachment.duration_seconds &&
            ` • ${formatDuration(attachment.duration_seconds)}`}
          {attachment.width &&
            attachment.height &&
            ` • ${attachment.width}×${attachment.height}`}
        </p>
      </div>

      {/* Actions */}
      {onDelete && (
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          <X className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
