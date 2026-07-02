import React from "react";
import { AbsoluteFill, random, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS } from "./types";

// Slowly drifting radial-gradient blobs so scenes never sit on a flat colour.
// Gradient circles instead of CSS blur: same soft look, far cheaper to render.
export const AnimatedBg: React.FC<{
  light?: boolean;
  variant?: number;
}> = ({ light = false, variant = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const blob = (
    key: string,
    color: string,
    size: number,
    cx: number,
    cy: number,
    driftX: number,
    driftY: number,
    speed: number,
    phase: number,
  ) => (
    <div
      key={key}
      style={{
        position: "absolute",
        width: size,
        height: size,
        borderRadius: "50%",
        background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
        left: `calc(${cx}% + ${Math.sin(t * speed + phase) * driftX}px)`,
        top: `calc(${cy}% + ${Math.cos(t * speed * 0.8 + phase) * driftY}px)`,
        transform: "translate(-50%, -50%)",
      }}
    />
  );

  const p = variant * 1.7;
  return (
    <AbsoluteFill
      style={{
        backgroundColor: light ? COLORS.cream : COLORS.bg,
        overflow: "hidden",
      }}
    >
      {light ? (
        <>
          {blob("a", "rgba(217,119,87,0.14)", 1100, 25, 20, 70, 50, 0.45, p)}
          {blob("b", "rgba(42,161,152,0.10)", 1000, 80, 80, 80, 60, 0.35, p + 2)}
        </>
      ) : (
        <>
          {blob("a", "rgba(217,119,87,0.32)", 950, 20, 22, 70, 45, 0.5, p)}
          {blob("b", "rgba(42,161,152,0.30)", 1050, 82, 76, 80, 55, 0.4, p + 2)}
          {blob("c", "rgba(242,238,228,0.07)", 700, 55, 45, 55, 65, 0.3, p + 4)}
          {/* slow rotating sheen so the darks feel glossy, not dead */}
          <AbsoluteFill
            style={{
              background: `conic-gradient(from ${(t * 9) % 360}deg at 72% 28%, transparent 0deg, rgba(255,255,255,0.045) 40deg, transparent 90deg, transparent 250deg, rgba(255,255,255,0.03) 300deg, transparent 360deg)`,
            }}
          />
          <Particles variant={variant} />
        </>
      )}
    </AbsoluteFill>
  );
};

// Small embers drifting upward: cheap depth cue on the dark scenes.
const Particles: React.FC<{ variant: number }> = ({ variant }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const tints = ["rgba(217,119,87,0.5)", "rgba(42,161,152,0.45)", "rgba(242,238,228,0.4)"];
  return (
    <AbsoluteFill style={{ overflow: "hidden", pointerEvents: "none" }}>
      {Array.from({ length: 14 }).map((_, i) => {
        const seed = `p${variant}-${i}`;
        const x = random(`${seed}x`) * 100;
        const size = 4 + random(`${seed}s`) * 8;
        const speed = 0.6 + random(`${seed}v`) * 1.2;
        const y = ((random(`${seed}y`) * height + height - frame * speed) % (height * 1.1)) - height * 0.05;
        const sway = Math.sin(frame / 40 + i * 2.1) * width * 0.015;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `calc(${x}% + ${sway}px)`,
              top: y,
              width: size,
              height: size,
              borderRadius: "50%",
              backgroundColor: tints[i % 3],
              opacity: 0.25 + random(`${seed}o`) * 0.35,
              filter: "blur(1px)",
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
