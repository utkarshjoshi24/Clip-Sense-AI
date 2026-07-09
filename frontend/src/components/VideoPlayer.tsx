// src/components/VideoPlayer.tsx — HTML5 player with seek-to-timestamp

import { useEffect, useRef } from "react";

interface VideoPlayerProps {
  src: string;
  seekTo?: number; // seconds
  className?: string;
}

export function VideoPlayer({ src, seekTo, className }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current && seekTo !== undefined) {
      videoRef.current.currentTime = seekTo;
    }
  }, [seekTo]);

  return (
    <video
      ref={videoRef}
      src={src}
      controls
      className={`w-full rounded-lg bg-black ${className ?? ""}`}
      preload="metadata"
      playsInline
    />
  );
}
