'use client';
import { useRef, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Line, Html } from '@react-three/drei';
import * as THREE from 'three';
import ScrollReveal from './ScrollReveal';

const catColors = {
  "Jackets & Outerwear": "#f97316",
  "Footwear": "#d97706",
  "Camping & Hiking": "#fbbf24",
  "Electronics & Gadgets": "#ef4444",
  "Apparel": "#fb923c",
};
const defaultColor = "#a8a29e";

function GlowSphere({ position, color, scale, isTop, label, category }) {
  const meshRef = useRef();
  const glowRef = useRef();
  const [hovered, setHovered] = useState(false);

  useFrame((state) => {
    if (meshRef.current) {
      const t = state.clock.elapsedTime;
      // Gentle floating motion
      meshRef.current.position.y = position[1] + Math.sin(t * 0.5 + position[0]) * 0.08;
      
      if (isTop) {
        const pulse = 1 + Math.sin(t * 3) * 0.15;
        meshRef.current.scale.setScalar(scale * pulse);
      }
    }
    if (glowRef.current) {
      glowRef.current.material.opacity = hovered ? 0.35 : (isTop ? 0.25 : 0.1);
    }
  });

  return (
    <group>
      {/* Inner core sphere */}
      <mesh
        ref={meshRef}
        position={position}
        scale={scale}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <sphereGeometry args={[0.2, 32, 32]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isTop ? 1.5 : 0.6}
          roughness={0.2}
          metalness={0.8}
        />
      </mesh>
      
      {/* Outer glow sphere */}
      <mesh ref={glowRef} position={position} scale={scale * 2}>
        <sphereGeometry args={[0.2, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={isTop ? 0.2 : 0.08} />
      </mesh>

      {/* Label on hover or if top result */}
      {(hovered || isTop) && (
        <Html position={position} distanceFactor={8} zIndexRange={[100, 0]}>
          <div className="three-tooltip" style={{ borderColor: color + '40' }}>
            <div className="tt-cat" style={{ color }}>{category}</div>
            <div className="tt-title">{label}</div>
          </div>
        </Html>
      )}
    </group>
  );
}

function QuerySphere({ position }) {
  const meshRef = useRef();
  const ringRef = useRef();

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (meshRef.current) {
      const s = 1 + Math.sin(t * 4) * 0.2;
      meshRef.current.scale.setScalar(s);
    }
    if (ringRef.current) {
      ringRef.current.rotation.x = t * 0.5;
      ringRef.current.rotation.z = t * 0.3;
    }
  });

  return (
    <group position={position}>
      {/* Core */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.3, 32, 32]} />
        <meshStandardMaterial
          color="#fbbf24"
          emissive="#f97316"
          emissiveIntensity={2}
          roughness={0.1}
          metalness={0.9}
        />
      </mesh>
      
      {/* Rotating ring */}
      <mesh ref={ringRef}>
        <torusGeometry args={[0.5, 0.02, 16, 64]} />
        <meshBasicMaterial color="#fbbf24" transparent opacity={0.5} />
      </mesh>

      {/* Glow */}
      <mesh>
        <sphereGeometry args={[0.6, 16, 16]} />
        <meshBasicMaterial color="#f97316" transparent opacity={0.12} />
      </mesh>
      
      <pointLight color="#f97316" intensity={3} distance={8} />
      
      <Html distanceFactor={8}>
        <div className="three-tooltip query-tooltip">🔍 Query Vector</div>
      </Html>
    </group>
  );
}

function SimilarityLines({ data, queryPos, topKIndices }) {
  if (!queryPos || topKIndices.length === 0) return null;

  return (
    <group>
      {topKIndices.map((idx) => {
        const item = data[idx];
        const points = [new THREE.Vector3(...queryPos), new THREE.Vector3(item.x, item.y, item.z)];
        return (
          <Line
            key={`line-${idx}`}
            points={points}
            color="#fbbf24"
            lineWidth={1.5}
            dashed={true}
            dashScale={40}
            dashSize={0.8}
            opacity={0.7}
            transparent
          />
        );
      })}
    </group>
  );
}

