import React from "react";

// Crisp vector emblems (not AI) so every hero carries a correct, readable
// symbol for its tool. Grouped by what the tool does. Rendered in the hero's
// colour, shown as a glowing chest/nameplate crest in the comic scenes.

type Glyph = (c: string) => React.ReactNode;

const stroke = (c: string, w = 7): React.SVGAttributes<SVGElement> => ({
  fill: "none",
  stroke: c,
  strokeWidth: w,
  strokeLinecap: "round",
  strokeLinejoin: "round",
});

const GLYPHS: Record<string, Glyph> = {
  // chat / assistant
  bubble: (c) => (
    <>
      <path {...stroke(c)} d="M18 22h64a6 6 0 0 1 6 6v34a6 6 0 0 1-6 6H44l-16 14V68h-10a6 6 0 0 1-6-6V28a6 6 0 0 1 6-6Z" />
      <circle cx="35" cy="45" r="4" fill={c} />
      <circle cx="50" cy="45" r="4" fill={c} />
      <circle cx="65" cy="45" r="4" fill={c} />
    </>
  ),
  // writing
  quill: (c) => (
    <>
      <path {...stroke(c)} d="M74 24C50 30 34 48 28 74l10 2c22-6 38-24 44-48Z" />
      <path {...stroke(c, 6)} d="M26 80l16-16" />
    </>
  ),
  // voice / audio
  wave: (c) => (
    <g>
      {[24, 36, 48, 60, 72].map((x, i) => {
        const h = [18, 34, 26, 40, 20][i];
        return <line key={x} x1={x} y1={50 - h / 2} x2={x} y2={50 + h / 2} {...stroke(c, 8)} />;
      })}
    </g>
  ),
  // image / art
  brush: (c) => (
    <>
      <path {...stroke(c)} d="M70 22 44 48m0 0-6 6c-6 6-6 14-14 18 8 2 16 0 22-6l4-4Z" />
      <circle cx="72" cy="24" r="7" fill={c} />
    </>
  ),
  // video / play
  play: (c) => (
    <>
      <rect x="18" y="24" width="64" height="52" rx="8" {...stroke(c)} />
      <path d="M44 38l20 12-20 12Z" fill={c} />
    </>
  ),
  // design
  palette: (c) => (
    <>
      <path {...stroke(c)} d="M50 20c-18 0-30 12-30 28 0 12 10 16 16 16 6 0 6 6 12 6 16 0 24-12 24-26 0-14-10-24-22-24Z" />
      <circle cx="38" cy="40" r="4" fill={c} />
      <circle cx="52" cy="34" r="4" fill={c} />
      <circle cx="64" cy="44" r="4" fill={c} />
    </>
  ),
  // notes / productivity
  blocks: (c) => (
    <>
      <rect x="20" y="20" width="26" height="26" rx="4" {...stroke(c)} />
      <rect x="54" y="20" width="26" height="26" rx="4" {...stroke(c)} />
      <rect x="20" y="54" width="26" height="26" rx="4" {...stroke(c)} />
      <rect x="54" y="54" width="26" height="26" rx="4" {...stroke(c)} />
    </>
  ),
  // analytics
  chart: (c) => (
    <>
      <line x1="22" y1="80" x2="22" y2="30" {...stroke(c)} />
      <line x1="22" y1="80" x2="82" y2="80" {...stroke(c)} />
      <rect x="34" y="56" width="12" height="24" fill={c} />
      <rect x="52" y="44" width="12" height="36" fill={c} />
      <rect x="70" y="32" width="12" height="48" fill={c} />
    </>
  ),
  // shield (grammar / guardian)
  shield: (c) => (
    <>
      <path {...stroke(c)} d="M50 18l28 10v22c0 18-12 28-28 34-16-6-28-16-28-34V28Z" />
      <path {...stroke(c, 8)} d="M38 50l9 10 18-20" />
    </>
  ),
  // target (campaign)
  target: (c) => (
    <>
      <circle cx="50" cy="50" r="30" {...stroke(c)} />
      <circle cx="50" cy="50" r="16" {...stroke(c)} />
      <circle cx="50" cy="50" r="4" fill={c} />
    </>
  ),
  // twin stars (gemini)
  stars: (c) => (
    <>
      <path d="M38 30l5 12 12 3-12 3-5 12-5-12-12-3 12-3Z" fill={c} />
      <path d="M66 52l4 9 9 2-9 2-4 9-4-9-9-2 9-2Z" fill={c} />
    </>
  ),
};

// tool slug -> glyph
const MAP: Record<string, string> = {
  chatgpt: "bubble", claude: "bubble", gemini: "stars",
  midjourney: "brush", canva: "palette", "adobe-express": "palette",
  elevenlabs: "wave", speechify: "wave", murf: "wave", descript: "wave",
  writesonic: "quill", jasper: "target", "copy-ai": "quill", rytr: "quill",
  grammarly: "shield", "notion-ai": "blocks",
  pictory: "play", invideo: "play", synthesia: "bubble", heygen: "bubble",
  "premiere-pro": "play", tubebuddy: "chart", vidiq: "chart",
};

export const Emblem: React.FC<{ slug: string; color: string; size?: number }> = ({
  slug,
  color,
  size = 120,
}) => {
  const glyph = GLYPHS[MAP[slug] || "bubble"];
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" style={{ filter: `drop-shadow(0 0 10px ${color})` }}>
      <circle cx="50" cy="50" r="46" fill="rgba(255,255,255,0.92)" stroke={color} strokeWidth="5" />
      {glyph(color)}
    </svg>
  );
};
