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

const ease = Easing.bezier(0.16, 1, 0.3, 1);

export const VerdictScene: React.FC<{
  toolA: string;
  toolB: string;
  rounds: RoundData[];
  verdict: string;
}> = ({ toolA, toolB, rounds, verdict }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const vertical = height > width;

  const final = scoreAfter(rounds, rounds.length - 1);
  const aWins = final.a >= final.b;
  const winner = aWins ? toolA : toolB;
  const winColor = aWins ? COLORS.coral : COLORS.teal;

  const crownScale = interpolate(frame, [0, 0.6 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.34, 1.56, 0.64, 1),
  });
  const nameOpacity = interpolate(frame, [0.4 * fps, 0.9 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const verdictOpacity = interpolate(frame, [1.2 * fps, 1.8 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const ctaOpacity = interpolate(frame, [3 * fps, 3.6 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.cream,
        alignItems: "center",
        justifyContent: "center",
        gap: vertical ? 36 : 18,
        padding: vertical ? 0 : 30,
      }}
    >
      <div style={{ scale: String(crownScale), fontSize: vertical ? 140 : 100 }}>
        👑
      </div>
      <div
        style={{
          opacity: nameOpacity,
          fontFamily,
          fontWeight: 900,
          fontSize: vertical ? 110 : 104,
          color: winColor,
          textAlign: "center",
        }}
      >
        {winner}
      </div>
      <div
        style={{
          opacity: nameOpacity,
          fontFamily,
          fontWeight: 700,
          fontSize: vertical ? 56 : 48,
          color: COLORS.dark,
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
        }}
      >
        {verdict}
      </div>
      <div
        style={{
          opacity: ctaOpacity,
          fontFamily,
          fontWeight: 700,
          fontSize: vertical ? 44 : 38,
          color: COLORS.cream,
          backgroundColor: COLORS.coral,
          padding: "20px 40px",
          borderRadius: 999,
          marginTop: vertical ? 20 : 8,
        }}
      >
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
        Snackbyte AI — new battle every week
      </div>
    </AbsoluteFill>
  );
};
