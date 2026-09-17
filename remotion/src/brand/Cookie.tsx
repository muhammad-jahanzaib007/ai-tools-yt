import React from "react";
import { AbsoluteFill } from "remotion";

// Snackbyte Human mark, cookie version (owner ask): a round cookie with a
// bitten (scalloped) edge, chocolate chips, and two crumbs floating off the
// bite - "snack + byte/bite" made literal, warm and friendly for a mind/body
// channel. CookieGlyph is the bare vector (reused by the avatar + the cover);
// Cookie wraps it on a background for the "CookieAvatar" still.

const COOKIE = "#d99a52";
const COOKIE_EDGE = "#c07f38";
const CHIP = "#43291a";
const CRUMB1 = "#d99a52";
const CRUMB2 = "#e8bd83";

export const CookieGlyph: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 100 100">
    <defs>
      <mask id="cookieBite">
        <circle cx="46" cy="54" r="30" fill="white" />
        <circle cx="72" cy="30" r="16" fill="black" />
        <circle cx="62" cy="22" r="6.5" fill="black" />
        <circle cx="82" cy="42" r="7" fill="black" />
      </mask>
    </defs>
    <g mask="url(#cookieBite)">
      <circle cx="46" cy="54" r="30" fill={COOKIE_EDGE} />
      <circle cx="46" cy="54" r="27" fill={COOKIE} />
      {/* chips wired as a tiny neural network = the mind/body content cue */}
      <polyline
        points="36,50 55,47 52,54 50,62 40,67 33,59 36,50"
        fill="none"
        stroke={CHIP}
        strokeWidth="1.2"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.5"
      />
      <circle cx="36" cy="50" r="4" fill={CHIP} />
      <circle cx="50" cy="62" r="4.6" fill={CHIP} />
      <circle cx="40" cy="67" r="3.4" fill={CHIP} />
      <circle cx="55" cy="47" r="3.1" fill={CHIP} />
      <circle cx="33" cy="59" r="3" fill={CHIP} />
      <circle cx="52" cy="54" r="2.4" fill={CHIP} />
    </g>
    <circle cx="76" cy="24" r="4" fill={CRUMB1} />
    <circle cx="83" cy="17" r="2.4" fill={CRUMB2} />
  </svg>
);

export type CookieProps = { theme: "dark" | "cream" };
const BG = {
  dark: { bg: "#0b0a0d", glow: "#e0a05a" as string | null },
  cream: { bg: "#f2eee4", glow: null as string | null },
};

export const Cookie: React.FC<CookieProps> = ({ theme }) => {
  const t = BG[theme];
  return (
    <AbsoluteFill style={{ background: t.bg, alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
      {t.glow && (
        <div style={{ position: "absolute", width: 520, height: 520, borderRadius: "50%", background: t.glow, opacity: 0.2, filter: "blur(130px)" }} />
      )}
      <CookieGlyph size={600} />
    </AbsoluteFill>
  );
};
