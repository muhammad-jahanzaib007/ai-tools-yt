import React from "react";
import { AbsoluteFill } from "remotion";

// Snackbyte "bitten byte" profile mark: a rounded square (a byte/snack) with a
// circular bite out of the top-right corner and two crumbs floating off - the
// original Snackbyte logo shape the owner liked, rebuilt as crisp vector for
// Snackbyte Human. The two crumbs double as thought-bubbles (the mind/body
// nod). Rendered as the "SnackAvatar" still in a few colourways to pick from.
type Theme = "coral-cream" | "coral-dark" | "violet-dark";
export type SnackProps = { theme: Theme };

const THEMES: Record<Theme, { bg: string; snack: string; c1: string; c2: string; glow: string | null }> = {
  "coral-cream": { bg: "#f2eee4", snack: "#d97757", c1: "#e7a88f", c2: "#efc7b7", glow: null },
  "coral-dark": { bg: "#0b0a0d", snack: "#e07a58", c1: "#f0a98f", c2: "#f6c9ba", glow: "#d97757" },
  "violet-dark": { bg: "#07070b", snack: "#7C5CFF", c1: "#a594ff", c2: "#cfc3ff", glow: "#7C5CFF" },
};

export const SnackMark: React.FC<SnackProps> = ({ theme }) => {
  const t = THEMES[theme];
  return (
    <AbsoluteFill style={{ background: t.bg, alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
      {t.glow && (
        <div
          style={{
            position: "absolute",
            width: 520,
            height: 520,
            borderRadius: "50%",
            background: t.glow,
            opacity: 0.22,
            filter: "blur(130px)",
          }}
        />
      )}
      <svg width={600} height={600} viewBox="0 0 100 100">
        <defs>
          <mask id="bite">
            <rect x="22" y="34" width="44" height="44" rx="13" ry="13" fill="white" />
            <circle cx="66" cy="34" r="12" fill="black" />
          </mask>
        </defs>
        <rect x="22" y="34" width="44" height="44" rx="13" ry="13" fill={t.snack} mask="url(#bite)" />
        <circle cx="72" cy="27" r="5.5" fill={t.c1} />
        <circle cx="79" cy="20" r="3.2" fill={t.c2} />
      </svg>
    </AbsoluteFill>
  );
};
