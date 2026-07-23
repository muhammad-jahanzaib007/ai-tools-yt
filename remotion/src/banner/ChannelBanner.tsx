import React from "react";
import { AbsoluteFill } from "remotion";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { loadFont as loadMontserrat } from "@remotion/google-fonts/Montserrat";

// 2026-07-23: one-off YouTube channel banner (2560x1440 canvas - YouTube's
// spec; the 1546x423 centered box is the "safe area" that survives on every
// device). Owner asked for new cover art to match the insight-format pivot
// (handle stays "snackbyteai", just the visual identity updates). Same dark
// bg + single-accent language as InsightVideo/Thumb so the banner, videos,
// and thumbnails all read as one channel. Not part of the daily pipeline -
// rendered once, handed to the owner to upload via YouTube Studio (channel
// art upload is account-settings, human-domain).

const { fontFamily: antonFont } = loadAnton();
const { fontFamily: montserratFont } = loadMontserrat();

const ACCENT = "#7C5CFF";

export const ChannelBanner: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: "#07070b", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: "20%",
          top: "30%",
          width: 1400,
          height: 1400,
          borderRadius: "50%",
          background: ACCENT,
          opacity: 0.22,
          filter: "blur(220px)",
          transform: "translate(-50%,-50%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: "78%",
          top: "70%",
          width: 1100,
          height: 1100,
          borderRadius: "50%",
          background: ACCENT,
          opacity: 0.14,
          filter: "blur(200px)",
          transform: "translate(-50%,-50%)",
        }}
      />
      {/* YouTube safe area: centered 1546x423 out of 2560x1440 */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ width: 1546, height: 423, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <div
            style={{
              fontFamily: antonFont,
              fontSize: 140,
              letterSpacing: 2,
              color: "#fff",
              textTransform: "uppercase",
              textShadow: `0 0 70px ${ACCENT}aa`,
            }}
          >
            SNACKBYTE
          </div>
          <div
            style={{
              fontFamily: montserratFont,
              fontWeight: 700,
              fontSize: 46,
              color: ACCENT,
              marginTop: 14,
              letterSpacing: 1,
            }}
          >
Why your mind and body do that.
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
