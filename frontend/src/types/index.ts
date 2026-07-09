// src/types/index.ts

export type UserRole = "free" | "pro" | "admin";

export interface User {
  id: string;
  email: string;
  role: UserRole;
  email_verified: boolean;
  created_at: string;
  oauth_provider?: string;
}

export type VideoStatus =
  | "uploaded"
  | "extracting_audio"
  | "detecting_scenes"
  | "transcribing"
  | "scoring"
  | "done"
  | "failed";

export interface Video {
  id: string;
  filename: string;
  duration_seconds: number | null;
  status: VideoStatus;
  error_message?: string;
  created_at: string;
  preview_url?: string;
}

export interface Clip {
  id: string;
  video_id: string;
  rank: number;
  start_time: number;
  end_time: number;
  composite_score: number;
  audio_energy_score: number;
  scene_boundary_score: number;
  transcript_signal_score: number;
  title_suggestion?: string;
  transcript_snippet?: string;
  export_status: "pending" | "done" | "failed";
  export_url?: string;
  created_at: string;
}

export interface ExportRequest {
  clip_ids: string[];
  format: "mp4" | "edl" | "fcpxml";
}

export interface ExportResponse {
  format: string;
  urls?: string[];
  content?: string;
  filename?: string;
}
