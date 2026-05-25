"use client";

import { useRef } from "react";

function offsetToward(
  ref: React.RefObject<HTMLDivElement | null>,
  mouseX: number,
  mouseY: number,
  maxDistance: number,
): { x: number; y: number } {
  if (!ref.current) return { x: 0, y: 0 };
  const rect = ref.current.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const dx = mouseX - cx;
  const dy = mouseY - cy;
  const distance = Math.min(Math.hypot(dx, dy), maxDistance);
  const angle = Math.atan2(dy, dx);
  return { x: Math.cos(angle) * distance, y: Math.sin(angle) * distance };
}

interface PupilProps {
  mouseX: number;
  mouseY: number;
  size?: number;
  maxDistance?: number;
  pupilColor?: string;
  forceLookX?: number;
  forceLookY?: number;
}

/** A bare pupil (no white) that drifts toward the cursor. */
export function Pupil({
  mouseX,
  mouseY,
  size = 12,
  maxDistance = 5,
  pupilColor = "black",
  forceLookX,
  forceLookY,
}: PupilProps) {
  const ref = useRef<HTMLDivElement>(null);
  const pos =
    forceLookX !== undefined && forceLookY !== undefined
      ? { x: forceLookX, y: forceLookY }
      : offsetToward(ref, mouseX, mouseY, maxDistance);

  return (
    <div
      ref={ref}
      className="rounded-full"
      style={{
        width: size,
        height: size,
        backgroundColor: pupilColor,
        transform: `translate(${pos.x}px, ${pos.y}px)`,
        transition: "transform 0.1s ease-out",
      }}
    />
  );
}

interface EyeBallProps {
  mouseX: number;
  mouseY: number;
  size?: number;
  pupilSize?: number;
  maxDistance?: number;
  eyeColor?: string;
  pupilColor?: string;
  isBlinking?: boolean;
  forceLookX?: number;
  forceLookY?: number;
}

/** A white eyeball with a pupil that tracks the cursor; collapses to a line when blinking. */
export function EyeBall({
  mouseX,
  mouseY,
  size = 18,
  pupilSize = 7,
  maxDistance = 5,
  eyeColor = "white",
  pupilColor = "#2D2D2D",
  isBlinking = false,
  forceLookX,
  forceLookY,
}: EyeBallProps) {
  const ref = useRef<HTMLDivElement>(null);
  const pos =
    forceLookX !== undefined && forceLookY !== undefined
      ? { x: forceLookX, y: forceLookY }
      : offsetToward(ref, mouseX, mouseY, maxDistance);

  return (
    <div
      ref={ref}
      className="flex items-center justify-center overflow-hidden rounded-full transition-all duration-150"
      style={{
        width: size,
        height: isBlinking ? 2 : size,
        backgroundColor: eyeColor,
      }}
    >
      {!isBlinking && (
        <div
          className="rounded-full"
          style={{
            width: pupilSize,
            height: pupilSize,
            backgroundColor: pupilColor,
            transform: `translate(${pos.x}px, ${pos.y}px)`,
            transition: "transform 0.1s ease-out",
          }}
        />
      )}
    </div>
  );
}
