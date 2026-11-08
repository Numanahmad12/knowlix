"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export default function ThreeSemanticOrb({ 
  mode = "idle", // "idle" | "searching" | "hit-semantic" | "hit-exact" | "miss"
  size = 280,
  interactive = true 
}) {
  const mountRef = useRef(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || size;
    const height = container.clientHeight || size;

    // Scene & Camera
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 220;

    // WebGL Renderer with Alpha transparency for light background
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    container.appendChild(renderer.domElement);

    // Group for all rotating elements
    const orbGroup = new THREE.Group();
    scene.add(orbGroup);

    // 1. Core Sphere (Soft Teal #A8C9C8)
    const coreGeo = new THREE.IcosahedronGeometry(36, 2);
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0xa8c9c8, // Primary Teal
      wireframe: true,
      transparent: true,
      opacity: 0.35,
    });
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);
    orbGroup.add(coreMesh);

    // 2. 384 Latent Vector Nodes: Teal (#A8C9C8) + Key Knowledge Nodes in Vibrant Orange (#F45B0B)
    const nodeCount = 384;
    const nodePositions = new Float32Array(nodeCount * 3);
    const nodeColors = new Float32Array(nodeCount * 3);

    const phi = Math.PI * (3 - Math.sqrt(5));
    const radius = 68;

    // Teal: R=0.66, G=0.79, B=0.78 (#A8C9C8)
    // Orange: R=0.96, G=0.36, B=0.04 (#F45B0B)
    for (let i = 0; i < nodeCount; i++) {
      const y = 1 - (i / (nodeCount - 1)) * 2;
      const radiusAtY = Math.sqrt(1 - y * y);
      const theta = phi * i;

      const x = Math.cos(theta) * radiusAtY;
      const z = Math.sin(theta) * radiusAtY;

      const jitter = 1 + (Math.random() - 0.5) * 0.16;
      nodePositions[i * 3] = x * radius * jitter;
      nodePositions[i * 3 + 1] = y * radius * jitter;
      nodePositions[i * 3 + 2] = z * radius * jitter;

      // ~15% Key Knowledge Nodes are Vibrant Orange, remaining are Primary Teal
      const isOrangeNode = Math.random() < 0.18;
      if (isOrangeNode) {
        nodeColors[i * 3] = 0.957;     // R (244)
        nodeColors[i * 3 + 1] = 0.357; // G (91)
        nodeColors[i * 3 + 2] = 0.043; // B (11) -> Vibrant Orange #F45B0B
      } else {
        nodeColors[i * 3] = 0.659;     // R (168)
        nodeColors[i * 3 + 1] = 0.788; // G (201)
        nodeColors[i * 3 + 2] = 0.784; // B (200) -> Primary Teal #A8C9C8
      }
    }

    const nodeGeo = new THREE.BufferGeometry();
    nodeGeo.setAttribute("position", new THREE.BufferAttribute(nodePositions, 3));
    nodeGeo.setAttribute("color", new THREE.BufferAttribute(nodeColors, 3));

    // Particle texture
    const canvas = document.createElement("canvas");
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext("2d");
    const gradient = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
    gradient.addColorStop(0, "rgba(255, 255, 255, 1)");
    gradient.addColorStop(0.4, "rgba(168, 201, 200, 0.9)");
    gradient.addColorStop(1, "rgba(168, 201, 200, 0)");
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(16, 16, 16, 0, Math.PI * 2);
    ctx.fill();

    const particleTexture = new THREE.CanvasTexture(canvas);

    const nodeMat = new THREE.PointsMaterial({
      size: 5.5,
      vertexColors: true,
      map: particleTexture,
      transparent: true,
      opacity: 0.9,
      depthWrite: false,
    });

    const particles = new THREE.Points(nodeGeo, nodeMat);
    orbGroup.add(particles);

    // 3. Knowledge Graph Connections (Teal #A8C9C8)
    const lineIndices = [];
    for (let i = 0; i < nodeCount; i += 3) {
      for (let j = i + 1; j < Math.min(i + 12, nodeCount); j++) {
        const dx = nodePositions[i * 3] - nodePositions[j * 3];
        const dy = nodePositions[i * 3 + 1] - nodePositions[j * 3 + 1];
        const dz = nodePositions[i * 3 + 2] - nodePositions[j * 3 + 2];
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist < 26) {
          lineIndices.push(i, j);
        }
      }
    }

    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.BufferAttribute(nodePositions, 3));
    lineGeo.setIndex(lineIndices);

    const lineMat = new THREE.LineBasicMaterial({
      color: 0xa8c9c8, // Primary Teal
      transparent: true,
      opacity: 0.45,
    });
    const lines = new THREE.LineSegments(lineGeo, lineMat);
    orbGroup.add(lines);

    // 4. Outer Orbital Ring (Soft Teal)
    const ringGeo = new THREE.RingGeometry(82, 83.5, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0xa8c9c8,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.4,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = Math.PI / 3;
    orbGroup.add(ring);

    // Interactive mouse parallax
    let mouseX = 0;
    let mouseY = 0;
    let targetX = 0;
    let targetY = 0;

    const onMouseMove = (e) => {
      if (!interactive) return;
      const rect = container.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      targetX = x * 0.8;
      targetY = y * 0.8;
    };

    if (interactive) {
      container.addEventListener("mousemove", onMouseMove);
    }

    // Animation loop
    let animId;
    let clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const time = clock.getElapsedTime();

      // Smooth follow
      mouseX += (targetX - mouseX) * 0.05;
      mouseY += (targetY - mouseY) * 0.05;

      orbGroup.rotation.y += 0.005 + (mode === "searching" ? 0.025 : 0);
      orbGroup.rotation.x = mouseY * 0.6 + Math.sin(time * 0.4) * 0.08;
      orbGroup.rotation.z = mouseX * 0.6;

      const pulse = Math.sin(time * 2) * 0.04 + 1;
      coreMesh.scale.set(pulse, pulse, pulse);
      ring.rotation.z -= 0.003;

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth || size;
      const h = container.clientHeight || size;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
      if (interactive) {
        container.removeEventListener("mousemove", onMouseMove);
      }
      if (renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      coreGeo.dispose();
      coreMat.dispose();
      nodeGeo.dispose();
      nodeMat.dispose();
      particleTexture.dispose();
      lineGeo.dispose();
      lineMat.dispose();
      ringGeo.dispose();
      ringMat.dispose();
      renderer.dispose();
    };
  }, [mode, size, interactive]);

  return (
    <div 
      ref={mountRef} 
      className="relative flex items-center justify-center pointer-events-auto"
      style={{ width: "100%", height: "100%", minHeight: `${size}px` }}
    />
  );
}
