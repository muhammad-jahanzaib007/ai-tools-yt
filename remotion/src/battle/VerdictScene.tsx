import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS, RoundData, scoreAfter } from "./types";
import { fontFamily } from "./font";
import { AnimatedBg } from "./AnimatedBg";
import { Confetti, Grain, ShineSweep } from "./fx";

const ease = Easing.bezier(0.16, 1, 0.3, 1);
const bounce = Easing.bezier(0.34, 1.8, 0.5, 1);

export const VerdictScene: React.FC<{
  toolA: string;
  toolB: string;
  rounds: RoundData[];
  verdict: string;
}> = ({ toolA, toolB, rounds, verdict }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const vertical = height > width;

  const final = scoreAfter(rounds, rounds.length - 1);
  const aWins = final.a >= final.b;
  const winner = aWins ? toolA : toolB;
  const winColor = aWins ? COLORS.coral : COLORS.teal;
  const winGradient = aWins
    ? "linear-gradient(180deg, #E8926B 10%, #B85A38 90%)"
    : "linear-gradient(180deg, #35B5AA 10%, #1E7C74 90%)";

  const crownDrop = interpolate(frame, [0, 0.6 * fps], [-260, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: bounce,
  });
  const crownOpacity = interpolate(frame, [0, 0.25 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const nameOpacity = interpolate(frame, [0.4 * fps, 0.9 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const nameScale = interpolate(frame, [0.4 * fps, 0.95 * fps], [0.85, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: bounce,
  });
  const verdictOpacity = interpolate(frame, [1.2 * fps, 1.8 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const ctaAt = Math.max(2 * fps, Math.min(3 * fps, durationInFrames * 0.35));
  const ctaOpacity = interpolate(frame, [ctaAt, ctaAt + 0.6 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const ctaRise = interpolate(frame, [ctaAt, ctaAt + 0.6 * fps], [30, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const halo = 0.5 + 0.5 * Math.sin(frame / 7);

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.cream }}>
      <AnimatedBg light />
      <Confetti colors={[COLORS.coral, COLORS.teal, "#E8B93C", COLORS.dark]} />
      {/* content in its own positioned layer so it paints above the bg */}
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          gap: vertical ? 34 : 18,
          padding: vertical ? 0 : 30,
        }}
      >
        <div
          style={{
            opacity: crownOpacity,
            translate: `0px ${crownDrop}px`,
            fontSize: vertical ? 140 : 100,
            filter: `drop-shadow(0 14px 40px rgba(232,185,60,${0.35 + halo * 0.3}))`,
          }}
        >
          👑
        </div>
        <div
          style={{
            opacity: nameOpacity,
            scale: String(nameScale),
            fontFamily,
            fontWeight: 900,
            fontSize: vertical ? 116 : 108,
            backgroundImage: winGradient,
            backgroundClip: "text",
            WebkitBackgroundClip: "text",
            color: "transparent",
            textAlign: "center",
            letterSpacing: "-0.02em",
            filter: `drop-shadow(0 10px 34px ${winColor}55)`,
          }}
        >
          {winner}
        </div>
        <div
          style={{
            opacity: nameOpacity,
            fontFamily,
            fontWeight: 800,
            fontSize: vertical ? 50 : 44,
            color: COLORS.cream,
            background: "linear-gradient(135deg, #2B2A24 0%, #1A1915 100%)",
            padding: "12px 38px",
            borderRadius: 999,
            boxShadow: "0 16px 40px rgba(26,25,21,0.35)",
          }}
        >
          wins {Math.max(final.a, final.b)}–{Math.min(final.a, final.b)}
        </div>
        <div
          style={{
            opacity: verdictOpacity,
            fontFamily,
            fontWeight: 500,
            fontSize: vertical ? 46 : 40,
            color: COLORS.dark,
            maxWidth: "80%",
            textAlign: "center",
            lineHeight: 1.35,
          }}
        >
          {verdict}
        </div>
        <div
          style={{
            opacity: ctaOpacity,
            translate: `0px ${ctaRise}px`,
            position: "relative",
            overflow: "hidden",
            fontFamily,
            fontWeight: 700,
            fontSize: vertical ? 44 : 38,
            color: COLORS.cream,
            background: "linear-gradient(135deg, #E8926B 0%, #C2603D 100%)",
            border: "1.5px solid rgba(255,255,255,0.35)",
            padding: "22px 44px",
            borderRadius: 999,
            boxShadow: "0 20px 50px rgba(217,119,87,0.45)",
          }}
        >
          <ShineSweep at={ctaAt + fps} duration={0.7 * fps} strength={0.45} />
          Links + deals in the description ↓
        </div>
        <div
          style={{
            opacity: ctaOpacity,
            fontFamily,
            fontWeight: 700,
            fontSize: vertical ? 38 : 32,
            color: COLORS.dark,
          }}
        >
          Snackbyte AI · new AI battle every day
        </div>
      </AbsoluteFill>
      <Grain opacity={0.04} />
    </AbsoluteFill>
  );
};
