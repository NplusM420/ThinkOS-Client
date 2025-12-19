/**
 * File upload component for multi-modal memory.
 */

import { useState, useRef, useCallback } from "react";
import {
  Upload,
  X,
  FileImage,
  FileAudio,
  FileVideo,
  FileText,
  File,
  Loader2,
  Check,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { uploadFile } from "@/lib/api/attachments";
import type { Attachment, UploadResponse } from "@/types/attachment";
import { getAttachmentType, formatFileSize } from "@/types/attachment";

export interface FileUploadProps {
  onUploadComplete?: (response: UploadResponse) => void;
  onError?: (error: string) => void;
  memoryId?: number;
  createMemory?: boolean;
  processContent?: boolean;
  accept?: string;
  maxSize?: number; // in bytes
  multiple?: boolean;
  className?: string;
}

interface UploadingFile {
  file: File;
  progress: number;
  status: "pending" | "uploading" | "complete" | "error";
  error?: string;
  attachment?: Attachment;
}

export function FileUpload({
  onUploadComplete,
  onError,
  memoryId,
  createMemory = true,
  processContent = true,
  accept,
  maxSize = 100 * 1024 * 1024, // 100MB default
  multiple = false,
  className,
}: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const fileArray = Array.from(files);

      // Validate files
      const validFiles: File[] = [];
      for (const file of fileArray) {
        if (file.size > maxSize) {
          onError?.(`File "${file.name}" exceeds maximum size of ${formatFileSize(maxSize)}`);
          continue;
        }
        validFiles.push(file);
      }

      if (validFiles.length === 0) return;

      // Add to uploading list
      const newUploading: UploadingFile[] = validFiles.map((file) => ({
        file,
        progress: 0,
        status: "pending",
      }));

      setUploadingFiles((prev) => [...prev, ...newUploading]);

      // Upload each file
      for (let i = 0; i < validFiles.length; i++) {
        const file = validFiles[i];
        const index = uploadingFiles.length + i;

        setUploadingFiles((prev) =>
          prev.map((f, idx) =>
            idx === index ? { ...f, status: "uploading", progress: 10 } : f
          )
        );

        try {
          const response = await uploadFile(file, {
            memoryId,
            createMemory,
            processContent,
          });

          setUploadingFiles((prev) =>
            prev.map((f, idx) =>
              idx === index
                ? {
                    ...f,
                    status: "complete",
                    progress: 100,
                    attachment: response.attachment,
                  }
                : f
            )
          );

          onUploadComplete?.(response);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Upload failed";
          setUploadingFiles((prev) =>
            prev.map((f, idx) =>
              idx === index ? { ...f, status: "error", error: message } : f
            )
          );
          onError?.(message);
        }
      }
    },
    [maxSize, memoryId, createMemory, processContent, onUploadComplete, onError, uploadingFiles.length]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        handleFiles(e.target.files);
      }
    },
    [handleFiles]
  );

  const removeFile = useCallback((index: number) => {
    setUploadingFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const getFileIcon = (mimeType: string) => {
    const type = getAttachmentType(mimeType);
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

  return (
    <div className={cn("space-y-4", className)}>
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
          isDragging
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleInputChange}
          className="hidden"
        />
        <Upload className="h-10 w-10 mx-auto mb-4 text-muted-foreground" />
        <p className="text-sm font-medium">
          Drop files here or click to upload
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          Images, audio, video, PDFs up to {formatFileSize(maxSize)}
        </p>
      </div>

      {/* Uploading Files List */}
      {uploadingFiles.length > 0 && (
        <div className="space-y-2">
          {uploadingFiles.map((item, index) => {
            const Icon = getFileIcon(item.file.type);
            return (
              <div
                key={`${item.file.name}-${index}`}
                className="flex items-center gap-3 p-3 rounded-lg border bg-muted/30"
              >
                <Icon className="h-8 w-8 text-muted-foreground flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium truncate">
                      {item.file.name}
                    </p>
                    <span className="text-xs text-muted-foreground ml-2">
                      {formatFileSize(item.file.size)}
                    </span>
                  </div>
                  {item.status === "uploading" && (
                    <Progress value={item.progress} className="h-1 mt-2" />
                  )}
                  {item.status === "error" && (
                    <p className="text-xs text-red-500 mt-1">{item.error}</p>
                  )}
                </div>
                <div className="flex-shrink-0">
                  {item.status === "uploading" && (
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  )}
                  {item.status === "complete" && (
                    <Check className="h-4 w-4 text-green-500" />
                  )}
                  {item.status === "error" && (
                    <AlertCircle className="h-4 w-4 text-red-500" />
                  )}
                  {(item.status === "complete" || item.status === "error") && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 ml-1"
                      onClick={() => removeFile(index)}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Compact file upload button.
 */
export interface FileUploadButtonProps {
  onUploadComplete?: (response: UploadResponse) => void;
  onError?: (error: string) => void;
  memoryId?: number;
  createMemory?: boolean;
  processContent?: boolean;
  accept?: string;
  className?: string;
  children?: React.ReactNode;
}

export function FileUploadButton({
  onUploadComplete,
  onError,
  memoryId,
  createMemory = true,
  processContent = true,
  accept,
  className,
  children,
}: FileUploadButtonProps) {
  const [isUploading, setIsUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const response = await uploadFile(file, {
        memoryId,
        createMemory,
        processContent,
      });
      onUploadComplete?.(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      onError?.(message);
    } finally {
      setIsUploading(false);
      // Reset input
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleChange}
        className="hidden"
      />
      <Button
        variant="outline"
        size="sm"
        onClick={() => inputRef.current?.click()}
        disabled={isUploading}
        className={className}
      >
        {isUploading ? (
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        ) : (
          <Upload className="h-4 w-4 mr-2" />
        )}
        {children || "Upload"}
      </Button>
    </>
  );
}
