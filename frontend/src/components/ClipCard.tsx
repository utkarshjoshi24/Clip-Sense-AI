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
  selected: boolean;
  onSelect: (id: string, selected: boolean) => void;
  onSeek: (time: number) => void;
}

export function ClipCard({ clip, selected, onSelect, onSeek }: ClipCardProps) {
  const [expanded, setExpanded] = useState(false);
  const duration = clip.end_time - clip.start_time;

  return (
    <div
      className={`card cursor-pointer transition-all duration-200 ${
        selected ? "border-accent/60 bg-accent/5" : "hover:border-white/10"
      }`}
      onClick={() => onSelect(clip.id, !selected)}
    >
      <div className="flex items-start gap-4">
        {/* Selection checkbox */}
        <div className="mt-0.5 flex-shrink-0">
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
            <span className="text-sm font-semibold text-text truncate">
              {clip.title_suggestion || `Clip ${clip.rank}`}
            </span>
            <span className="ml-auto text-xs font-mono text-accent font-bold">
              {Math.round(clip.composite_score * 100)}
            </span>
          </div>

          {/* Timestamps */}
          <div className="flex items-center gap-2 text-xs text-muted mb-3">
            <button
              className="hover:text-accent transition-colors font-mono"
              onClick={(e) => { e.stopPropagation(); onSeek(clip.start_time); }}
            >
              {formatTime(clip.start_time)}
            </button>
            <span>→</span>
            <button
              className="hover:text-accent transition-colors font-mono"
              onClick={(e) => { e.stopPropagation(); onSeek(clip.end_time); }}
            >
              {formatTime(clip.end_time)}
            </button>
            <span className="text-border">·</span>
            <span>{Math.round(duration)}s</span>
          </div>

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
