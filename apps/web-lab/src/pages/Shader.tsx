import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link } from "wouter";

// Fragment shader — 自写的程序化噪声 + 流动液体 + 鼠标交互
// 灵感: Perlin/Simplex 噪声 + FBM (Fractal Brownian Motion) + 时间 + 鼠标 uniform
const FRAG = /* glsl */ `
precision highp float;

uniform vec2 u_resolution;
uniform float u_time;
uniform vec2 u_mouse;

// 3D 噪声 (基于 Inigo Quilez 的 hash 函数, 自己组合实现)
float hash(vec3 p) {
  p = fract(p * 0.3183099 + 0.1);
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float noise(vec3 x) {
  vec3 i = floor(x);
  vec3 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash(i + vec3(0,0,0)), hash(i + vec3(1,0,0)), f.x),
                 mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x),
                 mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y), f.z);
}

// FBM = 多倍频噪声叠加
float fbm(vec3 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p *= 2.0;
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / u_resolution.y;
  vec2 m = (u_mouse - 0.5 * u_resolution.xy) / u_resolution.y;

  // 鼠标 → 引力中心
  vec2 toMouse = uv - m;
  float distToMouse = length(toMouse);
  uv += normalize(toMouse) * 0.3 * exp(-distToMouse * 3.0);

  float t = u_time * 0.15;

  // 多层 FBM 营造液体流动
  vec3 q = vec3(uv * 2.0, t);
  float n1 = fbm(q + vec3(fbm(q * 1.3), fbm(q + 2.5), 0.0));
  float n2 = fbm(q * 1.8 + vec3(t * 0.3, 0.0, t * 0.5));

  // 3 个品牌色混色
  vec3 c1 = vec3(0.36, 0.24, 1.0);   // violet
  vec3 c2 = vec3(1.0, 0.0, 0.67);    // magenta
  vec3 c3 = vec3(0.0, 0.94, 1.0);    // cyan
  vec3 c4 = vec3(1.0, 0.84, 0.0);    // gold

  vec3 col = mix(c1, c2, smoothstep(0.0, 1.0, n1));
  col = mix(col, c3, smoothstep(0.3, 0.8, n2));
  col = mix(col, c4, smoothstep(0.6, 0.95, n1 * n2));

  // 暗角
  float vignette = 1.0 - 0.4 * length(uv);
  col *= vignette;

  // 颗粒感 (film grain)
  col += (hash(vec3(gl_FragCoord.xy, u_time)) - 0.5) * 0.04;

  gl_FragColor = vec4(col, 1.0);
}
`;

const VERT = /* glsl */ `
attribute vec2 a_position;
void main() {
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

export default function ShaderPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const gl = canvas.getContext("webgl");
    if (!gl) return;

    // resize
    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      gl.viewport(0, 0, canvas.width, canvas.height);
    };
    resize();
    window.addEventListener("resize", resize);
    mouseRef.current = {
      x: window.innerWidth / 2,
      y: window.innerHeight / 2,
    };
    const handleMouse = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: canvas.height - e.clientY };
    };
    window.addEventListener("mousemove", handleMouse);

    // 编译 shader
    const compile = (type: number, src: string) => {
      const s = gl.createShader(type)!;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
        console.error(gl.getShaderInfoLog(s));
      }
      return s;
    };
    const vs = compile(gl.VERTEX_SHADER, VERT);
    const fs = compile(gl.FRAGMENT_SHADER, FRAG);
    const program = gl.createProgram()!;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    gl.useProgram(program);

    // 全屏四边形
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
      gl.STATIC_DRAW,
    );
    const aPos = gl.getAttribLocation(program, "a_position");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

    const uRes = gl.getUniformLocation(program, "u_resolution");
    const uTime = gl.getUniformLocation(program, "u_time");
    const uMouse = gl.getUniformLocation(program, "u_mouse");

    let raf = 0;
    const start = performance.now();
    const loop = () => {
      const t = (performance.now() - start) / 1000;
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform1f(uTime, t);
      gl.uniform2f(uMouse, mouseRef.current.x, mouseRef.current.y);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      raf = requestAnimationFrame(loop);
    };
    loop();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", handleMouse);
    };
  }, []);

  return (
    <main
      style={{
        height: "100vh",
        width: "100vw",
        background: "#000",
        overflow: "hidden",
        position: "relative",
      }}
    >
      <canvas
        ref={canvasRef}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
      />

      {/* 浮动 UI */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        style={{
          position: "absolute",
          top: 24,
          left: 24,
          right: 24,
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <Link
          href="/"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 14px",
            borderRadius: 100,
            background: "rgba(0,0,0,0.35)",
            backdropFilter: "blur(20px)",
            border: "1px solid rgba(255,255,255,0.15)",
            fontFamily: "ui-monospace, monospace",
            fontSize: 12,
            color: "#fff",
          }}
        >
          <ArrowLeft size={14} />
          EXP/002
        </Link>
        <div
          style={{
            textAlign: "right",
            fontFamily: "ui-monospace, monospace",
            fontSize: 11,
            color: "#fff",
            letterSpacing: 1.5,
            textShadow: "0 2px 8px rgba(0,0,0,0.4)",
          }}
        >
          <div>PROCEDURAL BLOOM</div>
          <div style={{ marginTop: 4, opacity: 0.6 }}>MOVE MOUSE · DISTORT</div>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1.5, delay: 0.5 }}
        style={{
          position: "absolute",
          left: "50%",
          bottom: "8%",
          transform: "translateX(-50%)",
          textAlign: "center",
          pointerEvents: "none",
        }}
      >
        <h1
          style={{
            fontSize: "clamp(40px, 8vw, 100px)",
            fontWeight: 900,
            color: "#fff",
            mixBlendMode: "difference",
            letterSpacing: "-0.04em",
          }}
        >
          FBM × Noise
        </h1>
      </motion.div>
    </main>
  );
}
