/* eslint-disable react/no-unknown-property */
import { OrbitControls, Stars, Trail, Float, Text } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { Link } from "wouter";

const PLANETS = [
  { name: "Mercury", dist: 4, size: 0.3, color: "#a0826d", speed: 4.2, emissive: "#3d2b1f" },
  { name: "Venus", dist: 5.5, size: 0.5, color: "#e8c87a", speed: 3.0, emissive: "#8b6914" },
  { name: "Earth", dist: 7.2, size: 0.55, color: "#4a90d9", speed: 2.4, emissive: "#1a4a7a" },
  { name: "Mars", dist: 9, size: 0.4, color: "#c1440e", speed: 1.8, emissive: "#5c1f06" },
  { name: "Jupiter", dist: 12, size: 1.4, color: "#c88b3a", speed: 0.8, emissive: "#4a3010", rings: false },
  { name: "Saturn", dist: 15.5, size: 1.1, color: "#e8d5a3", speed: 0.6, emissive: "#6b5a2e", rings: true },
  { name: "Pluto", dist: 19, size: 0.35, color: "#d4a886", speed: 0.3, emissive: "#6b4a2e", highlight: true },
];

function Sun() {
  const ref = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (ref.current) ref.current.rotation.y += 0.001;
    if (glowRef.current) {
      glowRef.current.scale.setScalar(1 + Math.sin(state.clock.elapsedTime * 2) * 0.05);
    }
  });
  return (
    <group>
      <mesh ref={ref}>
        <sphereGeometry args={[2, 64, 64]} />
        <meshBasicMaterial color="#fff5b8" />
      </mesh>
      {/* 外发光层 */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[2.4, 32, 32]} />
        <meshBasicMaterial color="#ffaa00" transparent opacity={0.15} />
      </mesh>
      <mesh>
        <sphereGeometry args={[3, 32, 32]} />
        <meshBasicMaterial color="#ff8800" transparent opacity={0.05} />
      </mesh>
      <pointLight intensity={3} color="#fff5e0" distance={60} decay={1.5} />
      <pointLight intensity={1.5} color="#ffaa44" distance={40} decay={2} />
    </group>
  );
}
function OrbitingPlanet({
  name, dist, size, color, emissive, speed, rings, highlight,
}: (typeof PLANETS)[number]) {
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const initialAngle = useMemo(() => Math.random() * Math.PI * 2, []);

  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime * speed * 0.3 + initialAngle;
    groupRef.current.position.x = Math.cos(t) * dist;
    groupRef.current.position.z = Math.sin(t) * dist;
    groupRef.current.position.y = Math.sin(t * 0.5) * 0.3;
    if (meshRef.current) meshRef.current.rotation.y += 0.01;
  });

  return (
    <group ref={groupRef}>
      <Float speed={2} floatIntensity={0.3} rotationIntensity={0.1}>
        <mesh
          ref={meshRef}
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
        >
          <sphereGeometry args={[size, 64, 64]} />
          <meshStandardMaterial
            color={color}
            emissive={emissive}
            emissiveIntensity={hovered ? 0.8 : highlight ? 0.5 : 0.2}
            roughness={0.6}
            metalness={0.2}
          />
        </mesh>
      </Float>
      {rings && (
        <mesh rotation={[Math.PI / 2.3, 0.1, 0]}>
          <ringGeometry args={[size * 1.4, size * 2.2, 64]} />
          <meshBasicMaterial color="#ffd9a8" transparent opacity={0.35} side={THREE.DoubleSide} />
        </mesh>
      )}
      {highlight && (
        <Trail width={1.5} length={8} color="#ff00aa" attenuation={(w) => w * w}>
          <mesh visible={false}><sphereGeometry args={[0.01]} /></mesh>
        </Trail>
      )}
      {hovered && (
        <Text position={[0, size + 0.6, 0]} fontSize={0.4} color="#fff" anchorX="center">
          {name}
        </Text>
      )}
    </group>
  );
}

function OrbitLine({ radius }: { radius: number }) {
  const points = useMemo(() => {
    const pts = [];
    for (let i = 0; i <= 128; i++) {
      const angle = (i / 128) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(angle) * radius, 0, Math.sin(angle) * radius));
    }
    return pts;
  }, [radius]);
  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points]);
  return (
    <line>
      <primitive object={geometry} attach="geometry" />
      <lineBasicMaterial color="#ffffff" transparent opacity={0.06} />
    </line>
  );
}

