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
import { Confetti, Grain, ShineSweep, SparkBurst, Vignette } from "../battle/fx";

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
  // Staged by render_video.py into public/ranking/ (optional): favicon per rank.
  logos?: Record<string, string>;
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

// VISUAL DIRECTION (rebuilt 2026-07-14 — owner: "don't add app previews,
// replan the ranking format"). A pure TYPOGRAPHIC countdown, no screenshots:
// each rank scene has one focal point (the tool name), a giant ghost numeral
// as the backdrop, a favicon-or-monogram brand cue, one tag chip, the reason
// as the hook, and a top countdown rail for game-show momentum. One cohesive
// accent per video (hashed from the theme). Follows the video-layout rule:
// one message per scene, big text, reveal over time — not a dashboard of cards.
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

const FONT = "DejaVu Sans, sans-serif";

const StageBg: React.FC<{ accent: string; strong?: boolean }> = ({
  accent,
  strong,
}) => {
  const frame = useCurrentFrame();
  const drift = Math.sin(frame / 44) * 70;
  return (
    <AbsoluteFill style={{ backgroundColor: BASE, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          width: 1300,
          height: 1300,
          borderRadius: "50%",
          left: -260 + drift,
          top: -360,
          background: `radial-gradient(circle, ${accent}${strong ? "3A" : "26"} 0%, transparent 60%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 1200,
          height: 1200,
          borderRadius: "50%",
          right: -300 - drift,
          bottom: -380,
          background: `radial-gradient(circle, ${accent}20 0%, transparent 62%)`,
        }}
      />
    </AbsoluteFill>
  );
};

// Giant outlined rank numeral behind the content — the scene's backdrop shape,
// distinct for every rank so the five scenes never read as identical cards.
const GhostNumber: React.FC<{ rank: number; accent: string }> = ({
  rank,
  accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const inn = spring({ frame, fps, config: { damping: 12, stiffness: 120 } });
  const float = Math.sin(frame / 30) * 10;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          fontFamily: FONT,
          fontWeight: 800,
          fontSize: 1240,
          lineHeight: 1,
          color: "transparent",
          WebkitTextStroke: `4px ${accent}`,
          opacity: 0.16 * inn,
          transform: `translateY(${(1 - inn) * 60 + float}px)`,
        }}
      >
        {rank}
      </div>
    </AbsoluteFill>
  );
};

// Countdown progress rail at the top: one segment per rank, lit up to the
// current position — a subtle "we're on 3 of 5" momentum cue.
const CountdownRail: React.FC<{
  rank: number;
  count: number;
  accent: string;
}> = ({ rank, count, accent }) => {
  const done = count - rank; // rank 5 -> 0 lit before it, rank 1 -> 4
  return (
    <div
      style={{
        position: "absolute",
        top: 96,
        left: 0,
        right: 0,
        display: "flex",
        gap: 16,
        justifyContent: "center",
      }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          style={{
            width: 116,
            height: 12,
            borderRadius: 6,
            backgroundColor: i <= done ? accent : "rgba(255,255,255,0.16)",
            boxShadow: i <= done ? `0 0 18px ${accent}77` : "none",
          }}
        />
      ))}
    </div>
  );
};

// Favicon when we have one, otherwise a letter monogram — so every tool always
// has a brand mark (favicons fail for some domains).
const ToolIcon: React.FC<{
  logo?: string;
  name: string;
  accent: string;
  size: number;
}> = ({ logo, name, accent, size }) =>
  logo ? (
    <Img
      src={staticFile(`ranking/${logo}`)}
      style={{ width: size, height: size, borderRadius: size * 0.24, flexShrink: 0 }}
    />
  ) : (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.24,
        backgroundColor: accent,
        color: "#0A0A12",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: FONT,
        fontWeight: 800,
        fontSize: size * 0.5,
        flexShrink: 0,
      }}
    >
      {(name || "?").slice(0, 1).toUpperCase()}
    </div>
  );

const RankBadge: React.FC<{ rank: number; accent: string; winner: boolean }> = ({
  rank,
  accent,
  winner,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 9, stiffness: 190 } });
  return (
    <div
      style={{
        scale: String(pop),
        fontFamily: FONT,
        fontWeight: 800,
        fontSize: winner ? 88 : 72,
        lineHeight: 1,
        color: winner ? "#0A0A12" : "#FFFFFF",
        backgroundColor: winner ? accent : "transparent",
        border: winner ? "none" : `4px solid ${accent}`,
        borderRadius: 20,
        padding: winner ? "6px 28px" : "4px 24px",
        textShadow: winner ? "none" : `0 0 30px ${accent}88`,
      }}
    >
      #{rank}
    </div>
  );
};

const IntroScene: React.FC<{
  theme: string;
  count: number;
  accent: string;
}> = ({ theme, count, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 10, stiffness: 170 } });
  const up = spring({ frame: frame - 6, fps, config: { damping: 14 } });
  return (
    <AbsoluteFill>
      <StageBg accent={accent} strong />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          padding: "0 70px",
          flexDirection: "column",
          gap: 48,
        }}
      >
        <div
          style={{
            scale: String(pop),
            backgroundColor: accent,
            color: "#0A0A12",
            padding: "22px 66px",
            borderRadius: 26,
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: 104,
            letterSpacing: 4,
            boxShadow: `0 24px 60px rgba(0,0,0,0.5), 0 0 70px ${accent}66`,
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
            fontSize: 82,
            lineHeight: 1.14,
            textAlign: "center",
            color: "#FFFFFF",
            textShadow: "0 6px 30px rgba(0,0,0,0.6)",
          }}
        >
          {theme}
        </div>
      </AbsoluteFill>
      <ShineSweep at={18} />
      <Grain />
      <Vignette strength={0.4} />
    </AbsoluteFill>
  );
};

const RankScene: React.FC<{
  item: RankItem;
  count: number;
  accent: string;
  logo?: string;
}> = ({ item, count, accent, logo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isWinner = item.rank === 1;
  const nameIn = spring({ frame, fps, config: { damping: 11, stiffness: 150 } });
  const chipIn = spring({ frame: frame - 8, fps, config: { damping: 14 } });
  const reasonIn = spring({ frame: frame - 14, fps, config: { damping: 14 } });
  const nameSize = Math.max(
    58,
    Math.min(112, Math.floor(880 / Math.max(6, item.name.length))),
  );
  return (
    <AbsoluteFill>
      <StageBg accent={accent} strong={isWinner} />
      <GhostNumber rank={item.rank} accent={accent} />
      <CountdownRail rank={item.rank} count={count} accent={accent} />
      {isWinner && (
        <Confetti colors={[accent, "#FFFFFF", accent, "#FDE047"]} count={30} />
      )}
      <SparkBurst at={2} color={accent} size={300} count={12} seed={`r${item.rank}`} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 40,
          padding: "150px 70px 120px",
        }}
      >
        <RankBadge rank={item.rank} accent={accent} winner={isWinner} />
        {/* focal row: brand mark + huge tool name */}
        <div
          style={{
            scale: String(nameIn),
            display: "flex",
            alignItems: "center",
            gap: 30,
            maxWidth: 960,
          }}
        >
          <ToolIcon logo={logo} name={item.name} accent={accent} size={isWinner ? 108 : 92} />
          <div
            style={{
              fontFamily: FONT,
              fontWeight: 800,
              fontSize: nameSize,
              lineHeight: 1.02,
              color: "#FFFFFF",
              textShadow: `0 6px 34px rgba(0,0,0,0.6), 0 0 50px ${accent}44`,
            }}
          >
            {item.name}
          </div>
        </div>
        <div
          style={{
            opacity: chipIn,
            scale: String(chipIn),
            backgroundColor: accent,
            color: "#0A0A12",
            borderRadius: 999,
            padding: "12px 38px",
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: 40,
          }}
        >
          {item.tag}
        </div>
        <div
          style={{
            opacity: reasonIn,
            translate: `0 ${(1 - reasonIn) * 50}px`,
            maxWidth: 900,
            fontFamily: FONT,
            fontWeight: 700,
            fontSize: 52,
            color: "#FFFFFF",
            textAlign: "center",
            lineHeight: 1.28,
            textShadow: "0 4px 22px rgba(0,0,0,0.6)",
          }}
        >
          {item.reason}
        </div>
      </AbsoluteFill>
      <ShineSweep at={24} />
      <Grain />
      <Vignette strength={0.34} />
    </AbsoluteFill>
  );
};

const OutroScene: React.FC<{
  items: RankItem[];
  cta: string;
  accent: string;
  logos?: Record<string, string>;
}> = ({ items, cta, accent, logos }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const byRank = [...items].sort((a, b) => a.rank - b.rank);
  return (
    <AbsoluteFill>
      <StageBg accent={accent} strong />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 18,
          padding: "0 80px",
        }}
      >
        {byRank.map((it, i) => {
          const rowIn = spring({
            frame: frame - i * 5,
            fps,
            config: { damping: 13 },
          });
          const top = it.rank === 1;
          return (
            <div
              key={it.rank}
              style={{
                opacity: rowIn,
                translate: `${(1 - rowIn) * 90}px 0`,
                backgroundColor: top ? accent : "rgba(255,255,255,0.08)",
                border: top ? "none" : "1px solid rgba(255,255,255,0.16)",
                borderRadius: 22,
                width: "100%",
                maxWidth: 880,
                padding: top ? "24px 38px" : "16px 38px",
                display: "flex",
                alignItems: "center",
                gap: 26,
                boxShadow: top ? `0 16px 44px ${accent}55` : "none",
              }}
            >
              <div
                style={{
                  fontFamily: FONT,
                  fontWeight: 800,
                  fontSize: top ? 58 : 42,
                  color: top ? "#0A0A12" : accent,
                  width: 92,
                }}
              >
                #{it.rank}
              </div>
              {logos && logos[String(it.rank)] ? (
                <Img
                  src={staticFile(`ranking/${logos[String(it.rank)]}`)}
                  style={{
                    width: top ? 62 : 48,
                    height: top ? 62 : 48,
                    borderRadius: 12,
                  }}
                />
              ) : null}
              <div
                style={{
                  fontFamily: FONT,
                  fontWeight: 800,
                  fontSize: top ? 56 : 42,
                  color: top ? "#0A0A12" : "#FFFFFF",
                }}
              >
                {it.name}
              </div>
            </div>
          );
        })}
        <div
          style={{
            marginTop: 26,
            opacity: interpolate(frame, [26, 44], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: 46,
            color: accent,
            textAlign: "center",
            textShadow: "0 4px 20px rgba(0,0,0,0.6)",
          }}
        >
          {cta}
        </div>
      </AbsoluteFill>
      <ShineSweep at={30} />
      <Grain />
      <Vignette strength={0.34} />
    </AbsoluteFill>
  );
};

export const RankingVideo: React.FC<RankingProps> = (props) => {
  const frames = framesOfRanking(props);
  const accent = pickAccent(props.theme || "snackbyte");
  const count = props.items.length;
  const seq: React.ReactNode[] = [
    <TransitionSeries.Sequence key="intro" durationInFrames={frames.intro}>
      <IntroScene theme={props.theme} count={count} accent={accent} />
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
        <RankScene
          item={it}
          count={count}
          accent={accent}
          logo={props.logos?.[String(it.rank)]}
        />
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
      <OutroScene
        items={props.items}
        cta={props.cta}
        accent={accent}
        logos={props.logos}
      />
    </TransitionSeries.Sequence>,
  );
  return <TransitionSeries>{seq}</TransitionSeries>;
};
