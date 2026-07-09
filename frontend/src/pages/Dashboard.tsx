// src/pages/Dashboard.tsx — Upload + video list with live status polling

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { videosApi } from "../api/videos";
import { authApi } from "../api/auth";
import { useAuthStore } from "../store/authStore";
import { UploadZone } from "../components/UploadZone";
import { VideoCard } from "../components/VideoCard";

export function Dashboard() {
  const navigate = useNavigate();
  const { user, logout: storeLogout } = useAuthStore();
  const qc = useQueryClient();
  const [uploadProgress, setUploadProgress] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["videos"],
    queryFn: () => videosApi.list(),
    refetchInterval: (data) => {
      // Poll every 3s while any video is in-progress
      const processing = data?.state.data?.videos?.some(
        (v) => !["done", "failed"].includes(v.status)
      );
      return processing ? 3000 : false;
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => videosApi.upload(file, setUploadProgress),
    onSuccess: (video) => {
      qc.invalidateQueries({ queryKey: ["videos"] });
      navigate(`/videos/${video.id}`);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(msg || "Upload failed. Please try again.");
      setUploadProgress(0);
    },
  });

  const handleLogout = async () => {
    await authApi.logout();
    storeLogout();
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-bg">
      {/* Header */}
      <header className="border-b border-border px-6 py-4 flex items-center justify-between">
        <span className="text-text font-bold text-lg">
          Clip<span className="text-accent">Sense</span>
        </span>
        <div className="flex items-center gap-4">
          <span className="text-muted text-sm">{user?.email}</span>
          <span className={`badge border text-xs ${user?.role === "pro"
            ? "text-accent-light border-accent/30 bg-accent/10"
            : "text-muted border-border bg-white/5"}`}>
            {user?.role?.toUpperCase()}
          </span>
          <button onClick={handleLogout} className="text-muted hover:text-text text-sm transition-colors">
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10 space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-text mb-1">Your videos</h1>
          <p className="text-muted text-sm">
            Upload a recording and ClipSense will find your best moments.
          </p>
        </div>

        <UploadZone
          onFile={(f) => uploadMutation.mutate(f)}
          uploading={uploadMutation.isPending}
          uploadProgress={uploadProgress}
        />

        {/* Video list */}
        <div className="space-y-3">
          {isLoading && (
            <div className="text-center text-muted py-8">Loading...</div>
          )}
          {!isLoading && !data?.videos?.length && (
            <div className="text-center text-muted py-8">
              No videos yet. Upload one above to get started.
            </div>
          )}
          {data?.videos?.map((v) => (
            <VideoCard key={v.id} video={v} />
          ))}
        </div>
      </main>
    </div>
  );
}
