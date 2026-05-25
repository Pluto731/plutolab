import { motion } from "framer-motion";
import { ArrowUpRight, FlaskConical } from "lucide-react";
import { useState } from "react";
import { Link } from "wouter";

// 4 张风格预览卡 — 每张点击进入对应实验
// 入口本身就是个"实验作品"，故意混排不规整，跟"非大众化"主题呼应
const experiments = [
  {
    href: "/galaxy",
    code: "001",
    title: "Galaxy Drift",
    subtitle: "Spatial 3.5D · WebGL",
    desc: "穿越柯伊伯带, 每个 Phase 是一颗自定义星球",
    tech: "Three.js · R3F · PBR",
    gradient:
      "radial-gradient(circle at 30% 40%, #5b3eff 0%, #ff00aa 40%, #000 80%)",
    rotate: -2,
    accent: "#ff00aa",
  },
  {
    href: "/shader",
    code: "002",
    title: "Procedural Bloom",
    subtitle: "Generative · GLSL",
    desc: "每次刷新都不同 · 鼠标搅动液态噪声 · Perlin × FBM",
    tech: "Fragment Shader · GLSL",
    gradient:
      "conic-gradient(from 90deg at 50% 50%, #00f0ff 0%, #5b3eff 25%, #ff00aa 50%, #ffd700 75%, #00f0ff 100%)",
    rotate: 1.5,
    accent: "#00f0ff",
  },
  {
    href: "/y2k",
    code: "003",
    title: "Aero Y2K",
    subtitle: "Frutiger Aero · 复古",
    desc: "Windows XP / iPod nano 美学 · 金属反光 · 磨砂玻璃",
    tech: "Pure CSS · Houdini",
    gradient:
      "linear-gradient(135deg, #b9e3ff 0%, #6fb8ff 40%, #ffffff 70%, #c5a8ff 100%)",
    rotate: -1,
    accent: "#6fb8ff",
  },
  {
    href: "/login",
    code: "004",
    title: "Character Login",
    subtitle: "角色动画登录页",
    desc: "拟人化角色伴你登录 · 密码输入时眼睛会动",
    tech: "SVG · Framer Motion",
    gradient:
      "linear-gradient(135deg, #ffd700 0%, #ff7a00 50%, #ff00aa 100%)",
    rotate: 2.5,
    accent: "#ffd700",
  },
];

export default function IndexPage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#000",
        color: "#fff",
        padding: "max(8vh, 64px) max(4vw, 32px)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 背景纹理 — 颗粒 + 暗纹 */}
      <NoiseBackground />

      {/* Header */}
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "8vh",
          position: "relative",
          zIndex: 1,
        }}
      >
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
              color: "rgba(255,255,255,0.4)",
              letterSpacing: 2,
              marginBottom: 24,
            }}
          >
            <FlaskConical size={14} />
            <span>FRONTEND / EXPERIMENTAL / LAB</span>
            <span style={{ color: "var(--accent)" }}>● LIVE</span>
          </div>
          <h1
            style={{
              fontSize: "clamp(48px, 9vw, 140px)",
              fontWeight: 900,
              lineHeight: 0.85,
              letterSpacing: "-0.04em",
              marginBottom: 16,
            }}
          >
            PLUTOLAB
            <br />
            <span
              style={{
                background:
                  "linear-gradient(90deg, #ff00aa, #ffd700, #00f0ff, #ff00aa)",
                backgroundSize: "300% 100%",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                animation: "shineX 6s linear infinite",
              }}
            >
              LAB / 实验场
            </span>
          </h1>
          <p
            style={{
              fontSize: 16,
              color: "rgba(255,255,255,0.5)",
              maxWidth: 480,
              lineHeight: 1.6,
            }}
          >
            非大众化前端探索 · 3D 渲染 · Shader 程序化艺术 · 复古拟物 · 角色动画 ·
            每一个都是独立宇宙
          </p>
        </div>

        <div style={{ textAlign: "right" }}>
          <Link
            href="http://23.95.25.153/"
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
              color: "rgba(255,255,255,0.4)",
              borderBottom: "1px solid rgba(255,255,255,0.2)",
              paddingBottom: 4,
            }}
          >
            ← 回 PlutoLab 主站
          </Link>
        </div>
      </motion.header>

      {/* 卡片墙 — 故意每张歪一点, 不对称 */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 28,
          position: "relative",
          zIndex: 1,
        }}
      >
        {experiments.map((exp, i) => (
          <ExperimentCard key={exp.code} exp={exp} index={i} />
        ))}
      </section>

      {/* Footer */}
      <footer
        style={{
          marginTop: "12vh",
          paddingTop: 32,
          borderTop: "1px solid rgba(255,255,255,0.1)",
          display: "flex",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 16,
          fontFamily: "ui-monospace, monospace",
          fontSize: 11,
          color: "rgba(255,255,255,0.35)",
          letterSpacing: 1,
          position: "relative",
          zIndex: 1,
        }}
      >
        <span>© 2026 PlutoLab Lab</span>
        <span>EXPERIMENTAL · NOT FOR PRODUCTION</span>
        <span>v0.0.1</span>
      </footer>

      <style>{`
        @keyframes shineX {
          0% { background-position: 0% 50%; }
          100% { background-position: 300% 50%; }
        }
      `}</style>
    </main>
  );
}

