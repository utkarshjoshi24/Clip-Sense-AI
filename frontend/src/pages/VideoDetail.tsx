// src/pages/VideoDetail.tsx — Clip list with preview player + export

import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { videosApi } from "../api/videos";
import { clipsApi } from "../api/clips";
import { VideoPlayer } from "../components/VideoPlayer";
import { ClipCard } from "../components/ClipCard";
import { ExportPanel } from "../components/ExportPanel";
import type { Clip } from "../types";

const STATUS_LABELS: Record<string, string> = {
  uploaded: "Queued for processing",
  extracting_audio: "Stage 1/4 — Extracting audio...",
  detecting_scenes: "Stage 2/4 — Detecting scenes...",
  transcribing: "Stage 3/4 — Transcribing with Whisper...",
  scoring: "Stage 4/4 — Scoring highlight windows...",
  done: "Processing complete",
  failed: "Processing failed",
};

export function VideoDetail() {
  const { id } = useParams<{ id: string }>();
  const [seekTo, setSeekTo] = useState<number | undefined>();
  const [selectedClips, setSelectedClips] = useState<Clip[]>([]);

  const { data: video, isLoading: vLoading } = useQuery({
    queryKey: ["video", id],
    queryFn: () => videosApi.get(id!),
    refetchInterval: (data) => {
      const status = data?.state.data?.status;
      return status && !["done", "failed"].includes(status) ? 3000 : false;
    },
    enabled: !!id,
  });

  const { data: clips = [] } = useQuery({
    queryKey: ["clips", id],
    queryFn: () => clipsApi.list(id!),
    enabled: video?.status === "done",
  });

  const toggleClip = (clipId: string, sel: boolean) => {
    if (sel) {
      const clip = clips.find((c) => c.id === clipId);
      if (clip) setSelectedClips((prev) => [...prev, clip]);
    } else {
      setSelectedClips((prev) => prev.filter((c) => c.id !== clipId));
    }
  };

  if (vLoading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <p className="text-muted">Loading...</p>
      </div>
    );
  }

  if (!video) return <div className="min-h-screen bg-bg flex items-center justify-center"><p className="text-error">Video not found</p></div>;

  return (
    <div className="min-h-screen bg-bg pb-32">
      {/* Header */}
      <header className="border-b border-border px-6 py-4 flex items-center gap-4">
        <Link to="/dashboard" className="text-muted hover:text-text transition-colors text-sm">
          ← Dashboard
        </Link>
        <span className="text-muted">/</span>
        <span className="text-text text-sm font-medium truncate">{video.filename}</span>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* Video Player */}
        {video.preview_url && (
          <VideoPlayer src={video.preview_url} seekTo={seekTo} className="max-h-80" />
        )}

        {/* Status */}
        {video.status !== "done" && (
          <div className={`card flex items-center gap-3 ${video.status === "failed" ? "border-error/30" : "border-accent/20"}`}>
            {video.status !== "failed" && (
              <svg className="w-4 h-4 text-accent animate-spin flex-shrink-0" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            <div>
              <p className={`text-sm font-medium ${video.status === "failed" ? "text-error" : "text-text"}`}>
                {STATUS_LABELS[video.status] || video.status}
              </p>
              {video.error_message && (
                <p className="text-error text-xs mt-0.5">{video.error_message}</p>
              )}
            </div>
          </div>
        )}

        {/* Clip list */}
        {video.status === "done" && (
          <>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-text">
                {clips.length} highlight{clips.length !== 1 ? "s" : ""} found
              </h2>
              {selectedClips.length > 0 && (
                <button
                  className="text-xs text-muted hover:text-text transition-colors"
                  onClick={() => setSelectedClips([])}
                >
                  Clear selection ({selectedClips.length})
                </button>
              )}
            </div>

            {clips.length === 0 && (
              <div className="card text-center py-8 text-muted">
                No highlights found. Try adjusting scoring weights in config.py.
              </div>
            )}

            <div className="space-y-3">
              {clips.map((clip) => (
                <ClipCard
                  key={clip.id}
                  clip={clip}
                  selected={selectedClips.some((c) => c.id === clip.id)}
                  onSelect={toggleClip}
                  onSeek={setSeekTo}
                />
              ))}
            </div>
          </>
        )}
      </main>

      <ExportPanel
        selected={selectedClips}
        videoFilename={video.filename}
        onClear={() => setSelectedClips([])}
      />
    </div>
  );
}
