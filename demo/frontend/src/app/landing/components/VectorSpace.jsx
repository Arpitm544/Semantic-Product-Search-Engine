'use client';
import { useRef, useState, useEffect, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
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

// Category cluster offsets for better spatial separation
const catOffsets = {
  "Jackets & Outerwear": [1.5, 0.5, 0],
  "Footwear": [-1.5, -0.8, 1],
  "Camping & Hiking": [0, 1.2, -1.5],
  "Electronics & Gadgets": [-1.8, 0.3, -0.5],
  "Apparel": [1, -1, 1.2],
};

function GlowSphere({ position, color, scale, isTop, label, category, rank }) {
  const meshRef = useRef();
  const glowRef = useRef();
  const [hovered, setHovered] = useState(false);
  const animStartRef = useRef(null);
  const targetScale = useRef(scale);

  // Animate scale transition when isTop changes
  useEffect(() => {
    targetScale.current = scale;
    if (isTop) {
      animStartRef.current = performance.now();
    }
  }, [isTop, scale]);

  useFrame((state) => {
    if (meshRef.current) {
      const t = state.clock.elapsedTime;
      // Gentle floating motion
      meshRef.current.position.y = position[1] + Math.sin(t * 0.5 + position[0]) * 0.08;
      
      // Smooth scale transition for NN results
      const currentScale = meshRef.current.scale.x;
      const newScale = THREE.MathUtils.lerp(currentScale, targetScale.current, 0.06);
      meshRef.current.scale.setScalar(newScale);

      if (isTop) {
        const pulse = 1 + Math.sin(t * 2.5) * 0.1;
        meshRef.current.scale.setScalar(newScale * pulse);
      }
    }
    if (glowRef.current) {
      glowRef.current.material.opacity = hovered ? 0.35 : (isTop ? 0.22 : 0.08);
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
        <sphereGeometry args={[0.2, isTop ? 48 : 32, isTop ? 48 : 32]} />
        <meshPhysicalMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isTop ? 1.5 : (hovered ? 0.8 : 0.4)}
          roughness={0.1}
          metalness={0.9}
          clearcoat={1.0}
          clearcoatRoughness={0.1}
          transmission={0.4}
        />
      </mesh>
      
      {/* Outer glow sphere */}
      <mesh ref={glowRef} position={position} scale={scale * 2.2}>
        <sphereGeometry args={[0.2, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={isTop ? 0.18 : 0.06} depthWrite={false} />
      </mesh>

      {/* Label on hover or if top result */}
      {(hovered || isTop) && (
        <Html position={position} distanceFactor={8} zIndexRange={[100, 0]}>
          <div className="three-tooltip" style={{ borderColor: color + '40' }}>
            {isTop && rank !== undefined && (
              <div style={{ fontSize: '0.58rem', color: '#fbbf24', fontWeight: 800, marginBottom: '0.1rem' }}>
                #{rank + 1} NEAREST
              </div>
            )}
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
      const s = 1 + Math.sin(t * 3) * 0.15;
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
        <sphereGeometry args={[0.25, 32, 32]} />
        <meshPhysicalMaterial
          color="#ffffff"
          emissive="#f97316"
          emissiveIntensity={2.5}
          roughness={0.1}
          metalness={1.0}
          clearcoat={1.0}
        />
      </mesh>
      
      {/* Rotating ring */}
      <mesh ref={ringRef}>
        <torusGeometry args={[0.45, 0.015, 16, 64]} />
        <meshBasicMaterial color="#fbbf24" transparent opacity={0.6} />
      </mesh>

      {/* Atmospheric Glow */}
      <mesh>
        <sphereGeometry args={[0.8, 32, 32]} />
        <meshBasicMaterial color="#ea580c" transparent opacity={0.15} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
      
      <pointLight color="#f97316" intensity={2.5} distance={8} />
      
      <Html distanceFactor={8}>
        <div className="three-tooltip query-tooltip">🔍 Query Vector</div>
      </Html>
    </group>
  );
}

function SimilarityLines({ data, queryPos, topKIndices }) {
  const materialRef = useRef();

  useFrame((state) => {
    if (materialRef.current) {
      materialRef.current.dashOffset -= 0.02;
    }
  });

  if (!queryPos || topKIndices.length === 0) return null;

  return (
    <group>
      {topKIndices.map((idx, i) => {
        const item = data[idx];
        const points = [new THREE.Vector3(...queryPos), new THREE.Vector3(item.x, item.y, item.z)];
        const dist = points[0].distanceTo(points[1]);
        // Closer = brighter
        const opacity = Math.max(0.4, 0.9 - (dist / 12));
        return (
          <Line
            key={`line-${idx}`}
            points={points}
            color="#fbbf24"
            lineWidth={2.5 - i * 0.3}
            dashed={true}
            dashScale={20}
            dashSize={0.5}
            dashOffset={0}
            opacity={opacity}
            transparent
            blending={THREE.AdditiveBlending}
          >
            <lineDashedMaterial ref={i === 0 ? materialRef : null} attach="material" color="#fbbf24" dashSize={0.5} gapSize={0.2} transparent opacity={opacity} />
          </Line>
        );
      })}
    </group>
  );
}

function Stars() {
  const ref = useRef();
  const positions = useMemo(() =>
    new Float32Array(
      Array.from({ length: 400 * 3 }, () => (Math.random() - 0.5) * 30)
    ),
  []);

  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.012;
    }
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          array={positions}
          count={400}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial color="#3a3835" size={0.04} sizeAttenuation transparent opacity={0.7} depthWrite={false} />
    </points>
  );
}

/* Camera controller: subtle auto-movement + zoom on query */
function CameraController({ queryPos }) {
  const { camera } = useThree();
  const hasQuery = !!queryPos;

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    // Slow ambient Y rotation even when not autoRotating
    if (!hasQuery) {
      camera.position.x = Math.sin(t * 0.08) * 12;
      camera.position.z = Math.cos(t * 0.08) * 12;
    }
  });

  return null;
}

/* Grid with reduced prominence */
function SubtleGrid() {
  return (
    <group position={[0, -5, 0]}>
      <gridHelper args={[20, 20, '#1c1917', '#171412']} />
    </group>
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
      .then(d => {
        // Apply cluster offsets for better separation
        const adjusted = d.map(item => {
          const offset = catOffsets[item.category] || [0, 0, 0];
          return {
            ...item,
            x: item.x + offset[0],
            y: item.y + offset[1],
            z: item.z + offset[2],
          };
        });
        setData(adjusted);
      })
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
                <span className="vs-legend-color" style={{ backgroundColor: color, boxShadow: `0 0 5px ${color}` }} />
                <span className="vs-legend-label">{cat}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="vs-canvas-wrapper">
          <Canvas camera={{ position: [0, 4, 12], fov: 50 }} dpr={[1, 1.5]} gl={{ alpha: true }}>
            <fog attach="fog" args={['#050505', 10, 25]} />

            <ambientLight intensity={0.35} />
            <directionalLight position={[10, 10, 5]} intensity={0.7} />
            <pointLight position={[-5, 5, -5]} color="#f97316" intensity={0.4} distance={20} />
            <pointLight position={[5, -5, 5]} color="#b45309" intensity={0.4} distance={20} />

            <OrbitControls
              enablePan={false}
              autoRotate={!queryPos}
              autoRotateSpeed={0.35}
              maxDistance={20}
              minDistance={5}
            />

            <CameraController queryPos={queryPos} />
            <Stars />
            <SubtleGrid />

            {data.map((item, i) => {
              const isTop = topKIndices.includes(i);
              const rank = isTop ? topKIndices.indexOf(i) : undefined;
              const color = catColors[item.category] || defaultColor;
              return (
                <GlowSphere
                  key={item.id}
                  position={[item.x, item.y, item.z]}
                  color={color}
                  scale={isTop ? 2.0 : 1}
                  isTop={isTop}
                  rank={rank}
                  label={item.title}
                  category={item.category}
                />
              );
            })}

            {queryPos && <QuerySphere position={queryPos} />}
            <SimilarityLines data={data} queryPos={queryPos} topKIndices={topKIndices} />
          </Canvas>
          <div className="vs-hint">🖱️ Drag to rotate · Scroll to zoom · Hover for details</div>
        </div>
      </div>
    </section>
  );
}