type Exp = (typeof experiments)[number];

function ExperimentCard({ exp, index }: { exp: Exp; index: number }) {
  const [hover, setHover] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 30, rotate: exp.rotate }}
      animate={{ opacity: 1, y: 0, rotate: exp.rotate }}
      transition={{ duration: 0.6, delay: 0.1 + index * 0.1 }}
      whileHover={{ y: -8, rotate: 0, scale: 1.02 }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{ transformOrigin: "center" }}
    >
      <Link href={exp.href}>
        <article
          style={{
            position: "relative",
            aspectRatio: "4 / 5",
            borderRadius: 20,
            overflow: "hidden",
            cursor: "pointer",
            background: "#0a0a0a",
            border: "1px solid rgba(255,255,255,0.08)",
            transition: "border-color 0.3s, box-shadow 0.3s",
            ...(hover && {
              borderColor: exp.accent,
              boxShadow: `0 20px 60px -20px ${exp.accent}66, 0 0 80px -20px ${exp.accent}44`,
            }),
          }}
        >
          {/* 预览区 — 风格渐变背景 */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: exp.gradient,
              opacity: hover ? 1 : 0.75,
              transition: "opacity 0.4s",
              filter: hover ? "saturate(1.2)" : "saturate(0.85)",
            }}
          />

          {/* 暗化遮罩 */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background:
                "linear-gradient(180deg, transparent 0%, transparent 30%, rgba(0,0,0,0.85) 100%)",
            }}
          />

          {/* 内容 */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              padding: 24,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            {/* 顶部 — code + 箭头 */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
              }}
            >
              <span
                style={{
                  fontFamily: "ui-monospace, monospace",
                  fontSize: 10,
                  letterSpacing: 2,
                  color: "rgba(255,255,255,0.7)",
                  background: "rgba(0,0,0,0.4)",
                  padding: "4px 8px",
                  borderRadius: 4,
                  backdropFilter: "blur(8px)",
                }}
              >
                EXP/{exp.code}
              </span>
              <motion.div
                animate={{
                  x: hover ? 6 : 0,
                  y: hover ? -6 : 0,
                  opacity: hover ? 1 : 0.5,
                }}
              >
                <ArrowUpRight size={20} color="#fff" />
              </motion.div>
            </div>

            {/* 底部 — 标题 + 描述 */}
            <div>
              <div
                style={{
                  fontFamily: "ui-monospace, monospace",
                  fontSize: 10,
                  letterSpacing: 2,
                  color: exp.accent,
                  marginBottom: 8,
                  textTransform: "uppercase",
                }}
              >
                {exp.subtitle}
              </div>
              <h2
                style={{
                  fontSize: 26,
                  fontWeight: 700,
                  letterSpacing: "-0.02em",
                  marginBottom: 8,
                  lineHeight: 1.1,
                }}
              >
                {exp.title}
              </h2>
              <p
                style={{
                  fontSize: 13,
                  color: "rgba(255,255,255,0.65)",
                  lineHeight: 1.5,
                  marginBottom: 12,
                }}
              >
                {exp.desc}
              </p>
              <div
                style={{
                  fontFamily: "ui-monospace, monospace",
                  fontSize: 10,
                  letterSpacing: 1,
                  color: "rgba(255,255,255,0.4)",
                  textTransform: "uppercase",
                }}
              >
                {exp.tech}
              </div>
            </div>
          </div>
        </article>
      </Link>
    </motion.div>
  );
}

// 颗粒噪点背景 — SVG turbulence, 性能比 canvas 好, 比 PNG 灵活
function NoiseBackground() {
  return (
    <svg
      style={{
        position: "fixed",
        inset: 0,
        pointerEvents: "none",
        opacity: 0.4,
        zIndex: 0,
      }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <filter id="noise">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" />
        <feColorMatrix
          values="0 0 0 0 1
                  0 0 0 0 1
                  0 0 0 0 1
                  0 0 0 0.06 0"
        />
      </filter>
      <rect width="100%" height="100%" filter="url(#noise)" />
    </svg>
  );
}
