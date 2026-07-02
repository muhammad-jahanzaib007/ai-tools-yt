import React from "react";
import { useVideoConfig } from "remotion";
import { COLORS } from "./types";
import { fontFamily } from "./font";

export const Scoreboard: React.FC<{
  toolA: string;
  toolB: string;
  scoreA: number;
  scoreB: number;
}> = ({ toolA, toolB, scoreA, scoreB }) => {
  const { width, height } = useVideoConfig();
  const vertical = height > width;
  const chip: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 18,
    fontFamily,
    fontWeight: 700,
    fontSize: vertical ? 40 : 44,
    color: COLORS.cream,
    padding: "14px 30px",
    borderRadius: 999,
  };
  const score: React.CSSProperties = {
    fontWeight: 900,
    fontSize: vertical ? 48 : 52,
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
      <div style={{ ...chip, backgroundColor: COLORS.coral }}>
        <span>{toolA}</span>
        <span style={score}>{scoreA}</span>
      </div>
      <div style={{ ...chip, backgroundColor: COLORS.teal }}>
        <span style={score}>{scoreB}</span>
        <span>{toolB}</span>
      </div>
    </div>
  );
};
