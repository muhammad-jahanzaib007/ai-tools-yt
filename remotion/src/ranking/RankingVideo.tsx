import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { FPS, TRANSITION_FRAMES } from "../battle/types";
import { Confetti, Grain, SparkBurst, Vignette } from "../battle/fx";

export type RankItem = {
  rank: number; // 5..1
  name: string;
  reason: string; // one display line
  tag: string; // short chip, e.g. "Free plan" / "Paid"
};

export type RankingProps = {
  theme: string; // big intro claim (the hook, compressed)
  items: RankItem[]; // countdown display order: rank 5 first ... rank 1 last
  cta: string; // outro line
  logos?: Record<string, string>; // favicon per rank (best-effort)
  sceneFrames?: { intro: number; rounds: number[]; verdict: number };
};

const INTRO_FRAMES = 3 * FPS;
const ITEM_FRAMES = 7 * FPS;
const OUTRO_FRAMES = 6 * FPS;

export const framesOfRanking = (p: RankingProps) => {
  const MIN_SCENE = 2 * TRANSITION_FRAMES + 5;
  const f =
    p.sceneFrames && p.sceneFrames.rounds.length === p.items.length
      ? p.sceneFrames
      : {
          intro: INTRO_FRAMES,
          rounds: p.items.map(() => ITEM_FRAMES),
          verdict: OUTRO_FRAMES,
        };
  return {
    intro: Math.max(MIN_SCENE, f.intro),
    rounds: f.rounds.map((r) => Math.max(MIN_SCENE, r)),
    verdict: Math.max(MIN_SCENE, f.verdict),
  };
};

export const totalRankingFrames = (p: RankingProps) => {
  const f = framesOfRanking(p);
  return (
    f.intro +
    f.rounds.reduce((a, b) => a + b, 0) +
    f.verdict -
    (p.items.length + 1) * TRANSITION_FRAMES
  );
};

// VISUAL DIRECTION "BOLD POSTER" (owner picked a fusion of the Bold and Poster
// explorations, 2026-07-14): vivid saturated per-video background, a GIANT
// hot-yellow rank numeral bleeding off the top with a thick black outline, and
// a black bottom block holding the tool name / tag / reason. Loud, graphic,
// high-CTR — one focal point per scene per the video-layout rule.
const INK = "#0B0B0B";
const YELLOW = "#FFE100";
const CHIP = "#FF2D55";
// Vivid, saturated backgrounds — one per video (hashed from the theme).
const BGS = [
  "#1B0FD6", // electric blue
  "#FF5A1F", // orange
  "#E60E7B", // magenta
  "#6D28D9", // violet
  "#E11D2A", // red
  "#0EA5A5", // teal
  "#2563EB", // blue
  "#DB2777", // pink
];
const pickBg = (seed: string) => {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return BGS[Math.abs(h) % BGS.length];
};

const FONT = "DejaVu Sans, sans-serif";
const outlined = (px: number): React.CSSProperties => ({
  WebkitTextStroke: `${px}px ${INK}`,
  paintOrder: "stroke fill" as unknown as React.CSSProperties["paintOrder"],
});

const Radial: React.FC = () => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      background:
        "radial-gradient(circle at 50% 34%, rgba(255,255,255,0.20) 0%, transparent 56%)",
    }}
  />
);

// Favicon or letter monogram — a small brand mark that always exists.
const ToolIcon: React.FC<{ logo?: string; name: string; size: number }> = ({
  logo,
  name,
  size,
}) =>
  logo ? (
    <Img
      src={staticFile(`ranking/${logo}`)}
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.22,
        border: `${Math.round(size * 0.05)}px solid ${INK}`,
        flexShrink: 0,
      }}
    />
  ) : (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.22,
        backgroundColor: YELLOW,
        border: `${Math.round(size * 0.05)}px solid ${INK}`,
        color: INK,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: FONT,
        fontWeight: 800,
        fontSize: size * 0.52,
        flexShrink: 0,
      }}
    >
      {(name || "?").slice(0, 1).toUpperCase()}
    </div>
  );

