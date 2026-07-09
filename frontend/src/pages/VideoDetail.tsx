// src/pages/VideoDetail.tsx — Clip list with preview player + export

import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { videosApi } from "../api/videos";
import { clipsApi } from "../api/clips";
import { ClipCard } from "../components/ClipCard";
import { ExportPanel } from "../components/ExportPanel";
import type { Clip } from "../types";

const STATUS_LABELS: Record<string, string> = {
  uploaded: "Queued for processing",
  extracting_audio: "Stage 1/5 — Extracting audio...",
  detecting_scenes: "Stage 2/5 — Detecting scenes...",
  transcribing: "Stage 3/5 — Transcribing with Whisper...",
  scoring: "Stage 4/5 — Scoring highlight windows...",
  cutting_clips: "Stage 5/5 — Physically cutting scenes (this may take a minute)...",
  done: "Processing complete",
  failed: "Processing failed",
};

export function VideoDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [selectedClips, setSelectedClips] = useState<Clip[]>([]);

  const { data: video, isLoading: vLoading } = useQuery({
    queryKey: ["video", id],
    queryFn: () => videosApi.get(id!),
    refetchInterval: (data) => {
      const status = data?.state.data?.status?.toLowerCase();
      return status && !["done", "failed"].includes(status) ? 3000 : false;
    },
    enabled: !!id,
  });

  const { data: clips = [] } = useQuery({
    queryKey: ["clips", id],
    queryFn: () => clipsApi.list(id!),
    enabled: video?.status?.toLowerCase() === "done",
  });

  const deleteMutation = useMutation({
    mutationFn: (clipId: string) => clipsApi.delete(id!, clipId),
    onSuccess: (_, clipId) => {
      queryClient.setQueryData(["clips", id], (old: Clip[] | undefined) => 
        old ? old.filter(c => c.id !== clipId) : []
      );
      setSelectedClips(prev => prev.filter(c => c.id !== clipId));
    }
  });

  const toggleClip = (clipId: string, sel: boolean) => {
    if (sel) {
      const clip = clips.find((c) => c.id === clipId);
      if (clip) setSelectedClips((prev) => [...prev, clip]);
    } else {
      setSelectedClips((prev) => prev.filter((c) => c.id !== clipId));
    }
  };

  const handleDelete = (clipId: string) => {
    if (window.confirm("Are you sure you want to delete this clip?")) {
      deleteMutation.mutate(clipId);
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
        {/* Status */}
        {video.status?.toLowerCase() !== "done" && (
          <div className={`card flex items-center gap-3 ${video.status?.toLowerCase() === "failed" ? "border-error/30" : "border-accent/20"}`}>
            {video.status?.toLowerCase() !== "failed" && (
              <svg className="w-4 h-4 text-accent animate-spin flex-shrink-0" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            <div>
              <p className={`text-sm font-medium ${video.status?.toLowerCase() === "failed" ? "text-error" : "text-text"}`}>
                {STATUS_LABELS[video.status?.toLowerCase()] || video.status}
              </p>
              {video.error_message && (
                <p className="text-error text-xs mt-0.5">{video.error_message}</p>
              )}
            </div>
          </div>
        )}

        {/* Clip list */}
        {video.status?.toLowerCase() === "done" && (
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

            <div className="space-y-5">
              {clips.map((clip) => (
                <ClipCard
                  key={clip.id}
                  clip={clip}
                  videoUrl={video.preview_url}
                  selected={selectedClips.some((c) => c.id === clip.id)}
                  onSelect={toggleClip}
                  onDelete={handleDelete}
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
