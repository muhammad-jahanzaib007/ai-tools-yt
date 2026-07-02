import React from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS } from "./types";
import { fontFamily } from "./font";
import { glass } from "./fx";

const pop = Easing.bezier(0.34, 1.56, 0.64, 1);

export const Scoreboard: React.FC<{
  toolA: string;
  toolB: string;
  scoreA: number;
  scoreB: number;
  popAt?: number;
}> = ({ toolA, toolB, scoreA, scoreB, popAt }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const vertical = height > width;
  // the score flips at popAt: bump the digits so the update reads as an event
  const bump =
    popAt === undefined
      ? 1
      : interpolate(frame, [popAt, popAt + 0.25 * fps, popAt + 0.5 * fps], [1, 1.45, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: pop,
        });

  const chip = (tint: string): React.CSSProperties => ({
    ...glass(tint, 24),
    position: "relative",
    overflow: "hidden",
    display: "flex",
    alignItems: "center",
    gap: 18,
    fontFamily,
    fontWeight: 700,
    fontSize: vertical ? 40 : 44,
    color: COLORS.cream,
    padding: "16px 32px",
    borderRadius: 999,
  });
  const glossline: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    background: "linear-gradient(180deg, rgba(255,255,255,0.22) 0%, transparent 45%)",
    borderRadius: 999,
    pointerEvents: "none",
  };
  const score: React.CSSProperties = {
    fontWeight: 900,
    fontSize: vertical ? 48 : 52,
    scale: String(bump),
    textShadow: "0 2px 12px rgba(0,0,0,0.4)",
  };

  return (
    <div
      style={{
        position: "absolute",
        top: vertical ? 60 : 40,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        gap: 30,
      }}
    >
      <div style={chip("rgba(217,119,87,0.55)")}>
        <div style={glossline} />
        <span>{toolA}</span>
        <span style={score}>{scoreA}</span>
      </div>
      <div style={chip("rgba(42,161,152,0.55)")}>
        <div style={glossline} />
        <span style={score}>{scoreB}</span>
        <span>{toolB}</span>
      </div>
    </div>
  );
};
