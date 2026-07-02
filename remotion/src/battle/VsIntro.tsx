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
import { Grain, ShineSweep, SparkBurst, Vignette } from "./fx";

const ease = Easing.bezier(0.16, 1, 0.3, 1);
const pop = Easing.bezier(0.34, 1.56, 0.64, 1);

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
  const vsAt = 0.8 * fps;
  const vsScale = interpolate(frame, [vsAt, 1.2 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  // impact shake when the VS badge slams in
  const shakeAmp = interpolate(frame, [vsAt, vsAt + 0.35 * fps], [14, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const shakeX = Math.sin(frame * 2.7) * shakeAmp;
  const shakeY = Math.cos(frame * 3.3) * shakeAmp * 0.6;
  const glowPulse = 0.5 + 0.5 * Math.sin(frame / 5);
  const tagOpacity = interpolate(frame, [1.4 * fps, 1.9 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const tagRise = interpolate(frame, [1.4 * fps, 1.9 * fps], [40, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

  const nameSize = vertical ? 88 : 100;
  const panel: React.CSSProperties = {
    flex: 1,
    position: "relative",
    overflow: "hidden",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily,
    fontWeight: 900,
    fontSize: nameSize,
    color: COLORS.white,
    textAlign: "center",
    padding: 40,
    letterSpacing: "-0.02em",
  };
  const gloss: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    background:
      "radial-gradient(120% 90% at 20% 0%, rgba(255,255,255,0.22) 0%, transparent 55%)",
    pointerEvents: "none",
  };
  const nameStyle: React.CSSProperties = {
    position: "relative",
    textShadow: "0 6px 30px rgba(0,0,0,0.35)",
  };

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: vertical ? "column" : "row",
          translate: `${shakeX}px ${shakeY}px`,
        }}
      >
        <div
          style={{
            ...panel,
            background: "linear-gradient(135deg, #E8926B 0%, #D97757 45%, #B85A38 100%)",
            translate: vertical ? `0px ${slideA}%` : `${slideA}% 0px`,
          }}
        >
          <div style={gloss} />
          <ShineSweep at={0.7 * fps} duration={0.6 * fps} />
          <span style={nameStyle}>{toolA}</span>
        </div>
        <div
          style={{
            ...panel,
            background: "linear-gradient(315deg, #35B5AA 0%, #2AA198 45%, #1E7C74 100%)",
            translate: vertical ? `0px ${slideB}%` : `${slideB}% 0px`,
          }}
        >
          <div style={gloss} />
          <ShineSweep at={0.85 * fps} duration={0.6 * fps} />
          <span style={nameStyle}>{toolB}</span>
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <SparkBurst at={vsAt + 3} color={COLORS.cream} size={vertical ? 420 : 360} count={12} seed="vs" />
        <div
          style={{
            scale: String(vsScale),
            position: "relative",
            width: vertical ? 270 : 310,
            height: vertical ? 270 : 310,
            borderRadius: "50%",
            padding: 8,
            background: `conic-gradient(from ${frame * 4}deg, ${COLORS.coral}, ${COLORS.cream}, ${COLORS.teal}, ${COLORS.coral})`,
            boxShadow: `0 0 ${60 + glowPulse * 50}px rgba(242,238,228,0.35), 0 30px 80px rgba(0,0,0,0.55)`,
          }}
        >
          <div
            style={{
              width: "100%",
              height: "100%",
              borderRadius: "50%",
              background: "radial-gradient(120% 120% at 30% 20%, #2B2A24 0%, #1A1915 60%)",
              color: COLORS.cream,
              fontFamily,
              fontWeight: 900,
              fontSize: vertical ? 118 : 138,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              textShadow: "0 4px 24px rgba(0,0,0,0.6)",
            }}
          >
            VS
          </div>
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-end" }}>
        <div
          style={{
            opacity: tagOpacity,
            translate: `0px ${tagRise}px`,
            fontFamily,
            fontWeight: 700,
            fontSize: vertical ? 52 : 56,
            color: COLORS.cream,
            backgroundColor: "rgba(26,25,21,0.62)",
            backdropFilter: "blur(18px)",
            border: "1.5px solid rgba(255,255,255,0.18)",
            boxShadow: "0 24px 60px rgba(0,0,0,0.45)",
            padding: "26px 52px",
            borderRadius: 24,
            marginBottom: vertical ? 220 : 90,
            maxWidth: "85%",
            textAlign: "center",
          }}
        >
          {tagline}
        </div>
      </AbsoluteFill>
      <Grain />
      <Vignette />
    </AbsoluteFill>
  );
};
