// src/components/ExportPanel.tsx — Sticky export panel when clips are selected

import { useState } from "react";
import type { Clip } from "../types";
import { clipsApi } from "../api/clips";

interface ExportPanelProps {
  selected: Clip[];
  videoFilename: string;
  onClear: () => void;
}

export function ExportPanel({ selected, videoFilename, onClear }: ExportPanelProps) {
  const [format, setFormat] = useState<"mp4" | "edl" | "fcpxml">("mp4");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (selected.length === 0) return null;

  const handleExport = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await clipsApi.export({
        clip_ids: selected.map((c) => c.id),
        format,
      });

      if (format === "mp4" && result.urls) {
        result.urls.forEach((url, i) => {
          const a = document.createElement("a");
          a.href = url;
          a.download = `highlight_${i + 1}.mp4`;
          a.click();
        });
      } else if (result.content && result.filename) {
        const blob = new Blob([result.content], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = result.filename;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (e: unknown) {
      setError("Export failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-surface/95 backdrop-blur-xl p-4 animate-slide-up">
      <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center gap-4">
        <div className="flex-1">
          <p className="text-text font-semibold">
            {selected.length} clip{selected.length > 1 ? "s" : ""} selected
          </p>
          <p className="text-muted text-xs">
            {selected.map((c) => `#${c.rank}`).join(", ")}
          </p>
        </div>

        {/* Format selector */}
        <div className="flex gap-1 bg-bg rounded-lg p-1 border border-border">
          {(["mp4", "edl", "fcpxml"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFormat(f)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                format === f ? "bg-accent text-white" : "text-muted hover:text-text"
              }`}
            >
              {f.toUpperCase()}
            </button>
          ))}
        </div>

        {error && <p className="text-error text-xs">{error}</p>}

        <div className="flex gap-2">
          <button onClick={onClear} className="btn-ghost text-sm py-2 px-4">
            Clear
          </button>
          <button
            onClick={handleExport}
            disabled={loading}
            className="btn-primary text-sm py-2 px-5"
          >
            {loading ? "Exporting..." : `Export ${format.toUpperCase()}`}
          </button>
        </div>
      </div>
    </div>
  );
}
