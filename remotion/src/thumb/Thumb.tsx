import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

// 16:9 (1280x720) hook thumbnail for the watch page / search / shares. Shorts
// feed ignores custom thumbnails, but every 16:9 surface uses this — so it must
// be edge-to-edge (no letterbox/blur bars, unlike the old frame-grab) with a
// big readable hook. Rendered as a single still by render_video.py.

export type ThumbProps = {
  kind: "ranking" | "battle" | "news" | "comic";
  title: string; // the hook line
  badge?: string; // "TOP 5" / "VS" / "AI NEWS"
  toolA?: string;
  toolB?: string;
  logos?: string[]; // staged favicon filenames (public/<logoDir>/…)
  logoDir?: string; // default "ranking"
};

const BASE = "#0A0A12";
const ACCENTS = [
  "#22D3EE", "#A855F7", "#FB7185", "#FBBF24",
  "#34D399", "#60A5FA", "#F472B6", "#F97316",
];
const pickAccent = (seed: string) => {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return ACCENTS[Math.abs(h) % ACCENTS.length];
};

// Bold-poster palette — MUST match remotion/src/ranking/RankingVideo.tsx so the
// ranking thumbnail and the video read as one design (same bg per theme).
const INK = "#0B0B0B";
const YELLOW = "#FFE100";
const BGS = [
  "#1B0FD6", "#FF5A1F", "#E60E7B", "#6D28D9",
  "#E11D2A", "#0EA5A5", "#2563EB", "#DB2777",
];
const pickBg = (seed: string) => {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return BGS[Math.abs(h) % BGS.length];
};
const outlined = (px: number): React.CSSProperties => ({
  WebkitTextStroke: `${px}px ${INK}`,
  paintOrder: "stroke fill" as unknown as React.CSSProperties["paintOrder"],
});

const FONT = "DejaVu Sans, sans-serif";

const Stage: React.FC<{ accent: string; children: React.ReactNode }> = ({
  accent,
  children,
}) => (
  <AbsoluteFill style={{ backgroundColor: BASE, overflow: "hidden" }}>
    <div
      style={{
        position: "absolute",
        width: 1100,
        height: 1100,
        borderRadius: "50%",
        left: -220,
        top: -360,
        background: `radial-gradient(circle, ${accent}3A 0%, transparent 60%)`,
      }}
    />
    <div
      style={{
        position: "absolute",
        width: 1000,
        height: 1000,
        borderRadius: "50%",
        right: -260,
        bottom: -340,
        background: `radial-gradient(circle, ${accent}22 0%, transparent 62%)`,
      }}
    />
    {/* accent edge bar */}
    <div
      style={{
        position: "absolute",
        left: 0,
        top: 0,
        bottom: 0,
        width: 16,
        backgroundColor: accent,
      }}
    />
    {children}
  </AbsoluteFill>
);

const Chip: React.FC<{ accent: string; text: string }> = ({ accent, text }) => (
  <div
    style={{
      alignSelf: "flex-start",
      backgroundColor: accent,
      color: "#0A0A12",
      fontFamily: FONT,
      fontWeight: 800,
      fontSize: 46,
      letterSpacing: 3,
      padding: "12px 34px",
      borderRadius: 16,
      boxShadow: `0 0 50px ${accent}66`,
    }}
  >
    {text}
  </div>
);

const Headline: React.FC<{ text: string; size?: number }> = ({
  text,
  size = 104,
}) => (
  <div
    style={{
      fontFamily: FONT,
      fontWeight: 800,
      fontSize: text.length > 46 ? size - 20 : size,
      lineHeight: 1.02,
      color: "#FFFFFF",
      textShadow: "0 6px 30px rgba(0,0,0,0.6)",
      maxWidth: 1140,
    }}
  >
    {text}
  </div>
);

