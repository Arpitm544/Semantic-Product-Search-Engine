'use client';
import { useRef, useMemo, useCallback } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { RoundedBox, Html } from '@react-three/drei';
import * as THREE from 'three';
import ScrollReveal from './ScrollReveal';

// Pipeline nodes definition — reduced Y spacing for tighter composition
const NODES = [
  { id: 'products',   label: 'Products',      sub: '50 items · JSON',         color: '#f97316', y:  5.5, icon: '📦' },
  { id: 'embedding',  label: 'Embeddings',     sub: 'all-MiniLM-L6-v2',       color: '#fb923c', y:  2.75, icon: '🧠' },
  { id: 'faiss',      label: 'FAISS Index',    sub: '384-dim vectors',         color: '#fbbf24', y:  0,    icon: '⚡' },
  { id: 'hybrid',     label: 'Hybrid Fusion',  sub: 'Semantic + BM25 · RRF',  color: '#f59e0b', y: -2.75, icon: '⚖️' },
  { id: 'results',    label: 'Ranked Results',  sub: 'Top-K · scored',         color: '#d97706', y: -5.5, icon: '🏆' },
];

// Shared scroll state via ref (avoids React re-renders)
const scrollState = { progress: 0, activeIndex: 0 };

/* ─── Stage-specific ambient particles ─── */

function StageParticles({ node, index, isActive, activeFactor }) {
  const pointsRef = useRef();
  const count = 18;

  const { positions, basePositions } = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const base = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const radius = 1.2 + Math.random() * 0.8;
      base[i * 3]     = Math.cos(angle) * radius;
      base[i * 3 + 1] = (Math.random() - 0.5) * 0.8;
      base[i * 3 + 2] = Math.sin(angle) * radius + (Math.random() - 0.5) * 0.4;
      pos[i * 3]     = base[i * 3];
      pos[i * 3 + 1] = base[i * 3 + 1];
      pos[i * 3 + 2] = base[i * 3 + 2];
    }
    return { positions: pos, basePositions: base };
  }, []);

  // Visual behavior differs per stage
  useFrame((state) => {
    if (!pointsRef.current) return;
    const t = state.clock.elapsedTime;
    const geo = pointsRef.current.geometry;
    const posAttr = geo.attributes.position;

    for (let i = 0; i < count; i++) {
      const bx = basePositions[i * 3];
      const by = basePositions[i * 3 + 1];
      const bz = basePositions[i * 3 + 2];

      switch (index) {
        case 0: // PRODUCTS — small orbiting cubes (represented as points orbiting)
          posAttr.array[i * 3]     = bx + Math.sin(t * 0.4 + i * 0.7) * 0.15;
          posAttr.array[i * 3 + 1] = by + Math.sin(t * 0.3 + i * 1.2) * 0.1;
          posAttr.array[i * 3 + 2] = bz + Math.cos(t * 0.5 + i * 0.5) * 0.12;
          break;
        case 1: // EMBEDDINGS — flowing downward stream
          posAttr.array[i * 3]     = bx + Math.sin(t * 0.6 + i) * 0.08;
          posAttr.array[i * 3 + 1] = by + ((t * 0.3 + i * 0.15) % 1.0) * 0.6 - 0.3;
          posAttr.array[i * 3 + 2] = bz + Math.cos(t * 0.4 + i) * 0.08;
          break;
        case 2: // FAISS — cluster dots, subtle connecting motion
          {
            const clusterAngle = t * 0.2 + i * 0.35;
            const clusterR = 0.9 + Math.sin(t * 0.5 + i) * 0.2;
            posAttr.array[i * 3]     = Math.cos(clusterAngle) * clusterR;
            posAttr.array[i * 3 + 1] = by + Math.sin(t * 0.3 + i * 0.8) * 0.15;
            posAttr.array[i * 3 + 2] = Math.sin(clusterAngle) * clusterR;
          }
          break;
        case 3: // HYBRID — two streams merging from left/right
          {
            const side = i < count / 2 ? -1 : 1;
            const mergeProgress = (Math.sin(t * 0.5 + i * 0.3) + 1) / 2;
            posAttr.array[i * 3]     = side * (1.2 - mergeProgress * 0.9) + Math.sin(t * 0.3) * 0.05;
            posAttr.array[i * 3 + 1] = by + Math.sin(t * 0.4 + i * 0.6) * 0.12;
            posAttr.array[i * 3 + 2] = bz * (1 - mergeProgress * 0.3);
          }
          break;
        case 4: // RESULTS — converging inward
          {
            const converge = (Math.sin(t * 0.6 + i * 0.5) + 1) / 2;
            posAttr.array[i * 3]     = bx * (1 - converge * 0.6);
            posAttr.array[i * 3 + 1] = by * (1 - converge * 0.4);
            posAttr.array[i * 3 + 2] = bz * (1 - converge * 0.5);
          }
          break;
        default:
          posAttr.array[i * 3]     = bx;
          posAttr.array[i * 3 + 1] = by;
          posAttr.array[i * 3 + 2] = bz;
      }
    }
    posAttr.needsUpdate = true;

    // Scale + opacity based on active factor
    const targetOpacity = isActive ? 0.65 : 0.12;
    const mat = pointsRef.current.material;
    mat.opacity = THREE.MathUtils.lerp(mat.opacity, targetOpacity, 0.05);
  });

  const particleColor = useMemo(() => new THREE.Color(node.color), [node.color]);

  return (
    <points ref={pointsRef} position={[0, node.y, 0]}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          array={positions}
          count={count}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        color={particleColor}
        size={isActive ? 0.07 : 0.04}
        sizeAttenuation
        transparent
        opacity={0.12}
        depthWrite={false}
      />
    </points>
  );
}

