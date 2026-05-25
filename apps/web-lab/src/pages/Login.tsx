import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Eye, EyeOff, Github, Lock, Mail } from "lucide-react";
import { useState } from "react";
import { Link } from "wouter";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [focusField, setFocusField] = useState<"email" | "password" | null>(null);
  const [shake, setShake] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.includes("@") || password.length < 6) {
      setShake(true);
      setTimeout(() => setShake(false), 600);
      return;
    }
    setSuccess(true);
    setTimeout(() => setSuccess(false), 3000);
  };

  const isHidingEyes = focusField === "password" && !showPassword;

  return (
    <main style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      padding: 24, position: "relative", overflow: "hidden",
      background: "radial-gradient(ellipse at 50% 0%, #1a0533 0%, #0d0015 50%, #000 100%)",
    }}>
      {/* 星空背景 */}
      <StarField />
      {/* 极光效果 */}
      <Aurora />

      {/* 返回按钮 */}
      <Link href="/" style={{
        position: "absolute", top: 24, left: 24, zIndex: 20,
        display: "inline-flex", alignItems: "center", gap: 8, padding: "8px 14px",
        borderRadius: 100, background: "rgba(255,255,255,0.05)", backdropFilter: "blur(20px)",
        border: "1px solid rgba(255,255,255,0.1)", fontFamily: "ui-monospace, monospace",
        fontSize: 12, color: "rgba(255,255,255,0.7)",
      }}>
        <ArrowLeft size={14} /> EXP/004
      </Link>

      {/* 主面板 */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 30 }}
        animate={{ opacity: 1, scale: 1, y: 0, x: shake ? [0, -12, 12, -8, 8, -4, 4, 0] : 0 }}
        transition={{ duration: 0.6, type: "spring", stiffness: 100 }}
        style={{
          width: "100%", maxWidth: 400, padding: "48px 36px 36px", borderRadius: 32,
          background: "rgba(255,255,255,0.03)", backdropFilter: "blur(40px)",
          border: "1px solid rgba(255,255,255,0.08)",
          boxShadow: "0 40px 80px -20px rgba(0,0,0,0.8), inset 0 1px 0 rgba(255,255,255,0.1)",
          position: "relative", zIndex: 10,
        }}
      >
        {/* 角色 */}
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 24 }}>
          <CharacterPluto
            looking={focusField === "email" ? "left" : focusField === "password" && showPassword ? "right" : "center"}
            hidingEyes={isHidingEyes}
            shake={shake}
            success={success}
          />
        </div>

        <AnimatePresence mode="wait">
          {success ? (
            <motion.div key="success" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} style={{ textAlign: "center", padding: "20px 0" }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>🎉</div>
              <div style={{ fontSize: 20, fontWeight: 600, color: "#fff" }}>欢迎回来!</div>
              <div style={{ fontSize: 14, color: "rgba(255,255,255,0.5)", marginTop: 8 }}>正在跳转到工作台...</div>
            </motion.div>
          ) : (
            <motion.div key="form" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <h1 style={{ fontSize: 24, fontWeight: 600, color: "#fff", textAlign: "center", marginBottom: 6, letterSpacing: "-0.02em" }}>
                欢迎回来
              </h1>
              <p style={{ fontSize: 14, color: "rgba(255,255,255,0.45)", textAlign: "center", marginBottom: 28 }}>
                登录你的 PlutoLab 工作台
              </p>

              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <Field icon={<Mail size={16} />} type="email" placeholder="邮箱地址" value={email} onChange={setEmail} onFocus={() => setFocusField("email")} onBlur={() => setFocusField(null)} />
                <Field icon={<Lock size={16} />} type={showPassword ? "text" : "password"} placeholder="密码" value={password} onChange={setPassword} onFocus={() => setFocusField("password")} onBlur={() => setFocusField(null)}
                  right={<button type="button" onClick={() => setShowPassword(v => !v)} style={{ color: "rgba(255,255,255,0.4)", display: "flex", alignItems: "center" }}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button>}
                />
                <motion.button type="submit" whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} style={{ marginTop: 6, padding: "14px 0", borderRadius: 14, background: "linear-gradient(135deg, #7c3aed 0%, #ec4899 100%)", color: "#fff", fontSize: 15, fontWeight: 600, boxShadow: "0 8px 24px -4px rgba(124,58,237,0.5)", letterSpacing: 0.3 }}>
                  登录
                </motion.button>
                <Divider />
                <motion.button type="button" whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} style={{ padding: "12px 0", borderRadius: 14, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.8)", fontSize: 14, fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                  <Github size={16} /> 用 GitHub 登录
                </motion.button>
              </form>
              <p style={{ marginTop: 20, textAlign: "center", fontSize: 13, color: "rgba(255,255,255,0.4)" }}>
                还没账号? <a style={{ color: "#a78bfa", cursor: "pointer" }}>立即注册 →</a>
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </main>
  );
}

