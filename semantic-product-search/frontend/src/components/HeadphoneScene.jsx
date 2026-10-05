'use client';

import { useEffect, useRef, useState } from 'react';
import AirPodsArtwork from './AirPodsArtwork';

// AirPods Max by Mr.Philin, CC BY 4.0. See public/models/ATTRIBUTION.md.
async function loadHeadphones(T, GLTFLoader) {
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
    if (!object.isMesh) return;
    const material = object.material;
    material.envMapIntensity = .7;
    material.roughness = Math.max(material.roughness, .42);
    for (const value of Object.values(material)) {
      if (value?.isTexture) value.anisotropy = 4;
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
  });
  model.userData.finish = finish;
  return model;
}

function disposeObject(root) {
  const geometries = new Set(), materials = new Set(), textures = new Set();
  root.traverse((object) => {
    if (object.geometry) geometries.add(object.geometry);
    for (const material of [object.material].flat().filter(Boolean)) {
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    }
  });
  geometries.forEach((geometry) => geometry.dispose());
  materials.forEach((material) => material.dispose());
  textures.forEach((texture) => { texture.source?.data?.close?.(); texture.dispose(); });
}

function makeMeaningSpace(T) {
  const field = new T.Group();
  const clusters = [
    { center: [1.2, .6, .3], color: '#658a9a', count: 45 },
    { center: [-1.1, -.65, -.5], color: '#9582ae', count: 35 },
    { center: [.9, -1.05, -.4], color: '#73946b', count: 35 },
  ];
  const positions = [], colors = [];
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
  const connectionPositions = [];
  [[1.2, .6, .3], [1.45, .83, .45], [.92, .3, .6]].forEach((point) => connectionPositions.push(...query.position.toArray(), ...point));
  const connections = new T.LineSegments(new T.BufferGeometry().setAttribute('position', new T.Float32BufferAttribute(connectionPositions, 3)), new T.LineBasicMaterial({ color: '#a18956', transparent: true, opacity: .85, toneMapped: false }));
  field.add(connections);
  [1.1, 1.7, 2.25].forEach((radius) => {
    const ring = new T.Mesh(new T.TorusGeometry(radius, .003, 3, 128), new T.MeshBasicMaterial({ color: '#a7b6b5', transparent: true, opacity: .28 }));
    ring.rotation.set(.3, -.25, .1); field.add(ring);
  });
  return field;
}

export default function HeadphoneScene({ progressRef, appearanceRef, rotationRef, onUnavailable }) {
  const mountRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let disposed = false, teardown = () => {};
    const host = mountRef.current;
    async function setup() {
      try {
        const [T, { RoomEnvironment }, { GLTFLoader }] = await Promise.all([import('three'), import('three/addons/environments/RoomEnvironment.js'), import('three/addons/loaders/GLTFLoader.js')]);
        if (disposed) return;
        const renderer = new T.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        renderer.outputColorSpace = T.SRGBColorSpace;
        renderer.toneMapping = T.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.1;
        renderer.domElement.setAttribute('aria-hidden', 'true');
        host.appendChild(renderer.domElement);
        const scene = new T.Scene();
        const camera = new T.PerspectiveCamera(33, 1, .1, 50);
        camera.position.set(0, .05, 8.2);
        const pmrem = new T.PMREMGenerator(renderer);
        const room = new RoomEnvironment();
        const environment = pmrem.fromScene(room, .04);
        scene.environment = environment.texture;
        room.dispose(); pmrem.dispose();
        scene.add(new T.HemisphereLight('#ffffff', '#6d8082', 1.3));
        const light = new T.DirectionalLight('#ffffff', 2.4); light.position.set(-3, 5, 5); scene.add(light);
        const rim = new T.DirectionalLight('#ddd7f3', 1.8); rim.position.set(4, 1, -3); scene.add(rim);
        // Establish cleanup before loading so partial setup and unmounts also release resources.
        teardown = () => { disposeObject(scene); environment.dispose(); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove(); };
        const headphones = await loadHeadphones(T, GLTFLoader);
        if (disposed) { disposeObject(headphones); return; }
        const field = makeMeaningSpace(T);
        scene.add(headphones, field);
        const resize = () => {
          const width = host.clientWidth, height = host.clientHeight;
          if (!width || !height) return;
          camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.setSize(width, height);
        };
        const resizeObserver = new ResizeObserver(resize); resizeObserver.observe(host); resize();
        let frame = 0, visible = false, dragging = false, lastX = 0, manualRotation = 0;
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
          field.traverse((object) => { if (object.material) { if (object.userData.originalOpacity === undefined) object.userData.originalOpacity = object.material.opacity; object.material.opacity = object.userData.originalOpacity * cloud; object.material.transparent = true; } });
          renderer.render(scene, camera);
          host.dataset.sceneReady = 'true';
          frame = requestAnimationFrame(animate);
        };
        const start = () => { cancelAnimationFrame(frame); if (visible && !document.hidden) frame = requestAnimationFrame(animate); };
        const visibilityObserver = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; start(); }, { rootMargin: '100px' });
        visibilityObserver.observe(host);
        const pointerDown = (event) => { if (event.pointerType !== 'mouse') return; dragging = true; lastX = event.clientX; renderer.domElement.setPointerCapture(event.pointerId); };
        const pointerMove = (event) => { if (!dragging) return; manualRotation += (event.clientX - lastX) * .009; lastX = event.clientX; };
        const pointerUp = () => { dragging = false; };
        renderer.domElement.addEventListener('pointerdown', pointerDown);
        renderer.domElement.addEventListener('pointermove', pointerMove);
        renderer.domElement.addEventListener('pointerup', pointerUp);
        renderer.domElement.addEventListener('pointercancel', pointerUp);
        document.addEventListener('visibilitychange', start);
        setReady(true);
        teardown = () => {
          cancelAnimationFrame(frame); resizeObserver.disconnect(); visibilityObserver.disconnect();
          document.removeEventListener('visibilitychange', start);
          renderer.domElement.removeEventListener('pointerdown', pointerDown);
          renderer.domElement.removeEventListener('pointermove', pointerMove);
          renderer.domElement.removeEventListener('pointerup', pointerUp);
          renderer.domElement.removeEventListener('pointercancel', pointerUp);
          disposeObject(scene);
          environment.dispose(); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
        };
      } catch { if (!disposed) { setFailed(true); onUnavailable(); } teardown(); }
    }
    setup();
    return () => { disposed = true; teardown(); };
  }, [progressRef, appearanceRef, rotationRef, onUnavailable]);

  return (
    <div className={`headphone-scene ${ready && !failed ? 'is-ready' : ''}`} role="img" aria-label="AirPods Max 3D model transitioning into a schematic map of related product meanings">
      {(!ready || failed) && <div className="scene-fallback"><AirPodsArtwork /></div>}
      <div className="scene-canvas" ref={mountRef} />
    </div>
  );
}
