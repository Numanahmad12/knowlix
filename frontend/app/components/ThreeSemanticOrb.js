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

    // 1. Core Sphere — Direction 4: the orange sun (#FF4D00)
    const coreGeo = new THREE.IcosahedronGeometry(36, 2);
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0xff4d00, // Vivid Orange sun
      wireframe: true,
      transparent: true,
      opacity: 0.4,
    });
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);
    orbGroup.add(coreMesh);

    // 2. 384 Latent Vector Nodes: Navy (#1E2A5C) + Key Knowledge Nodes in Vivid Orange (#FF4D00)
    const nodeCount = 384;
    const nodePositions = new Float32Array(nodeCount * 3);
    const nodeColors = new Float32Array(nodeCount * 3);

    const phi = Math.PI * (3 - Math.sqrt(5));
    const radius = 68;

    // Navy: R=0.118, G=0.165, B=0.361 (#1E2A5C)
    // Orange: R=1.0, G=0.302, B=0.0 (#FF4D00)
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

      // ~18% Key Knowledge Nodes are Vivid Orange, remaining are Navy
      const isOrangeNode = Math.random() < 0.18;
      if (isOrangeNode) {
        nodeColors[i * 3] = 1.0;       // R (255)
        nodeColors[i * 3 + 1] = 0.302; // G (77)
        nodeColors[i * 3 + 2] = 0.0;   // B (0) -> Vivid Orange #FF4D00
      } else {
        nodeColors[i * 3] = 0.118;     // R (30)
        nodeColors[i * 3 + 1] = 0.165; // G (42)
        nodeColors[i * 3 + 2] = 0.361; // B (92) -> Navy #1E2A5C
      }
    }

    const nodeGeo = new THREE.BufferGeometry();
    nodeGeo.setAttribute("position", new THREE.BufferAttribute(nodePositions, 3));
    nodeGeo.setAttribute("color", new THREE.BufferAttribute(nodeColors, 3));

    // Particle texture (neutral white sprite — vertex colours carry the navy/orange)
    const canvas = document.createElement("canvas");
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext("2d");
    const gradient = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
    gradient.addColorStop(0, "rgba(255, 255, 255, 1)");
    gradient.addColorStop(0.4, "rgba(255, 255, 255, 0.9)");
    gradient.addColorStop(1, "rgba(255, 255, 255, 0)");
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

    // 3. Knowledge Graph Connections (Navy #1E2A5C)
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
      color: 0x1e2a5c, // Navy
      transparent: true,
      opacity: 0.35,
    });
    const lines = new THREE.LineSegments(lineGeo, lineMat);
    orbGroup.add(lines);

    // 4. Outer Orbital Ring (Navy)
    const ringGeo = new THREE.RingGeometry(82, 83.5, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x1e2a5c,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.45,
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

    // Respect prefers-reduced-motion: render the orb static, never spin it.
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Animation loop
    let animId;
    let clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const time = clock.getElapsedTime();

      if (!prefersReducedMotion) {
        // Smooth follow
        mouseX += (targetX - mouseX) * 0.05;
        mouseY += (targetY - mouseY) * 0.05;

        orbGroup.rotation.y += 0.005 + (mode === "searching" ? 0.025 : 0);
        orbGroup.rotation.x = mouseY * 0.6 + Math.sin(time * 0.4) * 0.08;
        orbGroup.rotation.z = mouseX * 0.6;

        const pulse = Math.sin(time * 2) * 0.04 + 1;
        coreMesh.scale.set(pulse, pulse, pulse);
        ring.rotation.z -= 0.003;
      }

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
      aria-hidden="true"
      className="relative flex items-center justify-center pointer-events-auto"
      style={{ width: "100%", height: "100%", minHeight: `${size}px` }}
    />
  );
}
