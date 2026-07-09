// src/api/clips.ts
import { api } from "./client";
import type { Clip, ExportRequest, ExportResponse } from "../types";

export const clipsApi = {
  list: (videoId: string): Promise<Clip[]> =>
    api.get<Clip[]>(`/videos/${videoId}/clips`).then((r) => r.data),

  get: (videoId: string, clipId: string): Promise<Clip> =>
    api.get<Clip>(`/videos/${videoId}/clips/${clipId}`).then((r) => r.data),

  export: (req: ExportRequest): Promise<ExportResponse> =>
    api.post<ExportResponse>("/exports/", req).then((r) => r.data),
};
