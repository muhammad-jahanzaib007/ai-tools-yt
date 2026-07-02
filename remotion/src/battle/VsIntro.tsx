import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS } from "./types";
import { fontFamily } from "./font";

const ease = Easing.bezier(0.16, 1, 0.3, 1);

export const VsIntro: React.FC<{
  toolA: string;
  toolB: string;
  tagline: string;
}> = ({ toolA, toolB, tagline }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const vertical = height > width;

  const slideA = interpolate(frame, [0, 0.6 * fps], [-100, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const slideB = interpolate(frame, [0.15 * fps, 0.75 * fps], [100, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const vsScale = interpolate(frame, [0.8 * fps, 1.2 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.34, 1.56, 0.64, 1), // overshoot pop
  });
  const tagOpacity = interpolate(frame, [1.4 * fps, 1.9 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

  const nameSize = vertical ? 84 : 96;
  const panel: React.CSSProperties = {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily,
    fontWeight: 900,
    fontSize: nameSize,
    color: COLORS.white,
    textAlign: "center",
    padding: 40,
  };

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <AbsoluteFill
        style={{ display: "flex", flexDirection: vertical ? "column" : "row" }}
      >
        <div
          style={{
            ...panel,
            backgroundColor: COLORS.coral,
            translate: vertical ? `0px ${slideA}%` : `${slideA}% 0px`,
          }}
        >
          {toolA}
        </div>
        <div
          style={{
            ...panel,
            backgroundColor: COLORS.teal,
            translate: vertical ? `0px ${slideB}%` : `${slideB}% 0px`,
          }}
        >
          {toolB}
        </div>
      </AbsoluteFill>
      <AbsoluteFill
        style={{ alignItems: "center", justifyContent: "center" }}
      >
        <div
          style={{
            scale: String(vsScale),
            backgroundColor: COLORS.dark,
            color: COLORS.cream,
            fontFamily,
            fontWeight: 900,
            fontSize: vertical ? 120 : 140,
            borderRadius: "50%",
            width: vertical ? 260 : 300,
            height: vertical ? 260 : 300,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 0 80px rgba(0,0,0,0.6)",
          }}
        >
          VS
        </div>
      </AbsoluteFill>
      <AbsoluteFill
        style={{ alignItems: "center", justifyContent: "flex-end" }}
      >
        <div
          style={{
            opacity: tagOpacity,
            fontFamily,
            fontWeight: 700,
            fontSize: vertical ? 52 : 56,
            color: COLORS.cream,
            backgroundColor: "rgba(26,25,21,0.85)",
            padding: "24px 48px",
            borderRadius: 20,
            marginBottom: vertical ? 220 : 90,
            maxWidth: "85%",
            textAlign: "center",
          }}
        >
          {tagline}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
