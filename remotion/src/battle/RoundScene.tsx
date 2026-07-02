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
import { Grain, SparkBurst, Vignette } from "./fx";

const ease = Easing.bezier(0.16, 1, 0.3, 1);
const pop = Easing.bezier(0.34, 1.56, 0.64, 1);

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

  const titleY = interpolate(frame, [0, 0.5 * fps], [50, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const titleOpacity = interpolate(frame, [0, 0.4 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const cardA = interpolate(frame, [0.6 * fps, 1.25 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  const cardB = interpolate(frame, [1.2 * fps, 1.85 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  // winner highlight kicks in near the end of the round, however long the
  // narration made it (durationInFrames = this Sequence's duration)
  const winnerAt = Math.max(2.2 * fps, durationInFrames - 2.6 * fps);
  const winnerPop = interpolate(frame, [winnerAt, winnerAt + 0.5 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  const glowPulse = 0.6 + 0.4 * Math.sin((frame - winnerAt) / 4);

  // scoreboard shows score up to previous round, then updates on winner reveal
  const prev = scoreAfter(rounds, index - 1);
  const cur = scoreAfter(rounds, index);
  const shown = frame >= winnerAt ? cur : prev;

  const card = (
    color: string,
    progress: number,
    isWinner: boolean,
  ): React.CSSProperties => {
    const dim = !isWinner && winnerPop > 0;
    return {
      position: "relative",
      overflow: "hidden",
      opacity: progress * (dim ? 0.55 : 1),
      translate: `0px ${(1 - progress) * 90}px`,
      rotate: `${(1 - progress) * (isWinner ? -2.5 : 2.5)}deg`,
      scale: String(dim ? 0.97 : 1 + winnerPop * (isWinner ? 0.03 : 0)),
      background: "rgba(255,255,255,0.07)",
      backdropFilter: "blur(18px)",
      border: `5px solid ${isWinner && winnerPop > 0 ? color : "rgba(255,255,255,0.14)"}`,
      boxShadow:
        isWinner && winnerPop > 0
          ? `0 0 ${70 * winnerPop * glowPulse}px ${color}, 0 24px 60px rgba(0,0,0,0.45)`
          : "0 24px 60px rgba(0,0,0,0.35)",
      borderRadius: 32,
      padding: vertical ? "42px 46px" : "48px 56px",
      width: vertical ? "84%" : "42%",
      fontFamily,
      color: COLORS.cream,
    };
  };

  const cardGloss: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    background:
      "linear-gradient(180deg, rgba(255,255,255,0.10) 0%, transparent 40%)",
    pointerEvents: "none",
  };

  const winnerSide = round.winner === "a";

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <AnimatedBg variant={index + 1} />
      <Scoreboard
        toolA={toolA}
        toolB={toolB}
        scoreA={shown.a}
        scoreB={shown.b}
        popAt={winnerAt}
      />
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          gap: vertical ? 44 : 60,
          flexDirection: "column",
        }}
      >
        <div
          style={{
            opacity: titleOpacity,
            translate: `0px ${titleY}px`,
            display: "flex",
            alignItems: "center",
            gap: 26,
          }}
        >
          <div
            style={{
              fontFamily,
              fontWeight: 900,
              fontSize: vertical ? 46 : 52,
              color: COLORS.cream,
              background: "linear-gradient(135deg, #E8926B 0%, #C2603D 100%)",
              boxShadow: "0 12px 34px rgba(217,119,87,0.45)",
              padding: "14px 34px",
              borderRadius: 999,
              letterSpacing: "0.04em",
            }}
          >
            ROUND {index + 1}
          </div>
          <div
            style={{
              fontFamily,
              fontWeight: 900,
              fontSize: vertical ? 66 : 78,
              backgroundImage: "linear-gradient(180deg, #FFFFFF 20%, #D8D2C2 100%)",
              backgroundClip: "text",
              WebkitBackgroundClip: "text",
              color: "transparent",
              textShadow: "0 10px 40px rgba(0,0,0,0.4)",
            }}
          >
            {round.title}
          </div>
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: vertical ? "column" : "row",
            gap: vertical ? 40 : 48,
            width: "100%",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
          }}
        >
          <div style={card(COLORS.coral, cardA, winnerSide)}>
            <div style={cardGloss} />
            {winnerSide ? (
              <SparkBurst at={winnerAt} color={COLORS.coral} size={220} seed={`w${index}`} />
            ) : null}
            <div
              style={{
                fontWeight: 900,
                fontSize: vertical ? 54 : 58,
                color: COLORS.coral,
                display: "flex",
                alignItems: "center",
                gap: 18,
              }}
            >
              {toolA}
              {winnerSide && winnerPop > 0 ? (
                <span
                  style={{
                    scale: String(winnerPop),
                    display: "inline-flex",
                    width: 56,
                    height: 56,
                    borderRadius: "50%",
                    background: COLORS.coral,
                    color: COLORS.dark,
                    fontSize: 38,
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  ✓
                </span>
              ) : null}
            </div>
            <div style={{ fontWeight: 500, fontSize: vertical ? 44 : 46, marginTop: 18 }}>
              {round.aPoint}
            </div>
          </div>
          <div style={card(COLORS.teal, cardB, !winnerSide)}>
            <div style={cardGloss} />
            {!winnerSide ? (
              <SparkBurst at={winnerAt} color={COLORS.teal} size={220} seed={`w${index}`} />
            ) : null}
            <div
              style={{
                fontWeight: 900,
                fontSize: vertical ? 54 : 58,
                color: COLORS.teal,
                display: "flex",
                alignItems: "center",
                gap: 18,
              }}
            >
              {toolB}
              {!winnerSide && winnerPop > 0 ? (
                <span
                  style={{
                    scale: String(winnerPop),
                    display: "inline-flex",
                    width: 56,
                    height: 56,
                    borderRadius: "50%",
                    background: COLORS.teal,
                    color: COLORS.dark,
                    fontSize: 38,
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  ✓
                </span>
              ) : null}
            </div>
            <div style={{ fontWeight: 500, fontSize: vertical ? 44 : 46, marginTop: 18 }}>
              {round.bPoint}
            </div>
          </div>
        </div>
      </AbsoluteFill>
      <Grain />
      <Vignette />
    </AbsoluteFill>
  );
};