const IntroScene: React.FC<{ theme: string; count: number; bg: string }> = ({
  theme,
  count,
  bg,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 10, stiffness: 180 } });
  const up = spring({ frame: frame - 8, fps, config: { damping: 14 } });
  return (
    <AbsoluteFill style={{ backgroundColor: bg, overflow: "hidden" }}>
      <Radial />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 44,
          padding: "0 70px",
        }}
      >
        <div
          style={{
            scale: String(pop),
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: 260,
            lineHeight: 0.9,
            color: YELLOW,
            ...outlined(14),
            textShadow: "0 20px 0 rgba(0,0,0,0.3)",
          }}
        >
          TOP {count}
        </div>
        <div
          style={{
            opacity: up,
            translate: `0 ${(1 - up) * 60}px`,
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: 78,
            lineHeight: 1.12,
            textAlign: "center",
            color: "#FFFFFF",
            backgroundColor: INK,
            padding: "22px 40px",
            borderRadius: 18,
          }}
        >
          {theme}
        </div>
      </AbsoluteFill>
      <Grain />
      <Vignette strength={0.3} />
    </AbsoluteFill>
  );
};

const RankScene: React.FC<{ item: RankItem; bg: string; logo?: string }> = ({
  item,
  bg,
  logo,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isWinner = item.rank === 1;
  const slam = spring({ frame, fps, config: { damping: 12, stiffness: 150 } });
  const blockIn = spring({ frame: frame - 4, fps, config: { damping: 15 } });
  const nameIn = spring({ frame: frame - 10, fps, config: { damping: 12, stiffness: 160 } });
  const chipIn = spring({ frame: frame - 16, fps, config: { damping: 14 } });
  const reasonIn = spring({ frame: frame - 22, fps, config: { damping: 14 } });
  const numY = interpolate(slam, [0, 1], [-460, 0]);
  const nameSize = Math.max(66, Math.min(150, Math.floor(1120 / Math.max(6, item.name.length))));
  const blockBg = isWinner ? YELLOW : INK;
  const blockFg = isWinner ? INK : "#FFFFFF";
  return (
    <AbsoluteFill style={{ backgroundColor: bg, overflow: "hidden" }}>
      <Radial />
      {/* POSTER-style rank numeral: enormous, bleeding off the top-right corner
          as an intentional graphic element (not centered). */}
      <div
        style={{
          position: "absolute",
          top: -180,
          right: -90,
          translate: `0 ${numY}px`,
          fontFamily: FONT,
          fontWeight: 800,
          fontSize: 1500,
          lineHeight: 0.8,
          color: YELLOW,
          ...outlined(18),
          textShadow: "0 30px 0 rgba(0,0,0,0.28)",
        }}
      >
        {item.rank}
      </div>
      {isWinner && (
        <Confetti colors={[YELLOW, "#FFFFFF", CHIP, bg]} count={34} />
      )}
      <SparkBurst at={2} color={YELLOW} size={320} count={12} seed={`r${item.rank}`} />
      {/* bottom block: name + tag + reason */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          minHeight: 760,
          backgroundColor: blockBg,
          borderTop: `10px solid ${INK}`,
          translate: `0 ${(1 - blockIn) * 780}px`,
          padding: "56px 64px 96px",
          display: "flex",
          flexDirection: "column",
          gap: 26,
        }}
      >
        <div style={{ scale: String(nameIn), display: "flex", alignItems: "center", gap: 26 }}>
          <ToolIcon logo={logo} name={item.name} size={isWinner ? 116 : 100} />
          <div
            style={{
              fontFamily: FONT,
              fontWeight: 800,
              fontSize: nameSize,
              lineHeight: 0.98,
              color: blockFg,
            }}
          >
            {item.name}
          </div>
        </div>
        <div
          style={{
            opacity: chipIn,
            rotate: `${(1 - chipIn) * -8 - 3}deg`,
            alignSelf: "flex-start",
            backgroundColor: CHIP,
            color: "#FFFFFF",
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: 44,
            padding: "12px 36px",
            borderRadius: 14,
            border: `6px solid ${INK}`,
          }}
        >
          {item.tag.toUpperCase()}
        </div>
        <div
          style={{
            opacity: reasonIn,
            translate: `0 ${(1 - reasonIn) * 40}px`,
            fontFamily: FONT,
            fontWeight: 700,
            fontSize: 52,
            lineHeight: 1.2,
            color: blockFg,
            maxWidth: 940,
          }}
        >
          {item.reason}
        </div>
      </div>
      <Grain />
    </AbsoluteFill>
  );
};