/* ─── Animated particle that travels down a straight tube ─── */
function FlowParticle({ fromY, toY, color, speed, offset }) {
  const ref = useRef();
  const t = useRef(offset);

  useFrame((_, delta) => {
    t.current = (t.current + delta * speed) % 1;
    if (ref.current) {
      ref.current.position.y = THREE.MathUtils.lerp(fromY - 0.4, toY + 0.4, t.current);
    }
  });

  return (
    <mesh ref={ref} position={[0, fromY, 0]}>
      <sphereGeometry args={[0.05, 8, 8]} />
      <meshBasicMaterial color={color} />
    </mesh>
  );
}

/* ─── Glowing connecting tube between two nodes ─── */
function Connector({ fromY, toY, color, isActiveTransition }) {
  const tubeRef = useRef();
  const glowRef = useRef();
  const midY = (fromY + toY) / 2;
  const height = Math.abs(fromY - toY) - 0.9;

  useFrame(() => {
    if (tubeRef.current) {
      const targetOpacity = isActiveTransition ? 0.45 : 0.2;
      tubeRef.current.material.opacity = THREE.MathUtils.lerp(
        tubeRef.current.material.opacity, targetOpacity, 0.05
      );
    }
    if (glowRef.current) {
      const targetGlow = isActiveTransition ? 0.12 : 0.04;
      glowRef.current.material.opacity = THREE.MathUtils.lerp(
        glowRef.current.material.opacity, targetGlow, 0.05
      );
    }
  });

  return (
    <group>
      <mesh ref={tubeRef} position={[0, midY, 0]}>
        <cylinderGeometry args={[0.012, 0.012, height, 8]} />
        <meshBasicMaterial color={color} transparent opacity={0.2} />
      </mesh>
      <mesh ref={glowRef} position={[0, midY, 0]}>
        <cylinderGeometry args={[0.035, 0.035, height, 8]} />
        <meshBasicMaterial color={color} transparent opacity={0.04} />
      </mesh>
      {[0, 0.25, 0.5, 0.75].map((offset, i) => (
        <FlowParticle
          key={i}
          fromY={fromY}
          toY={toY}
          color={color}
          speed={0.35 + i * 0.04}
          offset={offset}
        />
      ))}
    </group>
  );
}

