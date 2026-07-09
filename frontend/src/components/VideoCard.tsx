// src/components/VideoCard.tsx — Video card with live status badge

import { Link } from "react-router-dom";
import type { Video, VideoStatus } from "../types";

const STATUS_CONFIG: Record<VideoStatus, { label: string; color: string; pulse: boolean }> = {
  uploaded:          { label: "Queued",             color: "text-muted bg-white/5 border-border",         pulse: false },
  extracting_audio:  { label: "Extracting Audio",   color: "text-warning bg-warning/10 border-warning/30", pulse: true  },
  detecting_scenes:  { label: "Detecting Scenes",   color: "text-warning bg-warning/10 border-warning/30", pulse: true  },
  transcribing:      { label: "Transcribing",        color: "text-accent-light bg-accent/10 border-accent/30", pulse: true },
  scoring:           { label: "Scoring",             color: "text-accent-light bg-accent/10 border-accent/30", pulse: true },
  done:              { label: "Ready",               color: "text-success bg-success/10 border-success/30", pulse: false },
  failed:            { label: "Failed",              color: "text-error bg-error/10 border-error/30",       pulse: false },
};

function formatDuration(sec: number | null) {
  if (!sec) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatDate(dt: string) {
  return new Date(dt).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric"
  });
}

interface VideoCardProps {
  video: Video;
}

export function VideoCard({ video }: VideoCardProps) {
  const cfg = STATUS_CONFIG[video.status];

  return (
    <Link to={`/videos/${video.id}`} className="block card hover:border-white/10 transition-all duration-200 hover:scale-[1.01]">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-text font-medium truncate">{video.filename}</p>
          <div className="flex items-center gap-3 mt-1 text-xs text-muted">
            <span>{formatDate(video.created_at)}</span>
            <span>·</span>
            <span>{formatDuration(video.duration_seconds)}</span>
          </div>
          {video.error_message && (
            <p className="mt-2 text-xs text-error bg-error/5 rounded px-2 py-1 border border-error/20 truncate">
              {video.error_message}
            </p>
          )}
        </div>

        <span className={`badge border shrink-0 ${cfg.color}`}>
          {cfg.pulse && (
            <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse-slow" />
          )}
          {cfg.label}
        </span>
      </div>
    </Link>
  );
}
