import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Float, Html, useTexture } from "@react-three/drei";
import * as THREE from "three";

// A single floating video clip/card
function ClipCard({
  position,
  rotation,
  image,
  title,
  delay = 0,
}: {
  position: [number, number, number];
  rotation: [number, number, number];
  image: string;
  title: string;
  delay?: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const texture = useTexture(image);
  
  // Animate Entrance
  useFrame((state) => {
    if (!meshRef.current) return;
    const t = state.clock.getElapsedTime();
    if (t > delay) {
      meshRef.current.position.y = THREE.MathUtils.lerp(meshRef.current.position.y, position[1], 0.05);
      const mat = meshRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = THREE.MathUtils.lerp(mat.opacity, 0.9, 0.05);
    }
  });

  return (
    <Float speed={2} rotationIntensity={0.2} floatIntensity={0.5}>
      <mesh
        ref={meshRef}
        position={[position[0], position[1] - 5, position[2]]}
        rotation={rotation}
      >
        <planeGeometry args={[3, 1.7]} />
        <meshBasicMaterial
          map={texture}
          transparent
          opacity={0}
          side={THREE.DoubleSide}
        />
        {/* Glow effect */}
        <Html transform position={[0, -1, 0]}>
          <div className="bg-surface-variant/80 backdrop-blur-md px-3 py-1 rounded-md border border-white/10 text-white font-mono-sm text-[10px] whitespace-nowrap shadow-xl">
            {title}
          </div>
        </Html>
      </mesh>
    </Float>
  );
}

// Timeline track that the clips converge onto
function TimelineTrack() {
  return (
    <group>
      {/* Replaced <line> with a thin <mesh> box to avoid SVG JSX type conflicts */}
      <mesh position={[0, -2, 0]}>
        <boxGeometry args={[8, 0.02, 0.02]} />
        <meshBasicMaterial color="#c0c1ff" transparent opacity={0.3} />
      </mesh>
      <mesh position={[-2, -2, 0]}>
        <circleGeometry args={[0.08, 16]} />
        <meshBasicMaterial color="#4cd7f6" />
      </mesh>
      <mesh position={[1.5, -2, 0]}>
        <circleGeometry args={[0.08, 16]} />
        <meshBasicMaterial color="#c0c1ff" />
      </mesh>
    </group>
  );
}

// Background Particles
function ParticleField() {
  const count = 200;
  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 20;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 10;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 10 - 5;
    }
    return pos;
  }, []);

  const pointsRef = useRef<THREE.Points>(null);

  useFrame((state) => {
    if (!pointsRef.current) return;
    pointsRef.current.rotation.y = state.clock.elapsedTime * 0.05;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial size={0.05} color="#c0c1ff" transparent opacity={0.4} />
    </points>
  );
}

// Camera parallax
function Rig() {
  const { camera, mouse } = useThree();
  useFrame(() => {
    camera.position.x = THREE.MathUtils.lerp(camera.position.x, mouse.x * 1, 0.05);
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, mouse.y * 1, 0.05);
    camera.lookAt(0, 0, 0);
  });
  return null;
}

export default function Hero3DScene() {
  // Intersection Observer to pause rendering when offscreen
  const containerRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting);
      },
      { threshold: 0 }
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="w-full h-[500px] relative">
      {isVisible && (
        <Canvas
          // Cap DPR to 1.5 to save GPU performance
          dpr={[1, 1.5]}
          camera={{ position: [0, 0, 6], fov: 45 }}
          gl={{ antialias: false, alpha: true }}
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
        >
          <Rig />
          <ambientLight intensity={0.5} />
          
          <ParticleField />
          <TimelineTrack />

          {/* Floating UI Clips */}
          <ClipCard
            position={[-2, 1, -1]}
            rotation={[0, 0.2, -0.05]}
            image="https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?q=80&w=800&auto=format&fit=crop"
            title="SCENE_01 / HIGHLIGHT"
            delay={0.2}
          />
          
          <ClipCard
            position={[0, 0, 0]}
            rotation={[0, 0, 0]}
            image="https://images.unsplash.com/photo-1492691527719-9d1e07e534b4?q=80&w=800&auto=format&fit=crop"
            title="AI_SELECTED (98%)"
            delay={0.6}
          />

          <ClipCard
            position={[2, 1.5, -2]}
            rotation={[0, -0.2, 0.05]}
            image="https://images.unsplash.com/photo-1616469829581-73993eb86b02?q=80&w=800&auto=format&fit=crop"
            title="AUDIO_PEAK_DETECTED"
            delay={1.0}
          />
        </Canvas>
      )}
    </div>
  );
}