function Divider() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "4px 0", fontSize: 12, color: "rgba(255,255,255,0.25)" }}>
      <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.08)" }} />
      <span>或</span>
      <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.08)" }} />
    </div>
  );
}

function Field({ icon, type, placeholder, value, onChange, onFocus, onBlur, right }: {
  icon: React.ReactNode; type: string; placeholder: string; value: string;
  onChange: (v: string) => void; onFocus: () => void; onBlur: () => void; right?: React.ReactNode;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", borderRadius: 14,
      background: "rgba(255,255,255,0.04)", border: `1px solid ${focused ? "rgba(124,58,237,0.5)" : "rgba(255,255,255,0.08)"}`,
      transition: "border-color 0.2s, box-shadow 0.2s",
      boxShadow: focused ? "0 0 0 3px rgba(124,58,237,0.1)" : "none",
    }}>
      <span style={{ color: "rgba(255,255,255,0.35)" }}>{icon}</span>
      <input type={type} placeholder={placeholder} value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => { setFocused(true); onFocus(); }}
        onBlur={() => { setFocused(false); onBlur(); }}
        style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "#fff", fontSize: 14 }}
      />
      {right}
    </div>
  );
}

function StarField() {
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
      {[...Array(60)].map((_, i) => (
        <div key={i} style={{
          position: "absolute", width: Math.random() > 0.8 ? 2 : 1, height: Math.random() > 0.8 ? 2 : 1,
          background: "#fff", borderRadius: "50%",
          top: `${Math.random() * 100}%`, left: `${Math.random() * 100}%`,
          opacity: Math.random() * 0.5 + 0.1,
          animation: `twinkle ${2 + Math.random() * 4}s ease-in-out infinite`,
          animationDelay: `${Math.random() * 3}s`,
        }} />
      ))}
      <style>{`@keyframes twinkle { 0%,100% { opacity: 0.1; } 50% { opacity: 0.8; } }`}</style>
    </div>
  );
}

function Aurora() {
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none", opacity: 0.6 }}>
      <motion.div
        animate={{ x: ["-20%", "20%", "-20%"], y: ["-10%", "10%", "-10%"] }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
        style={{ position: "absolute", top: "-30%", left: "-20%", width: "80vw", height: "60vh", borderRadius: "50%", background: "radial-gradient(ellipse, rgba(124,58,237,0.3) 0%, transparent 60%)", filter: "blur(60px)" }}
      />
      <motion.div
        animate={{ x: ["20%", "-20%", "20%"], y: ["10%", "-10%", "10%"] }}
        transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
        style={{ position: "absolute", bottom: "-20%", right: "-20%", width: "70vw", height: "50vh", borderRadius: "50%", background: "radial-gradient(ellipse, rgba(236,72,153,0.25) 0%, transparent 60%)", filter: "blur(60px)" }}
      />
    </div>
  );
}

