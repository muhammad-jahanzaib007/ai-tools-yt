import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
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
          {blob("a", "rgba(217,119,87,0.22)", 950, 20, 22, 70, 45, 0.5, p)}
          {blob("b", "rgba(42,161,152,0.20)", 1050, 82, 76, 80, 55, 0.4, p + 2)}
          {blob("c", "rgba(242,238,228,0.05)", 700, 55, 45, 55, 65, 0.3, p + 4)}
        </>
      )}
    </AbsoluteFill>
  );
};
