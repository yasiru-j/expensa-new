import { useCallback, useRef, useState, type ChangeEvent, type DragEvent } from "react";

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
    <div className="space-y-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && browseInputRef.current?.click()}
        role="button"
        tabIndex={0}
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
          isDragging ? "border-gray-900 bg-gray-50" : "border-gray-300"
        } ${disabled ? "pointer-events-none opacity-50" : ""}`}
      >
        <p className="text-gray-700">
          <span className="font-medium">Drag and drop</span> a receipt, or click to browse
        </p>
        <p className="text-xs text-gray-400">JPEG, PNG, or a single-page PDF — up to {MAX_SIZE_MB}MB</p>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            cameraInputRef.current?.click();
          }}
          disabled={disabled}
          className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
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

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