function Nebula() {
  const ref = useRef<THREE.Points>(null);
  const { positions, colors } = useMemo(() => {
    const count = 2000;
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 20 + Math.random() * 30;
      const theta = Math.random() * Math.PI * 2;
      const phi = (Math.random() - 0.5) * 0.6;
      pos[i * 3] = r * Math.cos(theta) * Math.cos(phi);
      pos[i * 3 + 1] = r * Math.sin(phi) * 2;
      pos[i * 3 + 2] = r * Math.sin(theta) * Math.cos(phi);
      const t = Math.random();
      col[i * 3] = t < 0.33 ? 0.4 : t < 0.66 ? 1 : 0;
      col[i * 3 + 1] = t < 0.33 ? 0.1 : t < 0.66 ? 0 : 0.9;
      col[i * 3 + 2] = t < 0.33 ? 1 : t < 0.66 ? 0.67 : 1;
    }
    return { positions: pos, colors: col };
  }, []);
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.01;
  });
  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.15} vertexColors transparent opacity={0.6} sizeAttenuation />
    </points>
  );
}

function CameraRig() {
  const { camera } = useThree();
  useFrame((state) => {
    const t = state.clock.elapsedTime * 0.05;
    camera.position.y = 4 + Math.sin(t) * 1.5;
  });
  return null;
}

export default function GalaxyPage() {
  return (
    <main style={{ height: "100vh", width: "100vw", background: "#000", overflow: "hidden", position: "relative" }}>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        style={{
          position: "absolute", top: 24, left: 24, right: 24, zIndex: 10,
          display: "flex", justifyContent: "space-between", alignItems: "flex-start", pointerEvents: "none",
        }}
      >
        <div style={{ pointerEvents: "auto" }}>
          <Link href="/" style={{
            display: "inline-flex", alignItems: "center", gap: 8, padding: "8px 14px",
            borderRadius: 100, background: "rgba(255,255,255,0.06)", backdropFilter: "blur(20px)",
            border: "1px solid rgba(255,255,255,0.1)", fontFamily: "ui-monospace, monospace",
            fontSize: 12, color: "rgba(255,255,255,0.8)",
          }}>
            <ArrowLeft size={14} /> BACK
          </Link>
        </div>
        <div style={{ textAlign: "right", fontFamily: "ui-monospace, monospace", fontSize: 11, color: "rgba(255,255,255,0.4)", letterSpacing: 1.5 }}>
          <div>PLUTO SYSTEM</div>
          <div style={{ marginTop: 4, color: "rgba(255,255,255,0.25)" }}>DRAG · ZOOM · EXPLORE</div>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 2, delay: 0.8 }}
        style={{ position: "absolute", left: "50%", bottom: "6%", transform: "translateX(-50%)", zIndex: 10, textAlign: "center", pointerEvents: "none" }}
      >
        <div style={{ fontSize: 10, fontFamily: "ui-monospace, monospace", color: "rgba(255,255,255,0.3)", letterSpacing: 4, marginBottom: 8 }}>
          KUIPER BELT · 39.5 AU
        </div>
        <h1 style={{ fontSize: "clamp(32px, 5vw, 64px)", fontWeight: 200, letterSpacing: "0.2em", color: "rgba(255,255,255,0.9)", textTransform: "uppercase" }}>
          Galaxy Drift
        </h1>
      </motion.div>

      <Canvas camera={{ position: [0, 8, 20], fov: 50 }} dpr={[1, 2]}>
        <color attach="background" args={["#020108"]} />
        <fog attach="fog" args={["#020108", 30, 60]} />
        <ambientLight intensity={0.08} />
        <Sun />
        <Nebula />
        <Stars radius={100} depth={80} count={6000} factor={4} fade speed={0.3} />
        {PLANETS.map((p) => (
          <OrbitingPlanet key={p.name} {...p} />
        ))}
        {PLANETS.map((p) => (
          <OrbitLine key={`orbit-${p.name}`} radius={p.dist} />
        ))}
        <CameraRig />
        <OrbitControls enablePan={false} minDistance={8} maxDistance={40} autoRotate autoRotateSpeed={0.2} maxPolarAngle={Math.PI / 1.8} />
      </Canvas>
    </main>
  );
}