/* ─── Single pipeline node with active/inactive hierarchy ─── */
function PipelineNode({ node, index, isActive, activeFactor }) {
  const meshRef = useRef();
  const glowRef = useRef();
  const wireRef = useRef();
  const groupRef = useRef();

  useFrame((state) => {
    const t = state.clock.elapsedTime;

    // Smooth scale transition: active = 1.15, inactive = 0.75
    if (groupRef.current) {
      const targetScale = isActive ? 1.12 : 0.75;
      const currentScale = groupRef.current.scale.x;
      const newScale = THREE.MathUtils.lerp(currentScale, targetScale, 0.05);
      groupRef.current.scale.setScalar(newScale);
    }

    // Gentle float — active floats more
    if (meshRef.current) {
      const floatAmp = isActive ? 0.15 : 0.04;
      const floatSpeed = isActive ? 1.2 : 0.4;
      meshRef.current.position.y = node.y + Math.sin(t * floatSpeed + index) * floatAmp;
    }

    // Glow pulse on active node
    if (glowRef.current) {
      const baseOpacity = isActive ? 0.35 : 0.04;
      const pulseAmp = isActive ? 0.12 : 0.02;
      const targetOpacity = baseOpacity + Math.sin(t * 2.5 + index) * pulseAmp;
      glowRef.current.material.opacity = THREE.MathUtils.lerp(
        glowRef.current.material.opacity, targetOpacity, 0.06
      );
    }

    // Wireframe opacity
    if (wireRef.current) {
      const targetWire = isActive ? 0.6 : 0.1;
      wireRef.current.material.opacity = THREE.MathUtils.lerp(
        wireRef.current.material.opacity, targetWire, 0.05
      );
    }
  });

  // Emissive intensity differs for active vs inactive
  const emissiveIntensity = isActive ? 0.8 : 0.08;

  return (
    <group ref={groupRef}>
      {/* Glow backing */}
      <mesh ref={glowRef} position={[0, node.y, -0.1]}>
        <boxGeometry args={[3.2, 1.4, 0.1]} />
        <meshBasicMaterial color={node.color} transparent opacity={0.06} />
      </mesh>

      {/* Main box — premium physical material */}
      <mesh ref={meshRef} position={[0, node.y, 0]}>
        <RoundedBox args={[2.5, 0.88, 0.22]} radius={0.12} smoothness={4}>
          <meshPhysicalMaterial
            color="#050505"
            emissive={node.color}
            emissiveIntensity={emissiveIntensity}
            roughness={0.2}
            metalness={0.8}
            clearcoat={1.0}
            clearcoatRoughness={0.1}
          />
        </RoundedBox>
      </mesh>

      {/* Wireframe outline */}
      <mesh ref={wireRef} position={[0, node.y, 0.13]}>
        <RoundedBox args={[2.52, 0.91, 0.02]} radius={0.12} smoothness={4}>
          <meshBasicMaterial color={node.color} transparent opacity={0.15} wireframe />
        </RoundedBox>
      </mesh>

      {/* HTML Label */}
      <Html position={[0, node.y, 0.22]} center distanceFactor={10} zIndexRange={[10, 0]}>
        <div
          className={`pipe-node-label ${isActive ? 'pipe-node-active' : ''}`}
          style={{ borderColor: isActive ? node.color + '60' : node.color + '20' }}
        >
          <span className="pipe-icon">{node.icon}</span>
          <div>
            <div className="pipe-name" style={{ color: isActive ? node.color : '#78716c' }}>{node.label}</div>
            <div className="pipe-sub">{node.sub}</div>
          </div>
        </div>
      </Html>

      {/* Per-stage ambient particles */}
      <StageParticles node={node} index={index} isActive={isActive} activeFactor={activeFactor} />
    </group>
  );
}

/* ─── Spotlight that follows the active stage ─── */
function ActiveSpotlight() {
  const lightRef = useRef();

  useFrame(() => {
    if (!lightRef.current) return;
    const activeY = NODES[scrollState.activeIndex]?.y ?? 0;
    lightRef.current.position.y = THREE.MathUtils.lerp(lightRef.current.position.y, activeY + 2, 0.04);
    lightRef.current.target.position.y = THREE.MathUtils.lerp(lightRef.current.target.position.y, activeY, 0.04);
    lightRef.current.target.updateMatrixWorld();
  });

  return (
    <spotLight
      ref={lightRef}
      position={[2, 6, 6]}
      angle={0.45}
      penumbra={0.8}
      color="#f97316"
      intensity={1.2}
      distance={18}
      castShadow={false}
    />
  );
}

