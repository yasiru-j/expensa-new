import { useCallback, useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { GlassCard } from "./ui/GlassCard";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "application/pdf"];
const MAX_SIZE_BYTES = Number(import.meta.env.VITE_MAX_UPLOAD_SIZE_BYTES) || 10 * 1024 * 1024;
const MAX_SIZE_MB = Math.floor(MAX_SIZE_BYTES / (1024 * 1024));

interface UploadDropzoneProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export function UploadDropzone({ onFileSelected, disabled = false }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const browseInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const validateAndSelect = useCallback(
    (file: File) => {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setError("Only JPEG, PNG, and PDF files are accepted.");
        return;
      }
      if (file.size > MAX_SIZE_BYTES) {
        setError(`File exceeds the ${MAX_SIZE_MB}MB upload limit.`);
        return;
      }
      setError(null);
      onFileSelected(file);
    },
    [onFileSelected],
  );

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    const file = e.dataTransfer.files[0];
    if (file) validateAndSelect(file);
  }

  function handleInputChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) validateAndSelect(file);
    e.target.value = ""; // allow re-selecting the same file after an error
  }

  return (
    <GlassCard className="flex h-full flex-col gap-2.5 p-3.5">
      {/* No nested <button> in here (a11y: interactive controls must not be
          nested) — "Take a photo" lives outside this role="button" area. */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && browseInputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled) {
            e.preventDefault();
            browseInputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={0}
        aria-label="Upload a receipt: drag and drop, or click to browse"
        className={`flex min-h-[150px] flex-1 cursor-pointer flex-col items-center justify-center gap-2.5 rounded-2xl border-[1.5px] border-dashed p-5 text-center transition-colors ${
          isDragging
            ? "border-brand-blue/65 bg-brand-blue/10"
            : "border-brand-blue/40 bg-brand-blue/5 hover:border-brand-blue/65 hover:bg-brand-blue/10"
        } ${disabled ? "pointer-events-none opacity-50" : ""}`}
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-gradient text-lg font-semibold text-white shadow-brand">
          +
        </span>
        <p className="text-[15px] font-semibold text-ink-900">
          Drop a receipt here, or click to browse
        </p>
        <p className="text-xs text-ink-600">
          JPEG, PNG, or a single-page PDF — up to {MAX_SIZE_MB}MB
        </p>
      </div>

      <div className="flex justify-center">
        <button
          type="button"
          onClick={() => cameraInputRef.current?.click()}
          disabled={disabled}
          className="rounded-lg border border-ink-900/10 bg-white/70 px-3 py-1.5 text-sm font-medium text-ink-900 hover:bg-white disabled:opacity-50"
        >
          Take a photo
        </button>
      </div>

      <input
        ref={browseInputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(",")}
        onChange={handleInputChange}
        className="hidden"
        disabled={disabled}
      />
      {/* capture="environment" opens the rear camera directly on mobile; on
          desktop browsers it's simply ignored and falls back to a file picker. */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleInputChange}
        className="hidden"
        disabled={disabled}
      />

      {error && <p className="text-center text-sm text-rose-600">{error}</p>}
    </GlassCard>
  );
}
