import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { loadFont as loadMontserrat } from "@remotion/google-fonts/Montserrat";

// One-off brand exploration: 4 cover+avatar DIRECTIONS for the owner to pick
// from (Snackbyte Human rebrand, mind/body niche). Rendered as stills via the
// "Brand" composition with {dir, kind} props; calculateMetadata sets 2560x1440
// for kind=cover and 800x800 for kind=avatar. Not part of the pipeline.

const { fontFamily: anton } = loadAnton();
const { fontFamily: mont } = loadMontserrat("normal", { weights: ["700"], subsets: ["latin"] });

const ACCENT = "#7C5CFF";
const TAGLINE = "Why your mind and body do that.";

type Dir = "icon" | "human" | "bold" | "bright";
type Kind = "cover" | "avatar";
export type BrandProps = { dir: Dir; kind: Kind };

// Mind + body glyph: a head (circle) holding a pulse line (body) with three
// ascending thought dots (mind). Crisp vector, scales to any size.
const Glyph: React.FC<{ size: number; ring?: boolean }> = ({ size, ring }) => (
  <svg width={size} height={size} viewBox="0 0 100 100">
    {ring && <circle cx="50" cy="50" r="47" fill="none" stroke={`${ACCENT}66`} strokeWidth="2" />}
    <circle cx="47" cy="54" r="30" fill="none" stroke="#fff" strokeWidth="5" />
    <polyline
      points="24,54 37,54 43,42 51,68 57,54 70,54"
      fill="none"
      stroke={ACCENT}
      strokeWidth="5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx="74" cy="24" r="4" fill={ACCENT} />
    <circle cx="83" cy="15" r="2.6" fill={ACCENT} />
    <circle cx="89" cy="8" r="1.8" fill={ACCENT} />
  </svg>
);

const Wordmark: React.FC<{ size: number; light?: boolean }> = ({ size, light }) => (
  <div
    style={{
      fontFamily: anton,
      fontSize: size,
      letterSpacing: 2,
      textTransform: "uppercase",
      whiteSpace: "nowrap",
      lineHeight: 1,
      color: light ? "#17142E" : "#fff",
      textShadow: light ? "none" : `0 0 70px ${ACCENT}aa`,
    }}
  >
    SNACKBYTE <span style={{ color: ACCENT }}>HUMAN</span>
  </div>
);

const Tag: React.FC<{ size: number; color: string }> = ({ size, color }) => (
  <div style={{ fontFamily: mont, fontWeight: 700, fontSize: size, color, marginTop: size * 0.4, letterSpacing: 1 }}>
    {TAGLINE}
  </div>
);

const Glow: React.FC<{ x: string; y: string; d: number; o: number }> = ({ x, y, d, o }) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: d,
      height: d,
      borderRadius: "50%",
      background: ACCENT,
      opacity: o,
      filter: `blur(${d / 6}px)`,
      transform: "translate(-50%,-50%)",
    }}
  />
);

export const BrandArt: React.FC<BrandProps> = ({ dir, kind }) => {
  const cover = kind === "cover";

  // ---- DIRECTION 1: illustrated icon / mascot (vector glyph) ----
  if (dir === "icon") {
    return (
      <AbsoluteFill style={{ background: "#07070b", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
        <Glow x="30%" y="40%" d={cover ? 1300 : 620} o={0.2} />
        {cover ? (
          <div style={{ display: "flex", alignItems: "center", gap: 70 }}>
            <Glyph size={360} />
            <div>
              <Wordmark size={130} />
              <Tag size={44} color={ACCENT} />
            </div>
          </div>
        ) : (
          <Glyph size={620} ring />
        )}
      </AbsoluteFill>
    );
  }

  // ---- DIRECTION 2: real human + violet treatment ----
  if (dir === "human") {
    return (
      <AbsoluteFill style={{ background: "#07070b", overflow: "hidden" }}>
        <Img
          src={staticFile("brand/human.jpg")}
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: cover ? "70% 30%" : "center 28%",
            filter: "grayscale(0.55) contrast(1.05) brightness(0.85)",
          }}
        />
        <AbsoluteFill style={{ background: ACCENT, mixBlendMode: "color", opacity: 0.6 }} />
        <AbsoluteFill
          style={{
            background: cover
              ? "linear-gradient(90deg,#05050b 0%,#05050bcc 34%,transparent 66%)"
              : "linear-gradient(0deg,#05050bdd 0%,transparent 55%)",
          }}
        />
        {cover ? (
          <AbsoluteFill style={{ justifyContent: "center", paddingLeft: 190 }}>
            <div>
              <Wordmark size={128} />
              <Tag size={44} color="#d9d2ff" />
            </div>
          </AbsoluteFill>
        ) : (
          <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-end", paddingBottom: 60 }}>
            <div style={{ fontFamily: anton, fontSize: 96, letterSpacing: 1, color: "#fff", textShadow: `0 0 40px ${ACCENT}` }}>
              <span>S</span>
              <span style={{ color: ACCENT }}>H</span>
            </div>
          </AbsoluteFill>
        )}
      </AbsoluteFill>
    );
  }

  // ---- DIRECTION 3: bold & colourful ----
  if (dir === "bold") {
    return (
      <AbsoluteFill
        style={{
          background: "linear-gradient(135deg,#6A2CFF 0%,#B14BFF 38%,#FF4D8D 70%,#FF9A3D 100%)",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        <div style={{ position: "absolute", right: cover ? "8%" : "-10%", top: "12%", width: cover ? 520 : 360, height: cover ? 520 : 360, borderRadius: "50%", background: "#ffffff22" }} />
        <div style={{ position: "absolute", left: "6%", bottom: "-8%", width: cover ? 460 : 300, height: cover ? 460 : 300, borderRadius: "50%", background: "#ffffff1f" }} />
        {cover ? (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontFamily: anton, fontSize: 190, color: "#fff", textTransform: "uppercase", lineHeight: 0.92, letterSpacing: 2, textShadow: "0 8px 0 #00000022" }}>
              SNACKBYTE<br />HUMAN
            </div>
            <div style={{ fontFamily: mont, fontWeight: 700, fontSize: 46, color: "#fff", marginTop: 26, background: "#00000033", display: "inline-block", padding: "10px 26px", borderRadius: 40 }}>
              {TAGLINE}
            </div>
          </div>
        ) : (
          <div style={{ fontFamily: anton, fontSize: 300, color: "#fff", letterSpacing: 4, textShadow: "0 10px 0 #00000022" }}>
            S<span style={{ WebkitTextStroke: "8px #fff", color: "transparent" }}>H</span>
          </div>
        )}
      </AbsoluteFill>
    );
  }

  // ---- DIRECTION 4: brighter, still text-led ----
  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(160deg,#F4F1FF 0%,#E7E0FF 55%,#D9CEFF 100%)",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      <div style={{ position: "absolute", inset: 0, opacity: 0.5, background: "radial-gradient(circle at 78% 22%, #7C5CFF33, transparent 45%)" }} />
      {cover ? (
        <div style={{ textAlign: "center" }}>
          <Wordmark size={130} light />
          <Tag size={44} color="#5B45C7" />
        </div>
      ) : (
        <div style={{ fontFamily: anton, fontSize: 320, letterSpacing: 2, color: "#17142E" }}>
          S<span style={{ color: ACCENT }}>H</span>
        </div>
      )}
    </AbsoluteFill>
  );
};
