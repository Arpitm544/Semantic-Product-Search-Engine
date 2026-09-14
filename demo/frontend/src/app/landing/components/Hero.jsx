'use client';
import { useRef, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function Hero3DField() {
  const pointsRef = useRef();
  
  const particleCount = 120;
  const positions = useMemo(() => {
    const pos = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i++) {
      pos[i * 3]     = (Math.random() - 0.5) * 15;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 10;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 8 - 2; // mostly behind
    }
    return pos;
  }, []);

  useFrame((state) => {
    if (!pointsRef.current) return;
    const t = state.clock.elapsedTime;
    
    const posAttr = pointsRef.current.geometry.attributes.position;
    for (let i = 0; i < particleCount; i++) {
      // Subtle drift
      posAttr.array[i * 3] += Math.sin(t * 0.1 + i) * 0.002;
      posAttr.array[i * 3 + 1] += Math.cos(t * 0.1 + i) * 0.002;
    }
    posAttr.needsUpdate = true;
    
    // Slow rotation
    pointsRef.current.rotation.y = t * 0.05;
    pointsRef.current.rotation.x = Math.sin(t * 0.1) * 0.1;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" array={positions} count={particleCount} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial color="#ea580c" size={0.05} transparent opacity={0.4} sizeAttenuation depthWrite={false} />
    </points>
  );
}

export default function Hero() {
  return (
    <section className="lp-hero">
      {/* Cinematic 3D backdrop specific to the hero */}
      <div className="hero-3d-container" style={{ position: 'absolute', inset: 0, zIndex: 0, opacity: 0.8, pointerEvents: 'none' }}>
        <Canvas camera={{ position: [0, 0, 8], fov: 50 }} dpr={[1, 1.5]} gl={{ antialias: false, alpha: true }}>
          <fog attach="fog" args={['#050505', 5, 15]} />
          <Hero3DField />
        </Canvas>
      </div>
      
      {/* Ambient glow blobs */}
      <div className="hero-glow hero-glow-1" />
      <div className="hero-glow hero-glow-2" />

      {/* Content */}
      <div className="hero-content">
        <motion.div
          className="hero-badge"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2, ease: [0.25, 1, 0.5, 1] }}
        >
          Semantic Product Search · Concept
        </motion.div>

        <motion.h1
          className="hero-title"
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.9, delay: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
        >
          Search That<br />
          Understands <span className="gradient-text">Meaning</span>
        </motion.h1>

        <motion.p
          className="hero-sub"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.6, ease: [0.25, 1, 0.5, 1] }}
        >
          Not just keywords — true intent. Powered by Sentence Transformers, FAISS vector search, and Hybrid Fusion Engine.
        </motion.p>

        <motion.div
          className="hero-ctas"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.8, ease: [0.25, 1, 0.5, 1] }}
        >
          <a href="#pipeline" className="hero-cta primary">
            Explore the Pipeline
          </a>
          <a href="#playground" className="hero-cta secondary">
            Try Live Search
          </a>
        </motion.div>

        {/* Scroll indicator */}
        <motion.div
          className="scroll-indicator-group"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.4, duration: 1.2, ease: "easeInOut" }}
        >
          <span className="scroll-label">SYSTEM READY</span>
          <div className="scroll-indicator">
            <div className="scroll-dot" />
          </div>
        </motion.div>
      </div>
    </section>
  );
}
