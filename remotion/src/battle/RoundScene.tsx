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
import { Scoreboard } from "./Scoreboard";
import { AnimatedBg } from "./AnimatedBg";

const ease = Easing.bezier(0.16, 1, 0.3, 1);

export const RoundScene: React.FC<{
  toolA: string;
  toolB: string;
  rounds: RoundData[];
  index: number;
}> = ({ toolA, toolB, rounds, index }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const vertical = height > width;
  const round = rounds[index];

  const titleY = interpolate(frame, [0, 0.5 * fps], [40, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const titleOpacity = interpolate(frame, [0, 0.4 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const cardA = interpolate(frame, [0.6 * fps, 1.2 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const cardB = interpolate(frame, [1.2 * fps, 1.8 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  // winner highlight kicks in near the end of the round, however long the
  // narration made it (durationInFrames = this Sequence's duration)
  const winnerAt = Math.max(2.2 * fps, durationInFrames - 2.6 * fps);
  const winnerPop = interpolate(frame, [winnerAt, winnerAt + 0.5 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.34, 1.56, 0.64, 1),
  });

  // scoreboard shows score up to previous round, then updates on winner reveal
  const prev = scoreAfter(rounds, index - 1);
  const cur = scoreAfter(rounds, index);
  const shown = frame >= winnerAt ? cur : prev;

  const card = (
    tool: string,
    point: string,
    color: string,
    progress: number,
    isWinner: boolean,
  ): React.CSSProperties & { children?: never } => ({
    opacity: progress,
    translate: `0px ${(1 - progress) * 60}px`,
    backgroundColor: "rgba(255,255,255,0.06)",
    border: `6px solid ${isWinner && winnerPop > 0 ? color : "rgba(255,255,255,0.15)"}`,
    boxShadow:
      isWinner && winnerPop > 0 ? `0 0 ${60 * winnerPop}px ${color}` : "none",
    borderRadius: 28,
    padding: vertical ? "40px 44px" : "48px 56px",
    width: vertical ? "84%" : "42%",
    fontFamily,
    color: COLORS.cream,
  });

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <AnimatedBg variant={index + 1} />
      <Scoreboard toolA={toolA} toolB={toolB} scoreA={shown.a} scoreB={shown.b} />
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          gap: vertical ? 40 : 60,
          flexDirection: "column",
        }}
      >
        <div
          style={{
            opacity: titleOpacity,
            translate: `0px ${titleY}px`,
            fontFamily,
            fontWeight: 900,
            fontSize: vertical ? 64 : 76,
            color: COLORS.cream,
            textAlign: "center",
          }}
        >
          <span style={{ color: COLORS.coral }}>ROUND {index + 1}</span>
          {"  "}
          {round.title}
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: vertical ? "column" : "row",
            gap: vertical ? 36 : 48,
            width: "100%",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div style={card(toolA, round.aPoint, COLORS.coral, cardA, round.winner === "a")}>
            <div style={{ fontWeight: 900, fontSize: vertical ? 52 : 56, color: COLORS.coral }}>
              {toolA}
              {round.winner === "a" && winnerPop > 0 ? "  ✓" : ""}
            </div>
            <div style={{ fontWeight: 500, fontSize: vertical ? 44 : 46, marginTop: 18 }}>
              {round.aPoint}
            </div>
          </div>
          <div style={card(toolB, round.bPoint, COLORS.teal, cardB, round.winner === "b")}>
            <div style={{ fontWeight: 900, fontSize: vertical ? 52 : 56, color: COLORS.teal }}>
              {toolB}
              {round.winner === "b" && winnerPop > 0 ? "  ✓" : ""}
            </div>
            <div style={{ fontWeight: 500, fontSize: vertical ? 44 : 46, marginTop: 18 }}>
              {round.bPoint}
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
