import React from "react";
import { AbsoluteFill } from "remotion";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";

const { fontFamily: antonFont } = loadAnton();
const ACCENT = "#7C5CFF";

// 800x800 square profile mark for Snackbyte Human. Same dark + single-violet
// language as ChannelBanner/InsightVideo so avatar, banner and videos read as
// one channel. Shown circle-cropped and tiny on YouTube/IG, so it is a big
// centered monogram inside a circular ring (both survive a circle crop).
// Rendered once; owner uploads it (account settings = human-domain).
export const Avatar: React.FC = () => {
  return (
    <AbsoluteFill
      style={{
        background: "#07070b",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          width: 620,
          height: 620,
          borderRadius: "50%",
          background: ACCENT,
          opacity: 0.25,
          filter: "blur(150px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 640,
          height: 640,
          borderRadius: "50%",
          border: `5px solid ${ACCENT}66`,
        }}
      />
      <div
        style={{
          fontFamily: antonFont,
          fontSize: 340,
          letterSpacing: -8,
          textTransform: "uppercase",
          lineHeight: 1,
          textShadow: `0 0 70px ${ACCENT}bb`,
        }}
      >
        <span style={{ color: "#fff" }}>S</span>
        <span style={{ color: ACCENT }}>H</span>
      </div>
    </AbsoluteFill>
  );
};