const OutroScene: React.FC<{
  items: RankItem[];
  cta: string;
  bg: string;
  logos?: Record<string, string>;
}> = ({ items, cta, bg, logos }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const byRank = [...items].sort((a, b) => a.rank - b.rank);
  return (
    <AbsoluteFill style={{ backgroundColor: bg, overflow: "hidden" }}>
      <Radial />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 16,
          padding: "0 70px",
        }}
      >
        {byRank.map((it, i) => {
          const rowIn = spring({ frame: frame - i * 5, fps, config: { damping: 14 } });
          const top = it.rank === 1;
          return (
            <div
              key={it.rank}
              style={{
                opacity: rowIn,
                translate: `${(1 - rowIn) * 80}px 0`,
                backgroundColor: top ? YELLOW : INK,
                border: `6px solid ${INK}`,
                borderRadius: 18,
                width: "100%",
                maxWidth: 900,
                padding: top ? "22px 34px" : "16px 34px",
                display: "flex",
                alignItems: "center",
                gap: 24,
              }}
            >
              <div
                style={{
                  fontFamily: FONT,
                  fontWeight: 800,
                  fontSize: top ? 58 : 44,
                  color: top ? INK : YELLOW,
                  width: 88,
                }}
              >
                #{it.rank}
              </div>
              {logos && logos[String(it.rank)] ? (
                <Img
                  src={staticFile(`ranking/${logos[String(it.rank)]}`)}
                  style={{ width: top ? 60 : 46, height: top ? 60 : 46, borderRadius: 10 }}
                />
              ) : null}
              <div
                style={{
                  fontFamily: FONT,
                  fontWeight: 800,
                  fontSize: top ? 56 : 44,
                  color: top ? INK : "#FFFFFF",
                }}
              >
                {it.name}
              </div>
            </div>
          );
        })}
        <div
          style={{
            marginTop: 24,
            opacity: interpolate(frame, [26, 44], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: 46,
            color: "#FFFFFF",
            backgroundColor: INK,
            padding: "16px 32px",
            borderRadius: 14,
            textAlign: "center",
          }}
        >
          {cta}
        </div>
      </AbsoluteFill>
      <Grain />
      <Vignette strength={0.3} />
    </AbsoluteFill>
  );
};

export const RankingVideo: React.FC<RankingProps> = (props) => {
  const frames = framesOfRanking(props);
  const bg = pickBg(props.theme || "snackbyte");
  const count = props.items.length;
  const seq: React.ReactNode[] = [
    <TransitionSeries.Sequence key="intro" durationInFrames={frames.intro}>
      <IntroScene theme={props.theme} count={count} bg={bg} />
    </TransitionSeries.Sequence>,
  ];
  props.items.forEach((it, i) => {
    seq.push(
      <TransitionSeries.Transition
        key={`t${i}`}
        presentation={slide({ direction: i % 2 === 0 ? "from-right" : "from-left" })}
        timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
      />,
      <TransitionSeries.Sequence key={`i${i}`} durationInFrames={frames.rounds[i]}>
        <RankScene item={it} bg={bg} logo={props.logos?.[String(it.rank)]} />
      </TransitionSeries.Sequence>,
    );
  });
  seq.push(
    <TransitionSeries.Transition
      key="tv"
      presentation={slide({ direction: "from-right" })}
      timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
    />,
    <TransitionSeries.Sequence key="outro" durationInFrames={frames.verdict}>
      <OutroScene items={props.items} cta={props.cta} bg={bg} logos={props.logos} />
    </TransitionSeries.Sequence>,
  );
  return <TransitionSeries>{seq}</TransitionSeries>;
};
