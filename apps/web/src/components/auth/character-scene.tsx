"use client";

import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { EyeBall, Pupil } from "@/components/auth/eyes";

interface CharacterSceneProps {
  /** Email field focused — characters glance at each other. */
  typing?: boolean;
  /** Password field focused — characters look away (and sneak the odd peek). */
  hidingEyes?: boolean;
}

type FacePos = { faceX: number; faceY: number; bodySkew: number };

const ENTRANCE = {
  initial: { y: 90, opacity: 0, scale: 0.85 },
  animate: { y: 0, opacity: 1, scale: 1 },
} as const;

const spring = (delay: number) => ({
  type: "spring" as const,
  stiffness: 200,
  damping: 18,
  delay,
});

export function CharacterScene({ typing = false, hidingEyes = false }: CharacterSceneProps) {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const [purpleBlink, setPurpleBlink] = useState(false);
  const [blackBlink, setBlackBlink] = useState(false);
  const [glancing, setGlancing] = useState(false);
  const [peeking, setPeeking] = useState(false);

  const purpleRef = useRef<HTMLDivElement>(null);
  const blackRef = useRef<HTMLDivElement>(null);
  const yellowRef = useRef<HTMLDivElement>(null);
  const orangeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      setMouseX(e.clientX);
      setMouseY(e.clientY);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  // Two independent random blink loops.
  useEffect(() => makeBlinkLoop(setPurpleBlink), []);
  useEffect(() => makeBlinkLoop(setBlackBlink), []);

  // Glance at each other briefly when the user starts typing the email.
  useEffect(() => {
    if (!typing) {
      setGlancing(false);
      return;
    }
    setGlancing(true);
    const t = setTimeout(() => setGlancing(false), 800);
    return () => clearTimeout(t);
  }, [typing]);

  // Occasional sneaky peek while hiding eyes during password entry.
  useEffect(() => {
    if (!hidingEyes) {
      setPeeking(false);
      return;
    }
    let alive = true;
    let inner: ReturnType<typeof setTimeout>;
    const schedule = () => {
      const t = setTimeout(
        () => {
          if (!alive) return;
          setPeeking(true);
          inner = setTimeout(() => {
            setPeeking(false);
            schedule();
          }, 700);
        },
        Math.random() * 3000 + 2000,
      );
      return t;
    };
    const first = schedule();
    return () => {
      alive = false;
      clearTimeout(first);
      clearTimeout(inner);
    };
  }, [hidingEyes]);

  const pos = (ref: React.RefObject<HTMLDivElement | null>): FacePos => {
    if (!ref.current) return { faceX: 0, faceY: 0, bodySkew: 0 };
    const rect = ref.current.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 3;
    const dx = mouseX - cx;
    const dy = mouseY - cy;
    return {
      faceX: clamp(dx / 20, -15, 15),
      faceY: clamp(dy / 30, -10, 10),
      bodySkew: clamp(-dx / 120, -6, 6),
    };
  };

  const purple = pos(purpleRef);
  const black = pos(blackRef);
  const orange = pos(orangeRef);
  const yellow = pos(yellowRef);

  return (
    <div className="relative" style={{ width: 550, height: 400 }}>
      {/* Purple — tall, back layer */}
      <motion.div
        className="absolute bottom-0"
        style={{ left: 70, zIndex: 1 }}
        initial={ENTRANCE.initial}
        animate={ENTRANCE.animate}
        transition={spring(0)}
      >
        <div
          ref={purpleRef}
          className="relative transition-all duration-700 ease-in-out"
          style={{
            width: 180,
            height: typing && !hidingEyes ? 440 : 400,
            backgroundColor: "#6C3FF5",
            borderRadius: "10px 10px 0 0",
            transform: hidingEyes
              ? "skewX(0deg)"
              : glancing
                ? `skewX(${purple.bodySkew - 10}deg) translateX(20px)`
                : `skewX(${purple.bodySkew}deg)`,
            transformOrigin: "bottom center",
          }}
        >
          <div
            className="absolute flex gap-8 transition-all duration-700 ease-in-out"
            style={{
              left: hidingEyes ? 20 : glancing ? 55 : 45 + purple.faceX,
              top: hidingEyes ? 35 : glancing ? 65 : 40 + purple.faceY,
            }}
          >
            {[0, 1].map((i) => (
              <EyeBall
                key={i}
                mouseX={mouseX}
                mouseY={mouseY}
                size={18}
                pupilSize={7}
                isBlinking={purpleBlink}
                forceLookX={hidingEyes ? (peeking ? 4 : -4) : glancing ? 3 : undefined}
                forceLookY={hidingEyes ? (peeking ? 5 : -4) : glancing ? 4 : undefined}
              />
            ))}
          </div>
        </div>
      </motion.div>

      {/* Black — middle layer */}
      <motion.div
        className="absolute bottom-0"
        style={{ left: 240, zIndex: 2 }}
        initial={ENTRANCE.initial}
        animate={ENTRANCE.animate}
        transition={spring(0.1)}
      >
        <div
          ref={blackRef}
          className="relative transition-all duration-700 ease-in-out"
          style={{
            width: 120,
            height: 310,
            backgroundColor: "#2D2D2D",
            borderRadius: "8px 8px 0 0",
            transform: hidingEyes
              ? "skewX(0deg)"
              : glancing
                ? `skewX(${black.bodySkew * 1.5 + 10}deg) translateX(20px)`
                : `skewX(${black.bodySkew}deg)`,
            transformOrigin: "bottom center",
          }}
        >
          <div
            className="absolute flex gap-6 transition-all duration-700 ease-in-out"
            style={{
              left: hidingEyes ? 10 : glancing ? 32 : 26 + black.faceX,
              top: hidingEyes ? 28 : glancing ? 12 : 32 + black.faceY,
            }}
          >
            {[0, 1].map((i) => (
              <EyeBall
                key={i}
                mouseX={mouseX}
                mouseY={mouseY}
                size={16}
                pupilSize={6}
                maxDistance={4}
                isBlinking={blackBlink}
                forceLookX={hidingEyes ? -4 : glancing ? 0 : undefined}
                forceLookY={hidingEyes ? -4 : glancing ? -4 : undefined}
              />
            ))}
          </div>
        </div>
      </motion.div>

      {/* Orange — front-left semicircle */}
      <motion.div
        className="absolute bottom-0"
        style={{ left: 0, zIndex: 3 }}
        initial={ENTRANCE.initial}
        animate={ENTRANCE.animate}
        transition={spring(0.2)}
      >
        <div
          ref={orangeRef}
          className="relative transition-all duration-700 ease-in-out"
          style={{
            width: 240,
            height: 200,
            backgroundColor: "#FF9B6B",
            borderRadius: "120px 120px 0 0",
            transform: hidingEyes ? "skewX(0deg)" : `skewX(${orange.bodySkew}deg)`,
            transformOrigin: "bottom center",
          }}
        >
          <div
            className="absolute flex gap-8 transition-all duration-200 ease-out"
            style={{
              left: hidingEyes ? 50 : 82 + orange.faceX,
              top: hidingEyes ? 85 : 90 + orange.faceY,
            }}
          >
            {[0, 1].map((i) => (
              <Pupil
                key={i}
                mouseX={mouseX}
                mouseY={mouseY}
                size={12}
                pupilColor="#2D2D2D"
                forceLookX={hidingEyes ? -5 : undefined}
                forceLookY={hidingEyes ? -4 : undefined}
              />
            ))}
          </div>
        </div>
      </motion.div>

      {/* Yellow — front-right, with a mouth */}
      <motion.div
        className="absolute bottom-0"
        style={{ left: 310, zIndex: 4 }}
        initial={ENTRANCE.initial}
        animate={ENTRANCE.animate}
        transition={spring(0.3)}
      >
        <div
          ref={yellowRef}
          className="relative transition-all duration-700 ease-in-out"
          style={{
            width: 140,
            height: 230,
            backgroundColor: "#E8D754",
            borderRadius: "70px 70px 0 0",
            transform: hidingEyes ? "skewX(0deg)" : `skewX(${yellow.bodySkew}deg)`,
            transformOrigin: "bottom center",
          }}
        >
          <div
            className="absolute flex gap-6 transition-all duration-200 ease-out"
            style={{
              left: hidingEyes ? 20 : 52 + yellow.faceX,
              top: hidingEyes ? 35 : 40 + yellow.faceY,
            }}
          >
            {[0, 1].map((i) => (
              <Pupil
                key={i}
                mouseX={mouseX}
                mouseY={mouseY}
                size={12}
                pupilColor="#2D2D2D"
                forceLookX={hidingEyes ? -5 : undefined}
                forceLookY={hidingEyes ? -4 : undefined}
              />
            ))}
          </div>
          <div
            className="absolute h-[4px] w-20 rounded-full bg-[#2D2D2D] transition-all duration-200 ease-out"
            style={{
              left: hidingEyes ? 10 : 40 + yellow.faceX,
              top: hidingEyes ? 88 : 88 + yellow.faceY,
            }}
          />
        </div>
      </motion.div>
    </div>
  );
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

function makeBlinkLoop(setBlink: (v: boolean) => void): () => void {
  let alive = true;
  let open: ReturnType<typeof setTimeout>;
  let close: ReturnType<typeof setTimeout>;
  const schedule = () => {
    open = setTimeout(
      () => {
        if (!alive) return;
        setBlink(true);
        close = setTimeout(() => {
          setBlink(false);
          schedule();
        }, 150);
      },
      Math.random() * 4000 + 3000,
    );
  };
  schedule();
  return () => {
    alive = false;
    clearTimeout(open);
    clearTimeout(close);
  };
}
