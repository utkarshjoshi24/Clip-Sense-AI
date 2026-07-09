// src/api/videos.ts
import { api } from "./client";
import type { Video, VideoStatus } from "../types";

export const videosApi = {
  upload: (file: File, onProgress?: (pct: number) => void): Promise<Video> =>
    api.post<Video>("/videos/upload", (() => {
      const fd = new FormData();
      fd.append("file", file);
      return fd;
    })(), {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    }).then((r) => r.data),

  list: (skip = 0, limit = 20) =>
    api.get<{ videos: Video[]; total: number }>("/videos/", { params: { skip, limit } })
      .then((r) => r.data),

  get: (id: string): Promise<Video> =>
    api.get<Video>(`/videos/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    api.delete(`/videos/${id}`).then(() => undefined),
};
