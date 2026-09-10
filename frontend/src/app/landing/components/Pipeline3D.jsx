'use client';
import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, RoundedBox, Html } from '@react-three/drei';
import * as THREE from 'three';
import ScrollReveal from './ScrollReveal';

// Pipeline nodes definition
const NODES = [
  { id: 'products',   label: 'Products',      sub: '50 items · JSON',         color: '#f97316', y:  6,   icon: '📦' },
  { id: 'embedding',  label: 'Embeddings',    sub: 'all-MiniLM-L6-v2',        color: '#fb923c', y:  3,   icon: '🧠' },
  { id: 'faiss',      label: 'FAISS Index',   sub: '384-dim vectors',          color: '#fbbf24', y:  0,   icon: '⚡' },
  { id: 'hybrid',     label: 'Hybrid Fusion', sub: 'Semantic + BM25 · RRF',   color: '#f59e0b', y: -3,   icon: '⚖️' },
  { id: 'results',    label: 'Ranked Results','sub': 'Top-K · scored',        color: '#d97706', y: -6,   icon: '🏆' },
];

// Animated particle that travels down a straight tube
function FlowParticle({ fromY, toY, color, speed, offset }) {
  const ref = useRef();
  const t = useRef(offset);

  useFrame((_, delta) => {
    t.current = (t.current + delta * speed) % 1;
    if (ref.current) {
      ref.current.position.y = THREE.MathUtils.lerp(fromY - 0.5, toY + 0.5, t.current);
    }
  });

  return (
    <mesh ref={ref} position={[0, fromY, 0]}>
      <sphereGeometry args={[0.07, 8, 8]} />
      <meshBasicMaterial color={color} />
    </mesh>
  );
}

// Glowing connecting tube between two nodes
function Connector({ fromY, toY, color }) {
  const midY = (fromY + toY) / 2;
  const height = Math.abs(fromY - toY) - 1.2;

  return (
    <group>
      {/* Main tube */}
      <mesh position={[0, midY, 0]}>
        <cylinderGeometry args={[0.015, 0.015, height, 8]} />
        <meshBasicMaterial color={color} transparent opacity={0.35} />
      </mesh>
      {/* Glow tube */}
      <mesh position={[0, midY, 0]}>
        <cylinderGeometry args={[0.04, 0.04, height, 8]} />
        <meshBasicMaterial color={color} transparent opacity={0.07} />
      </mesh>
      {/* Flow particles */}
      {[0, 0.25, 0.5, 0.75].map((offset, i) => (
        <FlowParticle
          key={i}
          fromY={fromY}
          toY={toY}
          color={color}
          speed={0.4 + i * 0.05}
          offset={offset}
        />
      ))}
    </group>
  );
}

// Single pipeline node (glowing rounded box + label)
function PipelineNode({ node, index }) {
  const meshRef = useRef();
  const glowRef = useRef();

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (meshRef.current) {
      // Subtle float
      meshRef.current.position.y = node.y + Math.sin(t * 0.6 + index) * 0.08;
    }
    if (glowRef.current) {
      glowRef.current.material.opacity = 0.08 + Math.sin(t * 1.5 + index) * 0.03;
    }
  });

  return (
    <group>
      {/* Glow box (slightly larger) */}
      <mesh ref={glowRef} position={[0, node.y, -0.1]}>
        <boxGeometry args={[2.6, 1.0, 0.1]} />
        <meshBasicMaterial color={node.color} transparent opacity={0.08} />
      </mesh>

      {/* Main node box */}
      <mesh ref={meshRef} position={[0, node.y, 0]}>
        <RoundedBox args={[2.4, 0.85, 0.22]} radius={0.12} smoothness={4}>
          <meshStandardMaterial
            color="#171717"
            emissive={node.color}
            emissiveIntensity={0.04}
            roughness={0.4}
            metalness={0.7}
          />
        </RoundedBox>
      </mesh>

      {/* Border frame */}
      <mesh position={[0, node.y, 0.12]}>
        <RoundedBox args={[2.42, 0.87, 0.02]} radius={0.12} smoothness={4}>
          <meshBasicMaterial color={node.color} transparent opacity={0.3} wireframe />
        </RoundedBox>
      </mesh>

      {/* HTML label overlay */}
      <Html position={[0, node.y, 0.25]} center distanceFactor={10} zIndexRange={[100, 0]}>
        <div className="pipe-node-label" style={{ borderColor: node.color + '40' }}>
          <span className="pipe-icon">{node.icon}</span>
          <div>
            <div className="pipe-name" style={{ color: node.color }}>{node.label}</div>
            <div className="pipe-sub">{node.sub}</div>
          </div>
        </div>
      </Html>
    </group>
  );
}

function PipelineScene() {
  return (
    <>
      <color attach="background" args={['#0a0a0a']} />
      <ambientLight intensity={0.6} />
      <pointLight position={[3, 5, 5]} color="#f97316" intensity={1.5} distance={25} />
      <pointLight position={[-3, -5, 5]} color="#fbbf24" intensity={1} distance={25} />

      <OrbitControls
        enablePan={false}
        enableZoom={false}
        autoRotate
        autoRotateSpeed={0.6}
        maxPolarAngle={Math.PI / 2 + 0.3}
        minPolarAngle={Math.PI / 2 - 0.3}
      />

      {/* Nodes */}
      {NODES.map((node, i) => (
        <PipelineNode key={node.id} node={node} index={i} />
      ))}

      {/* Connectors between nodes */}
      {NODES.slice(0, -1).map((node, i) => (
        <Connector
          key={`conn-${i}`}
          fromY={NODES[i].y}
          toY={NODES[i + 1].y}
          color={node.color}
        />
      ))}
    </>
  );
}

export default function Pipeline3D() {
  return (
    <section className="lp-section pipeline-section" id="pipeline">
      <ScrollReveal>
        <div className="section-badge">How It Works</div>
        <h2 className="section-title">The Search Pipeline</h2>
        <p className="section-sub">From raw product catalog to ranked semantic results — five stages, all connected. Rotate the diagram to explore.</p>
      </ScrollReveal>

      <div className="pipeline-canvas-wrapper">
        <Canvas camera={{ position: [0, 0, 14], fov: 45 }}>
          <PipelineScene />
        </Canvas>
        <div className="pipeline-hint">↔ Drag to rotate the pipeline</div>
      </div>

      {/* Stats below the 3D scene */}
      <div className="pipeline-stats">
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
