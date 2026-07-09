// src/api/auth.ts
import { api } from "./client";
import axios from "axios";
import type { User } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const authApi = {
  signup: (email: string, password: string) =>
    api.post("/auth/signup", { email, password }),

  login: async (email: string, password: string): Promise<string> => {
    const resp = await api.post<{ access_token: string }>("/auth/login", { email, password });
    return resp.data.access_token;
  },

  logout: () => api.post("/auth/logout"),

  refresh: async (): Promise<string> => {
    const resp = await axios.post<{ access_token: string }>(
      `${API_URL}/auth/refresh`,
      {},
      { withCredentials: true }
    );
    return resp.data.access_token;
  },

  me: (): Promise<User> => api.get<User>("/auth/me").then((r) => r.data),

  forgotPassword: (email: string) =>
    api.post("/auth/forgot-password", { email }),

  resetPassword: (token: string, new_password: string) =>
    api.post("/auth/reset-password", { token, new_password }),

  verifyEmail: (token: string) =>
    api.get(`/auth/verify-email?token=${token}`),

  googleLogin: () => {
    window.location.href = `${API_URL}/auth/google`;
  },
};

// src/api/videos.ts
export { videosApi } from "./videos";

// src/api/clips.ts
export { clipsApi } from "./clips";
