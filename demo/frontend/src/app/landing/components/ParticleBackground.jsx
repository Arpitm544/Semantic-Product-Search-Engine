'use client';
import { useEffect, useRef } from 'react';

export default function ParticleBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    // Respect reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let animId;
    const MOUSE = { x: -9999, y: -9999 };

    // Three depth layers for parallax effect
    // Semantic Neural Field: fewer particles, subtle colors, depth
    const LAYERS = [
      { count: 12, sizeRange: [1.2, 2.0], speed: 0.15, parallax: 0.35, opacity: [0.15, 0.3], color: '245, 245, 245' },  // near
      { count: 25, sizeRange: [0.6, 1.2], speed: 0.1,  parallax: 0.15, opacity: [0.08, 0.15], color: '161, 161, 170' },  // mid
      { count: 18, sizeRange: [0.3, 0.6], speed: 0.05, parallax: 0.05, opacity: [0.03, 0.08], color: '113, 113, 122' },  // far
      { count: 5,  sizeRange: [1.5, 2.5], speed: 0.12, parallax: 0.25, opacity: [0.1, 0.2],  color: '249, 115, 22' },   // rare semantic signals
    ];

    const CONNECTION_DIST = 110;

    let width, height;
    let allParticles = [];
    let resizeObserver;

    const resize = () => {
      width = canvas.offsetWidth || window.innerWidth;
      height = canvas.offsetHeight || window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
    };

    const createParticle = (layer) => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * layer.speed,
      vy: (Math.random() - 0.5) * layer.speed,
      size: layer.sizeRange[0] + Math.random() * (layer.sizeRange[1] - layer.sizeRange[0]),
      opacity: layer.opacity[0] + Math.random() * (layer.opacity[1] - layer.opacity[0]),
      parallax: layer.parallax,
      color: layer.color,
      layerIdx: 0,
    });

    const init = () => {
      resize();
      allParticles = [];
      LAYERS.forEach((layer, layerIdx) => {
        for (let i = 0; i < layer.count; i++) {
          const p = createParticle(layer);
          p.layerIdx = layerIdx;
          allParticles.push(p);
        }
      });
    };

    let lastScrollY = window.scrollY;

    const draw = () => {
      ctx.clearRect(0, 0, width, height);

      const currentScrollY = window.scrollY;
      const scrollDelta = currentScrollY - lastScrollY;
      lastScrollY = currentScrollY;

      // Get active pipeline stage screen position (if available)
      const activeScreenY = typeof window.__pipelineActiveScreenY === 'number'
        ? window.__pipelineActiveScreenY : height * 0.5;

      for (const p of allParticles) {
        if (!prefersReducedMotion) {
          p.x += p.vx;
          p.y += p.vy;

          // Parallax — different layers move at different rates relative to scroll
          p.y -= scrollDelta * p.parallax;

          // Very subtle drift toward active stage area (only near particles)
          if (p.layerIdx === 0) {
            const dy = activeScreenY - p.y;
            if (Math.abs(dy) < 200) {
              p.y += dy * 0.0008;
            }
          }
        }

        // Wrap around
        if (p.x < -50) p.x += width + 100;
        if (p.x > width + 50) p.x -= width + 100;
        if (p.y < -50) p.y += height + 100;
        if (p.y > height + 50) p.y -= height + 100;

        // Subtle mouse parallax (global offset)
        const targetMouseX = (MOUSE.x - width / 2) * 0.02 * p.parallax;
        const targetMouseY = (MOUSE.y - height / 2) * 0.02 * p.parallax;
        
        // Mouse repulsion (very subtle, only for near particles)
        const dx = p.x - MOUSE.x;
        const dy = p.y - MOUSE.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120 && !prefersReducedMotion && p.layerIdx === 0) {
          p.x += (dx / dist) * 0.3;
          p.y += (dy / dist) * 0.3;
        }

        // Draw particle
        ctx.beginPath();
        const renderX = p.x - targetMouseX;
        const renderY = p.y - targetMouseY;
        ctx.arc(renderX, renderY, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color}, ${p.opacity})`;
        ctx.fill();
        
        // Save render pos for connections
        p.renderX = renderX;
        p.renderY = renderY;
      }

      // Connection lines — intelligent neural look
      for (let i = 0; i < allParticles.length; i++) {
        for (let j = i + 1; j < allParticles.length; j++) {
          const a = allParticles[i];
          const b = allParticles[j];

          // Only connect particles in same or adjacent layers, and avoid connecting all orange ones
          if (Math.abs(a.layerIdx - b.layerIdx) > 1) continue;

          const dx = a.renderX - b.renderX;
          const dy = a.renderY - b.renderY;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < CONNECTION_DIST) {
            // Lines are very subtle, mostly white/gray unless an orange particle is involved
            const opacity = (1 - dist / CONNECTION_DIST) * 0.12;
            const isSemantic = a.layerIdx === 3 || b.layerIdx === 3;
            const color = isSemantic ? `rgba(249, 115, 22, ${opacity * 1.5})` : `rgba(255, 255, 255, ${opacity})`;
            
            ctx.beginPath();
            ctx.moveTo(a.renderX, a.renderY);
            ctx.lineTo(b.renderX, b.renderY);
            ctx.strokeStyle = color;
            ctx.lineWidth = isSemantic ? 0.8 : 0.4;
            ctx.stroke();
          }
        }
      }

      animId = requestAnimationFrame(draw);
    };

    const onMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      MOUSE.x = e.clientX - rect.left;
      MOUSE.y = e.clientY - rect.top;
    };

    // Use ResizeObserver for better perf
    resizeObserver = new ResizeObserver(() => {
      resize();
      // Reinitialize particles on resize
      allParticles = [];
      LAYERS.forEach((layer, layerIdx) => {
        for (let i = 0; i < layer.count; i++) {
          const p = createParticle(layer);
          p.layerIdx = layerIdx;
          allParticles.push(p);
        }
      });
    });
    resizeObserver.observe(canvas);

    canvas.addEventListener('mousemove', onMouseMove);

    init();
    draw();

    return () => {
      cancelAnimationFrame(animId);
      canvas.removeEventListener('mousemove', onMouseMove);
      if (resizeObserver) resizeObserver.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} className="particle-canvas" />;
}