function Stars() {
  const ref = useRef();
  const positions = useRef(
    new Float32Array(
      Array.from({ length: 500 * 3 }, () => (Math.random() - 0.5) * 30)
    )
  ).current;

  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.015;
    }
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          array={positions}
          count={500}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial color="#44403c" size={0.04} sizeAttenuation />
    </points>
  );
}

export default function VectorSpace() {
  const [data, setData] = useState([]);
  const [queryText, setQueryText] = useState('');
  const [queryPos, setQueryPos] = useState(null);
  const [topKIndices, setTopKIndices] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    fetch('/pca_embeddings.json')
      .then(res => res.json())
      .then(d => setData(d))
      .catch(err => console.error("Error loading PCA data:", err));
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    if (!queryText.trim() || data.length === 0) return;

    setIsSearching(true);

    const seed = queryText.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
    const fakeX = Math.sin(seed * 0.7) * 3;
    const fakeY = Math.cos(seed * 1.3) * 2;
    const fakeZ = Math.sin(seed * 2.1) * 3;

    const newQueryPos = [fakeX, fakeY, fakeZ];
    setQueryPos(newQueryPos);

    const distances = data.map((item, idx) => {
      const dx = item.x - fakeX;
      const dy = item.y - fakeY;
      const dz = item.z - fakeZ;
      return { idx, dist: Math.sqrt(dx * dx + dy * dy + dz * dz) };
    });

    distances.sort((a, b) => a.dist - b.dist);
    setTopKIndices(distances.slice(0, 5).map(d => d.idx));
    setTimeout(() => setIsSearching(false), 500);
  };

  return (
    <section className="lp-section" id="vector-space">
      <ScrollReveal>
        <div className="section-badge">Step 3 — Hero Visual</div>
        <h2 className="section-title">FAISS Vector Space</h2>
        <p className="section-sub">50 products plotted in 3D vector space using PCA-reduced embeddings. Products with similar meanings naturally cluster together.</p>
      </ScrollReveal>

      <div className="vs-container">
        <div className="vs-ui">
          <form onSubmit={handleSearch} className="vs-search-form">
            <input
              type="text"
              placeholder="Type a query to see it in vector space..."
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              className="vs-input"
            />
            <button type="submit" className="vs-button" disabled={isSearching}>
              {isSearching ? 'Plotting...' : 'Visualize Search'}
            </button>
          </form>

          <div className="vs-legend">
            {Object.entries(catColors).map(([cat, color]) => (
              <div key={cat} className="vs-legend-item">
                <span className="vs-legend-color" style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }} />
                <span className="vs-legend-label">{cat}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="vs-canvas-wrapper">
          <Canvas camera={{ position: [0, 4, 12], fov: 50 }}>
            <color attach="background" args={['#0a0a0a']} />

            <ambientLight intensity={0.4} />
            <directionalLight position={[10, 10, 5]} intensity={0.8} />
            <pointLight position={[-5, 5, -5]} color="#f97316" intensity={0.5} distance={20} />
            <pointLight position={[5, -5, 5]} color="#b45309" intensity={0.5} distance={20} />

            <OrbitControls
              enablePan={false}
              autoRotate={!queryPos}
              autoRotateSpeed={0.4}
              maxDistance={20}
              minDistance={5}
            />

            <Stars />

            <gridHelper args={[20, 20, '#292524', '#1c1917']} position={[0, -5, 0]} />

            {data.map((item, i) => {
              const isTop = topKIndices.includes(i);
              const color = catColors[item.category] || defaultColor;
              return (
                <GlowSphere
                  key={item.id}
                  position={[item.x, item.y, item.z]}
                  color={color}
                  scale={isTop ? 1.8 : 1}
                  isTop={isTop}
                  label={item.title}
                  category={item.category}
                />
              );
            })}

            {queryPos && <QuerySphere position={queryPos} />}
            <SimilarityLines data={data} queryPos={queryPos} topKIndices={topKIndices} />
          </Canvas>
          <div className="vs-hint">🖱️ Drag to rotate • Scroll to zoom • Hover for details</div>
        </div>
      </div>
    </section>
  );
}
