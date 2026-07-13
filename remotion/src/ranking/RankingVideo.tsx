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
import { Confetti, Grain, ShineSweep, Vignette } from "../battle/fx";

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
  // Staged by render_video.py into public/ranking/ (all optional):
  // shots[rank] = the tool's real homepage screenshot, logos[rank] = favicon.
  shots?: Record<string, string>;
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

// VISUAL DIRECTION (rebuilt 2026-07-13 after owner rejected the 5 per-rank
// rainbow "worlds" of v3 as not eye-catching + screenshots always cropped).
// A cohesive dark "tech editorial" look: near-black base, ONE saturated brand
// accent for the whole video (picked per video from the theme, so it varies
// video-to-video but is consistent within one), a giant ghost rank numeral as
// a design element, and the real product screenshot shown WHOLE (contain, no
// scroll-pan crop). Consistency reads premium; one bold accent > five clashing
// gradients.
const BASE = "#0A0A12";
const ACCENTS = [
  "#22D3EE", // cyan
  "#A855F7", // violet
  "#FB7185", // rose
  "#FBBF24", // amber
  "#34D399", // emerald
  "#60A5FA", // blue
  "#F472B6", // pink
  "#F97316", // orange
];

const pickAccent = (seed: string) => {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return ACCENTS[Math.abs(h) % ACCENTS.length];
};

const FONT = "DejaVu Sans, sans-serif";

// Dark base with a soft accent glow that drifts — subtle life without the
// rainbow. Same background for every scene = a single visual identity.
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

// Giant outlined rank numeral sitting behind the content as a design element.
const GhostNumber: React.FC<{ rank: number; accent: string }> = ({
  rank,
  accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const inn = spring({ frame, fps, config: { damping: 12, stiffness: 120 } });
  const float = Math.sin(frame / 30) * 10;
  return (
    <AbsoluteFill
      style={{ justifyContent: "center", alignItems: "center" }}
    >
      <div
        style={{
          fontFamily: FONT,
          fontWeight: 800,
          fontSize: 1180,
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

// The tool's real homepage shown WHOLE — object-fit:contain in a frame whose
// aspect matches the 720x1280 capture, so nothing is ever cropped (the v3
// scroll-pan cut the top and bottom off every shot — owner report).
const ScreenshotCard: React.FC<{ shot: string; accent: string }> = ({
  shot,
  accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const inSpring = spring({ frame: frame - 4, fps, config: { damping: 14 } });
  const float = Math.sin(frame / 28) * 6;
  return (
    <div
      style={{
        opacity: inSpring,
        transform: `translateY(${(1 - inSpring) * 70 + float}px)`,
        width: 636,
        height: 1120, // 636x1120 ~= the 720x1280 shot's 9:16 aspect
        borderRadius: 30,
        padding: 10,
        border: `3px solid ${accent}`,
        boxShadow: `0 30px 80px rgba(0,0,0,0.55), 0 0 60px ${accent}55`,
        backgroundColor: "#0F1117",
        overflow: "hidden",
      }}
    >
      <Img
        src={staticFile(`ranking/${shot}`)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain", // whole page visible, never cropped
          borderRadius: 22,
        }}
      />
    </div>
  );
};

const NamePill: React.FC<{
  item: RankItem;
  accent: string;
  logo?: string;
  big?: boolean;
}> = ({ item, accent, logo, big }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: 22,
      backgroundColor: "rgba(255,255,255,0.97)",
      borderRadius: 999,
      padding: big ? "20px 46px" : "16px 40px",
      boxShadow: "0 16px 44px rgba(0,0,0,0.45)",
    }}
  >
    {logo ? (
      <Img
        src={staticFile(`ranking/${logo}`)}
        style={{ width: 70, height: 70, borderRadius: 16 }}
      />
    ) : null}
    <div
      style={{
        fontFamily: FONT,
        fontWeight: 800,
        fontSize: big ? 80 : 62,
        color: "#0A0A12",
        whiteSpace: "nowrap",
      }}
    >
      {item.name}
    </div>
    <div
      style={{
        backgroundColor: accent,
        color: "#0A0A12",
        borderRadius: 999,
        padding: "9px 24px",
        fontFamily: FONT,
        fontWeight: 800,
        fontSize: 30,
        whiteSpace: "nowrap",
      }}
    >
      {item.tag}
    </div>
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
        transform: `scale(${pop})`,
        fontFamily: FONT,
        fontWeight: 800,
        fontSize: winner ? 96 : 78,
        lineHeight: 1,
        color: winner ? "#0A0A12" : "#FFFFFF",
        backgroundColor: winner ? accent : "transparent",
        border: winner ? "none" : `4px solid ${accent}`,
        borderRadius: 22,
        padding: winner ? "8px 30px" : "6px 26px",
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
            transform: `scale(${pop})`,
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
            transform: `translateY(${(1 - up) * 60}px)`,
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
  accent: string;
  shot?: string;
  logo?: string;
}> = ({ item, accent, shot, logo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isWinner = item.rank === 1;
  const rowIn = spring({ frame: frame - 6, fps, config: { damping: 13 } });
  return (
    <AbsoluteFill>
      <StageBg accent={accent} strong={isWinner} />
      <GhostNumber rank={item.rank} accent={accent} />
      {isWinner && (
        <Confetti
          colors={[accent, "#FFFFFF", accent, "#FDE047"]}
          count={30}
        />
      )}
      <AbsoluteFill
        style={{
          justifyContent: shot ? "flex-start" : "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 28,
          padding: shot ? "70px 60px 120px" : "0 70px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 26,
          }}
        >
          <RankBadge rank={item.rank} accent={accent} winner={isWinner} />
          <NamePill item={item} accent={accent} logo={logo} big={!shot} />
        </div>
        {shot ? (
          <ScreenshotCard shot={shot} accent={accent} />
        ) : (
          <div
            style={{
              opacity: rowIn,
              transform: `translateY(${(1 - rowIn) * 60}px)`,
              maxWidth: 900,
              fontFamily: FONT,
              fontWeight: 800,
              fontSize: 52,
              color: "#FFFFFF",
              textAlign: "center",
              lineHeight: 1.3,
              textShadow: "0 4px 22px rgba(0,0,0,0.6)",
            }}
          >
            {item.reason}
          </div>
        )}
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
                transform: `translateX(${(1 - rowIn) * 90}px)`,
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
  const seq: React.ReactNode[] = [
    <TransitionSeries.Sequence key="intro" durationInFrames={frames.intro}>
      <IntroScene
        theme={props.theme}
        count={props.items.length}
        accent={accent}
      />
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
          accent={accent}
          shot={props.shots?.[String(it.rank)]}
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