/* ─── Main pipeline scene with cinematic camera ─── */
function PipelineScene() {
  const scrollRef = useRef(0);
  const cameraTarget = useRef({ x: 0, y: 12, z: 14, rotX: 0 });

  // Scroll listener via useFrame for smooth RAF-based reading
  useFrame((state) => {
    if (typeof window === 'undefined') return;

    const scrollY = window.scrollY;
    const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const progress = Math.min(Math.max(scrollY / maxScroll, 0), 1);

    // Smooth scroll progress (avoids jitter)
    scrollRef.current = THREE.MathUtils.lerp(scrollRef.current, progress, 0.06);
    const smooth = scrollRef.current;

    // Determine active stage index
    const activeIdx = Math.min(Math.floor(smooth * 5.5), 4);
    scrollState.progress = smooth;
    scrollState.activeIndex = activeIdx;

    // Expose for particle background
    if (typeof window !== 'undefined') {
      window.__pipelineActiveIndex = activeIdx;
      window.__pipelineActiveScreenY = (0.5 - (NODES[activeIdx]?.y ?? 0) / 12) * window.innerHeight;
    }

    const viewportWidth = window.innerWidth;
    const isMobile = viewportWidth < 768;
    const isTablet = viewportWidth >= 768 && viewportWidth < 1024;

    // Cinematic camera — travels THROUGH the pipeline with inertia
    // Y: from above pipeline (12) down through it (-7)
    const targetY = 12 - (smooth * 19);

    // X: pipeline stays right side; slight sinusoidal drift for cinema
    const xOffset = isMobile ? 0 : isTablet ? 3.5 : 5.5;
    const xDrift = Math.sin(smooth * Math.PI * 0.8) * 0.6;
    const targetX = -xOffset + xDrift;

    // Z: deeper push-in for cinematic scale
    const zBase = isMobile ? 18 : 12;
    const zBreath = Math.sin(smooth * Math.PI) * 2.5;
    const targetZ = zBase - zBreath;

    // Slight rotation tilt for cinematic feel
    const tiltX = smooth * 0.02;
    const tiltY = Math.sin(smooth * Math.PI) * -0.05;

    // Update targets
    cameraTarget.current.x = targetX;
    cameraTarget.current.y = targetY;
    cameraTarget.current.z = targetZ;
    cameraTarget.current.rotX = tiltX;

    // Lerp camera toward targets (damping = cinematic inertia)
    const dampSpeed = 0.035;
    state.camera.position.x = THREE.MathUtils.lerp(state.camera.position.x, cameraTarget.current.x, dampSpeed);
    state.camera.position.y = THREE.MathUtils.lerp(state.camera.position.y, cameraTarget.current.y, dampSpeed);
    state.camera.position.z = THREE.MathUtils.lerp(state.camera.position.z, cameraTarget.current.z, dampSpeed);

    // Look at offset target to keep pipeline in right lane
    const lookAtX = -xOffset;
    state.camera.lookAt(lookAtX, state.camera.position.y + tiltX, tiltY);
  });

  // Compute active states
  const activeIndex = scrollState.activeIndex;

  return (
    <>
      {/* Lighting — reduced ambient, spotlight follows active */}
      <ambientLight intensity={0.3} />
      <pointLight position={[3, 5, 5]} color="#f97316" intensity={0.8} distance={22} />
      <pointLight position={[-3, -5, 5]} color="#fbbf24" intensity={0.5} distance={22} />
      <ActiveSpotlight />

      {/* Pipeline nodes */}
      {NODES.map((node, i) => {
        const isActive = i === activeIndex;
        const dist = Math.abs(i - activeIndex);
        const activeFactor = Math.max(0, 1 - dist * 0.35);
        return (
          <PipelineNode
            key={node.id}
            node={node}
            index={i}
            isActive={isActive}
            activeFactor={activeFactor}
          />
        );
      })}

      {/* Connectors with active transition highlighting */}
      {NODES.slice(0, -1).map((node, i) => {
        const isActiveTransition = i === activeIndex || i === activeIndex - 1;
        return (
          <Connector
            key={`conn-${i}`}
            fromY={NODES[i].y}
            toY={NODES[i + 1].y}
            color={node.color}
            isActiveTransition={isActiveTransition}
          />
        );
      })}
    </>
  );
}

// Fixed background canvas for the whole page
export function PipelineBackground() {
  return (
    <Canvas
      camera={{ position: [0, 12, 14], fov: 42 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true }}
    >
      <PipelineScene />
    </Canvas>
  );
}

// Standard HTML component for the pipeline section (stats, text)
export default function PipelineSection() {
  return (
    <section className="lp-section pipeline-section" id="pipeline" style={{ minHeight: '60vh', justifyContent: 'center' }}>
      <ScrollReveal>
        <div className="section-badge">How It Works</div>
        <h2 className="section-title">The Search Pipeline</h2>
        <p className="section-sub">
          Scroll down to traverse the pipeline. From raw product catalog to ranked semantic results — five stages, all connected in a real-time vector flow.
        </p>
      </ScrollReveal>

      <div className="pipeline-stats" style={{ marginTop: '4rem' }}>
        {[
          { label: 'Products Indexed', value: '50' },
          { label: 'Vector Dimensions', value: '384' },
          { label: 'Avg. Search Latency', value: '<50ms' },
          { label: 'Fusion Method', value: 'RRF' },
        ].map((s) => (
          <div key={s.label} className="pipeline-stat">
            <div className="ps-value">{s.value}</div>
            <div className="ps-label">{s.label}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
