import React from "react";
import { AbsoluteFill } from "remotion";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { loadFont as loadMontserrat } from "@remotion/google-fonts/Montserrat";
import { CookieGlyph } from "./Cookie";

// Final Snackbyte Human YouTube cover (2560x1440): cookie mark + wordmark on
// near-black with a warm gold glow. Content sits inside YouTube's centered
// 1546x423 safe area so it survives on mobile.
const { fontFamily: anton } = loadAnton();
const { fontFamily: mont } = loadMontserrat("normal", { weights: ["700"], subsets: ["latin"] });
const GOLD = "#e6a95c";

export const CoverFinal: React.FC = () => (
  <AbsoluteFill style={{ background: "#0b0a0d", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
    <div
      style={{
        position: "absolute",
        left: "38%",
        top: "48%",
        width: 1500,
        height: 1500,
        borderRadius: "50%",
        background: "#e0a05a",
        opacity: 0.13,
        filter: "blur(240px)",
        transform: "translate(-50%,-50%)",
      }}
    />
    <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
      <CookieGlyph size={320} />
      <div>
        <div
          style={{
            fontFamily: anton,
            fontSize: 118,
            letterSpacing: 2,
            textTransform: "uppercase",
            whiteSpace: "nowrap",
            lineHeight: 1,
            color: "#fff",
          }}
        >
          SNACKBYTE <span style={{ color: GOLD }}>HUMAN</span>
        </div>
        <div style={{ fontFamily: mont, fontWeight: 700, fontSize: 44, color: GOLD, marginTop: 16, letterSpacing: 1 }}>
          Why your mind and body do that.
        </div>
      </div>
    </div>
  </AbsoluteFill>
);
