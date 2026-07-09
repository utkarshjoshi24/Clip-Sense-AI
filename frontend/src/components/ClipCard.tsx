// src/components/ClipCard.tsx — Ranked clip with score breakdown + selection

import { useState } from "react";
import type { Clip } from "../types";
import { ScoreBar } from "./ScoreBar";

function formatTime(sec: number) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

interface ClipCardProps {
  clip: Clip;
  videoUrl?: string;
  selected: boolean;
  onSelect: (id: string, selected: boolean) => void;
  onDelete: (id: string) => void;
}

export function ClipCard({ clip, videoUrl, selected, onSelect, onDelete }: ClipCardProps) {
  const [expanded, setExpanded] = useState(false);
  const duration = clip.end_time - clip.start_time;

  return (
    <div
      className={`card transition-all duration-200 overflow-hidden ${
        selected ? "border-accent/60 bg-accent/5" : "hover:border-white/10"
      }`}
    >
      <div className="flex items-start gap-4">
        {/* Selection checkbox */}
        <div className="mt-1 flex-shrink-0 cursor-pointer" onClick={() => onSelect(clip.id, !selected)}>
          <div
            className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
              selected ? "bg-accent border-accent" : "border-border"
            }`}
          >
            {selected && (
              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
        </div>

        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-center gap-3 mb-2">
            <span className="text-xs font-mono bg-white/5 text-muted px-2 py-0.5 rounded">
              #{clip.rank}
            </span>
            <span className="text-sm font-semibold text-text truncate cursor-pointer" onClick={() => onSelect(clip.id, !selected)}>
              {clip.title_suggestion || `Clip ${clip.rank}`}
            </span>
            <span className="ml-auto text-xs font-mono text-accent font-bold">
              {Math.round(clip.composite_score * 100)}
            </span>
            
            {/* Delete button */}
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(clip.id); }}
              className="text-muted hover:text-error transition-colors p-1 rounded hover:bg-error/10 ml-2"
              title="Delete clip"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>

          {/* Timestamps */}
          <div className="flex items-center gap-2 text-xs text-muted mb-3 cursor-pointer" onClick={() => onSelect(clip.id, !selected)}>
            <span className="font-mono">{formatTime(clip.start_time)}</span>
            <span>→</span>
            <span className="font-mono">{formatTime(clip.end_time)}</span>
            <span className="text-border">·</span>
            <span>{Math.round(duration)}s</span>
          </div>

          {/* Video Player */}
          {videoUrl && (
            <div className="mt-3 mb-4 rounded-lg overflow-hidden bg-black/50 border border-white/5 relative shadow-inner">
              <video
                src={`${videoUrl}#t=${clip.start_time},${clip.end_time}`}
                controls
                controlsList="nodownload"
                className="w-full h-auto max-h-64 object-contain"
                preload="metadata"
              />
            </div>
          )}

          {/* Score breakdown */}
          <div className="space-y-2 mb-3">
            <ScoreBar label="Audio Energy" value={clip.audio_energy_score} color="#f59e0b" icon="🔊" />
            <ScoreBar label="Scene Cut" value={clip.scene_boundary_score} color="#10b981" icon="✂️" />
            <ScoreBar label="Transcript" value={clip.transcript_signal_score} color="#7c3aed" icon="💬" />
          </div>

          {/* Transcript snippet */}
          {clip.transcript_snippet && (
            <div className="mt-2">
              <button
                className="text-xs text-muted hover:text-text transition-colors"
                onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
              >
                {expanded ? "▲ Hide transcript" : "▼ Show transcript"}
              </button>
              {expanded && (
                <p className="mt-2 text-xs text-muted bg-white/3 rounded-lg p-3 leading-relaxed border border-border">
                  {clip.transcript_snippet}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
