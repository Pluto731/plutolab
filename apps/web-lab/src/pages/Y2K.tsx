import { motion, useMotionValue, useTransform } from "framer-motion";
import { ArrowLeft, Cloud, Droplets, Leaf, Play, SkipBack, SkipForward, Volume2 } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "wouter";

export default function Y2KPage() {
  return (
    <main style={{
      minHeight: "100vh",
      background: "linear-gradient(170deg, #7ec8e3 0%, #4fa8d4 25%, #a8d8ea 50%, #c5e8f7 75%, #e8f4f8 100%)",
      position: "relative", overflow: "hidden", fontFamily: "'Segoe UI', Tahoma, sans-serif",
    }}>
      {/* 大气光效 */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        <div style={{ position: "absolute", top: "-30%", left: "-20%", width: "80vw", height: "80vw", borderRadius: "50%", background: "radial-gradient(circle, rgba(255,255,255,0.7) 0%, transparent 50%)", filter: "blur(40px)" }} />
        <div style={{ position: "absolute", bottom: "-40%", right: "-20%", width: "90vw", height: "90vw", borderRadius: "50%", background: "radial-gradient(circle, rgba(180,220,255,0.6) 0%, transparent 50%)", filter: "blur(60px)" }} />
      </div>

      {/* 浮动水滴 */}
      {[...Array(8)].map((_, i) => <WaterDrop key={i} index={i} />)}

      {/* 浮动叶子 */}
      {[...Array(5)].map((_, i) => <FloatingLeaf key={`leaf-${i}`} index={i} />)}

      {/* 顶部导航 */}
      <nav style={{ position: "relative", zIndex: 20, padding: "20px 32px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 18px", borderRadius: 100, ...glassStyle(), fontSize: 12, color: "#1a4a6e", fontWeight: 600 }}>
          <ArrowLeft size={14} /> EXP/003
        </Link>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <StatusPill icon={<Cloud size={12} />} text="Aero" />
          <StatusPill icon={<Droplets size={12} />} text="Glass" />
        </div>
      </nav>

      {/* 主内容区 */}
      <section style={{ position: "relative", zIndex: 10, padding: "4vh 32px 8vh", maxWidth: 1100, margin: "0 auto" }}>
        {/* 标题 */}
        <motion.div initial={{ opacity: 0, y: -30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
          <h1 style={{ fontSize: "clamp(48px, 8vw, 96px)", fontWeight: 300, color: "#0a3d5c", letterSpacing: "-0.03em", lineHeight: 1, marginBottom: 8, textShadow: "0 2px 0 rgba(255,255,255,0.8)" }}>
            Frutiger<span style={{ fontWeight: 700 }}>Aero</span>
          </h1>
          <p style={{ fontSize: 16, color: "#2a6a8e", maxWidth: 500, lineHeight: 1.7, marginBottom: 48 }}>
            那个相信科技与自然可以和谐共存的年代。透明、圆润、有机、充满希望。
          </p>
        </motion.div>

        {/* 组件展示网格 */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginBottom: 48 }}>
          <MediaPlayer />
          <GlassWidget title="System Info" icon={<Leaf size={16} />}>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {["Transparency", "Reflections", "Organic Curves"].map((item, i) => (
                <div key={item} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 0.8 + i * 0.1 }}
                    style={{ width: 8, height: 8, borderRadius: "50%", background: `hsl(${200 + i * 30}, 70%, 55%)` }}
                  />
                  <span style={{ fontSize: 14, color: "#1a4a6e" }}>{item}</span>
                  <div style={{ flex: 1, height: 4, borderRadius: 2, background: "rgba(0,0,0,0.06)", overflow: "hidden" }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${70 + i * 10}%` }}
                      transition={{ delay: 1 + i * 0.15, duration: 0.8 }}
                      style={{ height: "100%", borderRadius: 2, background: `linear-gradient(90deg, hsl(${200 + i * 30}, 70%, 55%), hsl(${220 + i * 30}, 80%, 65%))` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </GlassWidget>
        </div>

        {/* 底部卡片 */}
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.5 }} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 20 }}>
          {[
            { icon: "💎", label: "Crystal", desc: "通透如水晶", hue: 200 },
            { icon: "🌊", label: "Liquid", desc: "流动玻璃质感", hue: 220 },
            { icon: "✨", label: "Shine", desc: "金属反射高光", hue: 40 },
            { icon: "🍃", label: "Organic", desc: "有机曲线", hue: 140 },
          ].map((c, i) => (
            <GlassCard key={c.label} item={c} index={i} />
          ))}
        </motion.div>
      </section>
    </main>
  );
}

function glassStyle(): React.CSSProperties {
  return {
    background: "linear-gradient(180deg, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0.5) 50%, rgba(255,255,255,0.7) 100%)",
    backdropFilter: "blur(20px)",
    border: "1px solid rgba(255,255,255,0.95)",
    boxShadow: "inset 0 1px 0 rgba(255,255,255,1), inset 0 -1px 0 rgba(0,0,0,0.04), 0 8px 32px rgba(80,140,200,0.2)",
  };
}

function StatusPill({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 100, ...glassStyle(), fontSize: 11, color: "#1a4a6e", fontWeight: 600, letterSpacing: 1 }}>
      {icon} {text}
    </div>
  );
}

function WaterDrop({ index }: { index: number }) {
  const sizes = [40, 55, 70, 35, 60, 45, 80, 50];
  const positions = [
    { top: "10%", left: "15%" }, { top: "25%", left: "78%" },
    { top: "55%", left: "5%" }, { top: "70%", left: "65%" },
    { top: "40%", left: "88%" }, { top: "80%", left: "25%" },
    { top: "15%", left: "55%" }, { top: "60%", left: "42%" },
  ];
  const size = sizes[index % sizes.length];
  const pos = positions[index % positions.length];
  return (
    <motion.div
      animate={{ y: [0, -12, 0], scale: [1, 1.05, 1] }}
      transition={{ duration: 5 + index * 0.7, repeat: Infinity, ease: "easeInOut" }}
      style={{
        position: "absolute", ...pos, width: size, height: size, borderRadius: "50%", pointerEvents: "none", zIndex: 1,
        background: "radial-gradient(circle at 30% 25%, rgba(255,255,255,0.95), rgba(255,255,255,0.3) 50%, rgba(100,180,255,0.3))",
        boxShadow: "inset 0 -6px 12px rgba(0,0,0,0.08), inset 0 6px 12px rgba(255,255,255,0.9), 0 6px 20px rgba(100,160,220,0.3)",
      }}
    />
  );
}

function FloatingLeaf({ index }: { index: number }) {
  const positions = [
    { top: "20%", right: "10%" }, { top: "50%", right: "5%" },
    { top: "75%", left: "10%" }, { top: "35%", left: "3%" },
    { top: "85%", right: "20%" },
  ];
  const pos = positions[index % positions.length];
  return (
    <motion.div
      animate={{ y: [0, -20, 0], rotate: [0, 15, -10, 0], x: [0, 8, -5, 0] }}
      transition={{ duration: 8 + index * 2, repeat: Infinity, ease: "easeInOut" }}
      style={{ position: "absolute", ...pos, zIndex: 1, pointerEvents: "none", opacity: 0.7 }}
    >
      <Leaf size={20 + index * 4} color="#4a9e6e" strokeWidth={1.5} />
    </motion.div>
  );
}

function MediaPlayer() {
  const [playing, setPlaying] = useState(false);
  const progress = useMotionValue(0.35);
  const progressWidth = useTransform(progress, [0, 1], ["0%", "100%"]);
  const trackRef = useRef<HTMLDivElement>(null);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      style={{ padding: 24, borderRadius: 20, ...glassStyle() }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <div style={{ width: 48, height: 48, borderRadius: 12, background: "linear-gradient(135deg, #4fa8d4, #7ec8e3)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 4px 12px rgba(79,168,212,0.4)" }}>
          <Volume2 size={20} color="#fff" />
        </div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#0a3d5c" }}>Aqua Dreams</div>
          <div style={{ fontSize: 12, color: "#4a8aae" }}>Windows Media Player 11</div>
        </div>
      </div>
      <div ref={trackRef} style={{ height: 6, borderRadius: 3, background: "rgba(0,0,0,0.08)", marginBottom: 16, overflow: "hidden", cursor: "pointer" }}
        onClick={(e) => {
          if (!trackRef.current) return;
          const rect = trackRef.current.getBoundingClientRect();
          progress.set((e.clientX - rect.left) / rect.width);
        }}
      >
        <motion.div style={{ height: "100%", borderRadius: 3, background: "linear-gradient(90deg, #4fa8d4, #7ec8e3)", width: progressWidth }} />
      </div>
      <div style={{ display: "flex", justifyContent: "center", gap: 12 }}>
        {[SkipBack, playing ? Play : Play, SkipForward].map((Icon, i) => (
          <motion.button key={i} whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
            onClick={() => i === 1 && setPlaying(!playing)}
            style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: i === 1 ? "linear-gradient(180deg, #5ab8e8, #2d8cc4)" : "rgba(0,0,0,0.04)", border: i === 1 ? "none" : "1px solid rgba(0,0,0,0.06)", color: i === 1 ? "#fff" : "#1a4a6e", boxShadow: i === 1 ? "0 4px 12px rgba(45,140,196,0.4)" : "none" }}
          >
            <Icon size={14} />
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
}

function GlassWidget({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      style={{ padding: 24, borderRadius: 20, ...glassStyle() }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <div style={{ color: "#2a7a9e" }}>{icon}</div>
        <span style={{ fontSize: 14, fontWeight: 600, color: "#0a3d5c" }}>{title}</span>
      </div>
      {children}
    </motion.div>
  );
}

function GlassCard({ item, index }: { item: { icon: string; label: string; desc: string; hue: number }; index: number }) {
  return (
    <motion.div
      whileHover={{ y: -6, scale: 1.03 }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.6 + index * 0.1 }}
      style={{
        padding: "24px 20px", borderRadius: 20, cursor: "pointer",
        background: "linear-gradient(180deg, rgba(255,255,255,0.8) 0%, rgba(255,255,255,0.4) 50%, rgba(255,255,255,0.6) 100%)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(255,255,255,0.95)",
        boxShadow: `inset 0 1px 0 rgba(255,255,255,1), inset 0 -1px 0 rgba(0,0,0,0.04), 0 8px 32px hsla(${item.hue}, 60%, 60%, 0.2)`,
      }}
    >
      <div style={{ fontSize: 36, marginBottom: 10 }}>{item.icon}</div>
      <div style={{ fontSize: 16, fontWeight: 600, color: "#0a3d5c", marginBottom: 4 }}>{item.label}</div>
      <div style={{ fontSize: 13, color: "rgba(10,61,92,0.6)" }}>{item.desc}</div>
    </motion.div>
  );
}
