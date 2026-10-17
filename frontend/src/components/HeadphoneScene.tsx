'use client';
import { classes } from '@/lib/classes';

import { useEffect, useRef, useState } from 'react';
import type * as THREE from 'three';
import type { GLTFLoader as Loader } from 'three/addons/loaders/GLTFLoader.js';
import type { RoomEnvironment as Room } from 'three/addons/environments/RoomEnvironment.js';
import type { MutableRefObject } from 'react';
import HeadphonePoster from './HeadphonePoster';

// AirPods Max by Mr.Philin, CC BY 4.0. See public/models/ATTRIBUTION.md.
async function loadHeadphones(T: typeof THREE, GLTFLoader: typeof Loader) {
  const gltf = await new GLTFLoader().loadAsync('/models/airpods-max.glb');
  const asset = gltf.scene;
  asset.updateMatrixWorld(true);
  const bounds = new T.Box3().setFromObject(asset);
  const center = bounds.getCenter(new T.Vector3());
  const size = bounds.getSize(new T.Vector3());
  const normalized = new T.Group();
  asset.position.sub(center);
  normalized.add(asset);
  normalized.scale.setScalar(3.55 / Math.max(size.x, size.y, size.z));
  const model = new T.Group();
  model.add(normalized);
  const finish = { value: 1 };
  asset.traverse((object) => {
    if (!(object instanceof T.Mesh)) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
    if (!(material instanceof T.MeshStandardMaterial)) continue;
    material.envMapIntensity = .7;
    material.roughness = Math.max(material.roughness, .42);
    for (const value of Object.values(material)) {
      if (value instanceof T.Texture) value.anisotropy = 4;
    }
    // Preserve the artist's surface detail while offering a silver color study.
    // The green setting retains the original texture color.
    material.onBeforeCompile = (shader) => {
      shader.uniforms.silverFinish = finish;
      shader.fragmentShader = 'uniform float silverFinish;\n' + shader.fragmentShader;
      shader.fragmentShader = shader.fragmentShader.replace('#include <map_fragment>', `
        #include <map_fragment>
        float surfaceTone = dot(diffuseColor.rgb, vec3(.2126, .7152, .0722));
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(surfaceTone), silverFinish);
      `);
    };
    material.customProgramCacheKey = () => 'airpods-finish-v1';
    }
  });
  model.userData.finish = finish;
  return model;
}

function disposeObject(root: THREE.Object3D) {
  const geometries = new Set<THREE.BufferGeometry>(), materials = new Set<THREE.Material>(), textures = new Set<THREE.Texture>();
  root.traverse((object) => {
    if (!('geometry' in object) || !('material' in object)) return;
    const mesh = object as THREE.Mesh;
    if (mesh.geometry) geometries.add(mesh.geometry);
    for (const material of [mesh.material].flat().filter(Boolean)) {
      materials.add(material);
      for (const value of Object.values(material)) if (value && typeof value === 'object' && 'isTexture' in value) textures.add(value as THREE.Texture);
    }
  });
  geometries.forEach((geometry) => geometry.dispose());
  materials.forEach((material) => material.dispose());
  textures.forEach((texture) => { const data: unknown = texture.source?.data; if (typeof ImageBitmap !== 'undefined' && data instanceof ImageBitmap) data.close(); texture.dispose(); });
}