const LogoStrip: React.FC<{ logos: string[]; dir: string; accent: string }> = ({
  logos,
  dir,
  accent,
}) => (
  <div style={{ display: "flex", gap: 20 }}>
    {logos.slice(0, 5).map((f, i) => (
      <div
        key={i}
        style={{
          width: 108,
          height: 108,
          borderRadius: 24,
          backgroundColor: "rgba(255,255,255,0.97)",
          border: `3px solid ${accent}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 12px 34px rgba(0,0,0,0.45)",
        }}
      >
        <Img
          src={staticFile(`${dir}/${f}`)}
          style={{ width: 72, height: 72, borderRadius: 12 }}
        />
      </div>
    ))}
  </div>
);

// Bold-poster ranking thumbnail — matches the ranking video: vivid bg, giant
// yellow black-outlined "TOP N", theme on a black block, favicon strip.
const RankingThumb: React.FC<{
  title: string;
  badge?: string;
  logos?: string[];
  dir: string;
}> = ({ title, badge, logos, dir }) => {
  const bg = pickBg(title || "snackbyte");
  return (
    <AbsoluteFill style={{ backgroundColor: bg, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 30% 30%, rgba(255,255,255,0.18) 0%, transparent 55%)",
        }}
      />
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 18, backgroundColor: INK }} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          flexDirection: "column",
          gap: 26,
          padding: "56px 74px",
        }}
      >
        {badge ? (
          <div
            style={{
              alignSelf: "flex-start",
              fontFamily: FONT,
              fontWeight: 800,
              fontSize: 150,
              lineHeight: 0.9,
              color: YELLOW,
              ...outlined(11),
              textShadow: "0 12px 0 rgba(0,0,0,0.28)",
            }}
          >
            {badge}
          </div>
        ) : null}
        <div
          style={{
            alignSelf: "flex-start",
            backgroundColor: INK,
            color: "#FFFFFF",
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: title.length > 40 ? 68 : 84,
            lineHeight: 1.05,
            padding: "18px 30px",
            borderRadius: 14,
            maxWidth: 1150,
          }}
        >
          {title}
        </div>
        {logos && logos.length ? (
          <div style={{ display: "flex", gap: 18 }}>
            {logos.slice(0, 5).map((f, i) => (
              <div
                key={i}
                style={{
                  width: 104,
                  height: 104,
                  borderRadius: 22,
                  backgroundColor: "#FFFFFF",
                  border: `6px solid ${INK}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Img
                  src={staticFile(`${dir}/${f}`)}
                  style={{ width: 68, height: 68, borderRadius: 12 }}
                />
              </div>
            ))}
          </div>
        ) : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const Thumb: React.FC<ThumbProps> = (props) => {
  const accent = pickAccent(props.title || props.badge || "snackbyte");
  const dir = props.logoDir || "ranking";

  if (props.kind === "ranking") {
    return (
      <RankingThumb
        title={props.title}
        badge={props.badge}
        logos={props.logos}
        dir={dir}
      />
    );
  }

  if (props.kind === "battle") {
    // Size the names to fit each ~470px side column so long tool names
    // ("Premiere Pro", "Writesonic") never clip at the frame edges.
    const maxLen = Math.max(
      (props.toolA || "").length,
      (props.toolB || "").length,
    );
    const nameSize = Math.max(50, Math.min(92, Math.floor(440 / (maxLen * 0.58))));
    const sideName: React.CSSProperties = {
      flex: 1,
      minWidth: 0,
      fontFamily: FONT,
      fontWeight: 800,
      fontSize: nameSize,
      whiteSpace: "nowrap",
      overflow: "hidden",
      color: "#FFFFFF",
      textShadow: "0 6px 30px rgba(0,0,0,0.6)",
    };
    return (
      <Stage accent={accent}>
        <AbsoluteFill
          style={{
            justifyContent: "center",
            alignItems: "center",
            flexDirection: "column",
            gap: 30,
            padding: "60px 40px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 34,
              width: "100%",
              justifyContent: "center",
            }}
          >
            <div style={{ ...sideName, textAlign: "right" }}>{props.toolA}</div>
            <div
              style={{
                backgroundColor: accent,
                color: "#0A0A12",
                fontFamily: FONT,
                fontWeight: 800,
                fontSize: 66,
                width: 140,
                height: 140,
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: `0 0 70px ${accent}88`,
                flexShrink: 0,
              }}
            >
              VS
            </div>
            <div style={{ ...sideName, textAlign: "left" }}>{props.toolB}</div>
          </div>
          {props.title ? (
            <div
              style={{
                fontFamily: FONT,
                fontWeight: 700,
                fontSize: 46,
                color: accent,
                textAlign: "center",
                maxWidth: 1040,
              }}
            >
              {props.title}
            </div>
          ) : null}
        </AbsoluteFill>
      </Stage>
    );
  }

  // news / comic: chip + big hook on the dark single-accent stage.
  return (
    <Stage accent={accent}>
      <AbsoluteFill
        style={{
          justifyContent: "center",
          flexDirection: "column",
          gap: 34,
          padding: "70px 80px",
        }}
      >
        {props.badge ? <Chip accent={accent} text={props.badge} /> : null}
        <Headline text={props.title} />
        {props.logos && props.logos.length ? (
          <LogoStrip logos={props.logos} dir={dir} accent={accent} />
        ) : null}
      </AbsoluteFill>
    </Stage>
  );
};