function CharacterPluto({ looking, hidingEyes, shake, success }: {
  looking: "left" | "right" | "center"; hidingEyes: boolean; shake: boolean; success: boolean;
}) {
  const eyeX = looking === "left" ? -4 : looking === "right" ? 4 : 0;
  const eyeY = looking === "center" ? 0 : -1;

  return (
    <motion.div
      animate={shake ? { rotate: [0, -10, 10, -8, 8, -4, 4, 0] } : { rotate: 0 }}
      transition={{ duration: 0.5 }}
      style={{ width: 130, height: 130 }}
    >
      <svg width="130" height="130" viewBox="0 0 130 130">
        <defs>
          <radialGradient id="bodyG" cx="35%" cy="30%">
            <stop offset="0%" stopColor="#f5dcc8" />
            <stop offset="50%" stopColor="#d4a886" />
            <stop offset="100%" stopColor="#9e6b4a" />
          </radialGradient>
          <radialGradient id="cheekG">
            <stop offset="0%" stopColor="#ff8aa8" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#ff8aa8" stopOpacity="0" />
          </radialGradient>
          <filter id="glow"><feGaussianBlur stdDeviation="2" result="g" /><feMerge><feMergeNode in="g" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <ellipse cx="65" cy="118" rx="28" ry="4" fill="rgba(124,58,237,0.3)" />
        <circle cx="65" cy="62" r="50" fill="url(#bodyG)" />
        <ellipse cx="50" cy="74" rx="12" ry="8" fill="#f5dcc8" opacity="0.5" />
        <circle cx="44" cy="68" r="10" fill="url(#cheekG)" />
        <circle cx="86" cy="68" r="10" fill="url(#cheekG)" />

        <AnimatePresence mode="wait">
          {hidingEyes ? (
            <motion.g key="h" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: 0.2 }}>
              <ellipse cx="48" cy="55" rx="10" ry="7" fill="#9e6b4a" />
              <ellipse cx="82" cy="55" rx="10" ry="7" fill="#9e6b4a" />
              <ellipse cx="48" cy="53" rx="8" ry="5" fill="#d4a886" />
              <ellipse cx="82" cy="53" rx="8" ry="5" fill="#d4a886" />
            </motion.g>
          ) : (
            <motion.g key="e" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <circle cx="48" cy="55" r="8" fill="#fff" />
              <motion.circle cx={48 + eyeX} cy={55 + eyeY} r="4" fill="#1a1a1a" animate={{ cx: 48 + eyeX, cy: 55 + eyeY }} transition={{ duration: 0.2 }} />
              <circle cx={48 + eyeX + 1.5} cy={55 + eyeY - 1.5} r="1.5" fill="#fff" />
              <circle cx="82" cy="55" r="8" fill="#fff" />
              <motion.circle cx={82 + eyeX} cy={55 + eyeY} r="4" fill="#1a1a1a" animate={{ cx: 82 + eyeX, cy: 55 + eyeY }} transition={{ duration: 0.2 }} />
              <circle cx={82 + eyeX + 1.5} cy={55 + eyeY - 1.5} r="1.5" fill="#fff" />
            </motion.g>
          )}
        </AnimatePresence>

        <motion.path
          d={success ? "M 52 82 Q 65 94 78 82" : shake ? "M 52 82 Q 65 76 78 82" : "M 54 80 Q 65 88 76 80"}
          stroke="#5d2f1a" strokeWidth="2.5" strokeLinecap="round" fill="none"
          animate={{ d: success ? "M 52 82 Q 65 94 78 82" : shake ? "M 52 82 Q 65 76 78 82" : "M 54 80 Q 65 88 76 80" }}
          transition={{ duration: 0.3 }}
        />
        {success && <circle cx="65" cy="30" r="8" fill="none" stroke="#ffd700" strokeWidth="2" filter="url(#glow)" opacity="0.8" />}
      </svg>
    </motion.div>
  );
}