function makeMeaningSpace(T: typeof THREE) {
  const field = new T.Group();
  const clusters = [
    { center: [1.2, .6, .3], color: '#658a9a', count: 45 },
    { center: [-1.1, -.65, -.5], color: '#9582ae', count: 35 },
    { center: [.9, -1.05, -.4], color: '#73946b', count: 35 },
  ];
  const positions: number[] = [], colors: number[] = [];
  let seed = 39;
  const random = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
  clusters.forEach(({ center, color, count }) => {
    const c = new T.Color(color);
    for (let index = 0; index < count; index++) {
      positions.push(center[0] + (random() - .5) * 1.4, center[1] + (random() - .5) * 1.1, center[2] + (random() - .5) * 1.2);
      colors.push(c.r, c.g, c.b);
    }
  });
  const geometry = new T.BufferGeometry();
  geometry.setAttribute('position', new T.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('color', new T.Float32BufferAttribute(colors, 3));
  const dots = new T.Points(geometry, new T.PointsMaterial({ size: .105, vertexColors: true, transparent: true, opacity: .95, toneMapped: false }));
  field.add(dots);
  const query = new T.Mesh(new T.SphereGeometry(.09, 20, 16), new T.MeshBasicMaterial({ color: '#bd985a', transparent: true }));
  query.position.set(.05, .75, .9); field.add(query);
  const connectionPositions: number[] = [];
  [[1.2, .6, .3], [1.45, .83, .45], [.92, .3, .6]].forEach((point) => connectionPositions.push(...query.position.toArray(), ...point));
  const connections = new T.LineSegments(new T.BufferGeometry().setAttribute('position', new T.Float32BufferAttribute(connectionPositions, 3)), new T.LineBasicMaterial({ color: '#a18956', transparent: true, opacity: .85, toneMapped: false }));
  field.add(connections);
  [1.1, 1.7, 2.25].forEach((radius) => {
    const ring = new T.Mesh(new T.TorusGeometry(radius, .003, 3, 128), new T.MeshBasicMaterial({ color: '#a7b6b5', transparent: true, opacity: .28 }));
    ring.rotation.set(.3, -.25, .1); field.add(ring);
  });
  return field;
}

export default function HeadphoneScene({ progressRef, appearanceRef, rotationRef }: { progressRef: MutableRefObject<number>; appearanceRef: MutableRefObject<string>; rotationRef: MutableRefObject<number> }) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let disposed = false, teardown = () => {};
    setReady(false);
    setFailed(false);
    const fail = () => {
      if (disposed) return;
      disposed = true;
      clearTimeout(timeout);
      setReady(false);
      setFailed(true);
      if (mountRef.current) delete mountRef.current.dataset.sceneReady;
      teardown();
    };
    const timeout = setTimeout(fail, 20000);
    const host = mountRef.current;
    if (!host) { clearTimeout(timeout); return; }
    async function setup(host: HTMLDivElement) {
      let renderer: THREE.WebGLRenderer;
      let scene: THREE.Scene;
      let pmrem: THREE.PMREMGenerator | null;
      let room: Room | null;
      let environment: THREE.WebGLRenderTarget | undefined;
      let resizeObserver: ResizeObserver | undefined, visibilityObserver: IntersectionObserver | undefined, frame = 0;
      let onVisibilityChange: (() => void) | undefined;
      let pointerDown: ((event: PointerEvent) => void) | undefined;
      let pointerMove: ((event: PointerEvent) => void) | undefined;
      let pointerUp: (() => void) | undefined;
      let cleaned = false;
      const onContextLost = (event: Event) => { event.preventDefault(); fail(); };
      const cleanup = () => {
        if (cleaned) return;
        cleaned = true;
        cancelAnimationFrame(frame);
        resizeObserver?.disconnect(); visibilityObserver?.disconnect();
        if (onVisibilityChange) document.removeEventListener('visibilitychange', onVisibilityChange);
        if (renderer?.domElement) {
          renderer.domElement.removeEventListener('webglcontextlost', onContextLost);
          if (pointerDown) renderer.domElement.removeEventListener('pointerdown', pointerDown);
          if (pointerMove) renderer.domElement.removeEventListener('pointermove', pointerMove);
          if (pointerUp) {
            renderer.domElement.removeEventListener('pointerup', pointerUp);
            renderer.domElement.removeEventListener('pointercancel', pointerUp);
          }
        }
        if (scene) disposeObject(scene);
        environment?.dispose(); room?.dispose(); pmrem?.dispose();
        if (renderer) {
          renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
        }
      };
      try {
        const [T, { RoomEnvironment }, { GLTFLoader }] = await Promise.all([import('three'), import('three/addons/environments/RoomEnvironment.js'), import('three/addons/loaders/GLTFLoader.js')]);
        if (disposed) return;
        renderer = new T.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' });
        teardown = cleanup;
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        renderer.outputColorSpace = T.SRGBColorSpace;
        renderer.toneMapping = T.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.1;
        renderer.domElement.setAttribute('aria-hidden', 'true');
        host.appendChild(renderer.domElement);
        renderer.domElement.addEventListener('webglcontextlost', onContextLost);
        scene = new T.Scene();
        const camera = new T.PerspectiveCamera(33, 1, .1, 50);
        camera.position.set(0, .05, 8.2);
        pmrem = new T.PMREMGenerator(renderer);
        room = new RoomEnvironment();
        environment = pmrem.fromScene(room, .04);
        scene.environment = environment.texture;
        room.dispose(); pmrem.dispose();
        room = null; pmrem = null;
        scene.add(new T.HemisphereLight('#ffffff', '#6d8082', 1.3));
        const light = new T.DirectionalLight('#ffffff', 2.4); light.position.set(-3, 5, 5); scene.add(light);
        const rim = new T.DirectionalLight('#ddd7f3', 1.8); rim.position.set(4, 1, -3); scene.add(rim);
        const headphones = await loadHeadphones(T, GLTFLoader);
        if (disposed) { disposeObject(headphones); return; }
        scene.add(headphones);
        const field = makeMeaningSpace(T);
        scene.add(field);
        const resize = () => {
          const width = host.clientWidth, height = host.clientHeight;
          if (!width || !height) return;
          camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.setSize(width, height);
        };
        resizeObserver = new ResizeObserver(resize); resizeObserver.observe(host); resize();
        let visible = false, dragging = false, lastX = 0, manualRotation = 0;
        let smoothed = progressRef.current;
        const lerp = T.MathUtils.lerp;
        const animate = (time = 0) => {
          if (disposed || !visible || document.hidden) return;
          smoothed = lerp(smoothed, progressRef.current, .09);
          const cloud = T.MathUtils.smoothstep(smoothed, .43, .56) * (1 - T.MathUtils.smoothstep(smoothed, .72, .81));
          headphones.visible = cloud < .98;
          const scale = lerp(1 + T.MathUtils.smoothstep(smoothed, .12, .38) * .12, .34, cloud);
          headphones.scale.setScalar(scale);
          headphones.position.set(lerp(0, 1.6, cloud), Math.sin(time * .00065) * .04 - .05, lerp(0, -.8, cloud));
          headphones.rotation.set(.12 + cloud * .12, -.95 + smoothed * Math.PI * 2 + manualRotation + rotationRef.current, -.06 + Math.sin(smoothed * Math.PI) * .12);
          headphones.userData.finish.value = appearanceRef.current === 'sage' ? 0 : 1;
          field.visible = cloud > .01;
          field.rotation.y = -.2 + smoothed * .45;
          field.scale.setScalar(lerp(.4, 1.04, cloud));
          field.traverse((object) => {
            if (!(object instanceof T.Mesh || object instanceof T.Points || object instanceof T.Line)) return;
            const materials = Array.isArray(object.material) ? object.material : [object.material];
            for (const material of materials) {
              if (material.userData.originalOpacity === undefined) material.userData.originalOpacity = material.opacity;
              material.opacity = material.userData.originalOpacity * cloud;
              material.transparent = true;
            }
          });
          try {
            renderer.render(scene, camera);
          } catch {
            fail();
            return;
          }
          if (host.dataset.sceneReady !== 'true') {
            host.dataset.sceneReady = 'true';
            setReady(true);
          }
          frame = requestAnimationFrame(animate);
        };
        const start = () => { cancelAnimationFrame(frame); if (visible && !document.hidden) frame = requestAnimationFrame(animate); };
        visibilityObserver = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; start(); }, { rootMargin: '100px' });
        visibilityObserver.observe(host);
        pointerDown = (event) => { if (event.button !== 0) return; event.preventDefault(); dragging = true; lastX = event.clientX; renderer.domElement.setPointerCapture(event.pointerId); };
        pointerMove = (event) => { if (!dragging) return; manualRotation += (event.clientX - lastX) * .009; lastX = event.clientX; };
        pointerUp = () => { dragging = false; };
        renderer.domElement.addEventListener('pointerdown', pointerDown);
        renderer.domElement.addEventListener('pointermove', pointerMove);
        renderer.domElement.addEventListener('pointerup', pointerUp);
        renderer.domElement.addEventListener('pointercancel', pointerUp);
        onVisibilityChange = start;
        document.addEventListener('visibilitychange', onVisibilityChange);
        clearTimeout(timeout);
      } catch {
        fail();
      }
    }
    setup(host);
    return () => { disposed = true; clearTimeout(timeout); delete host.dataset.sceneReady; teardown(); };
  }, [progressRef, appearanceRef, rotationRef, attempt]);

  return (
    <div className={classes(`headphone-scene ${ready && !failed ? 'is-ready' : ''}`)} role="group" aria-label="AirPods Max product preview">
      <div className={`absolute inset-0 z-10 transition-opacity duration-500 motion-reduce:transition-none ${ready && !failed ? 'pointer-events-none opacity-0' : 'opacity-100'}`} aria-hidden={ready && !failed}>
        <HeadphonePoster loading={!ready && !failed} failed={failed} onRetry={() => setAttempt(value => value + 1)} />
      </div>
      <div className={`scene-canvas ${ready && !failed ? 'opacity-100' : 'opacity-0'} transition-opacity duration-500 motion-reduce:transition-none absolute [inset:0] [&_canvas]:block [&_canvas]:w-[100%] [&_canvas]:h-[100%] [&_canvas]:cursor-grab [&_canvas]:touch-pan-y [&_canvas:active]:cursor-grabbing`} ref={mountRef} />
    </div>
  );
}
