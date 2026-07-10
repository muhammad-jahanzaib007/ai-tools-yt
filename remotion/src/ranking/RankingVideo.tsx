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
import { COLORS, FPS, TRANSITION_FRAMES } from "../battle/types";
import { Confetti, Grain, ShineSweep, Vignette, glass } from "../battle/fx";

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
  // bgs[i] = Pexels photo behind scene i (intro, items..., outro),
  // logos[rank] = tool favicon shown on that rank's card.
  bgs?: (string | null)[];
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

// Rank accent: gold for #1, silver #2, bronze #3, teal the rest.
const rankColor = (rank: number) =>
  rank === 1 ? "#F5C542" : rank === 2 ? "#C9CDD6" : rank === 3 ? "#D08A4E" : COLORS.teal;

const Bg: React.FC<{ hue?: string }> = ({ hue = COLORS.teal }) => {
  const frame = useCurrentFrame();
  const drift = Math.sin(frame / 55) * 40;
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          width: 900,
          height: 900,
          borderRadius: "50%",
          left: -280 + drift,
          top: -220,
          background: `radial-gradient(circle, ${hue}44 0%, transparent 65%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 1000,
          height: 1000,
          borderRadius: "50%",
          right: -350 - drift,
          bottom: -300,
          background: `radial-gradient(circle, ${COLORS.coral}3a 0%, transparent 65%)`,
        }}
      />
    </AbsoluteFill>
  );
};

// Photo background with a slow Ken Burns zoom + dark overlay for text
// legibility. No photo staged -> the gradient Bg carries the scene.
const SceneBg: React.FC<{ photo?: string | null; hue?: string }> = ({ photo, hue }) => {
  const frame = useCurrentFrame();
  if (!photo) {
    return <Bg hue={hue} />;
  }
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, overflow: "hidden" }}>
      <Img
        src={staticFile(`ranking/${photo}`)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${1.08 + frame * 0.0006})`,
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(11,11,20,0.78) 0%, rgba(11,11,20,0.58) 45%, rgba(11,11,20,0.85) 100%)",
        }}
      />
      {hue ? (
        <AbsoluteFill
          style={{
            background: `radial-gradient(circle at 50% 32%, ${hue}30 0%, transparent 60%)`,
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};

const IntroScene: React.FC<{ theme: string; count: number; photo?: string | null }> = ({ theme, count, photo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 11, stiffness: 160 } });
  const up = spring({ frame: frame - 6, fps, config: { damping: 14 } });
  return (
    <AbsoluteFill>
      <SceneBg photo={photo} hue={COLORS.teal} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          padding: "0 70px",
          flexDirection: "column",
          gap: 46,
        }}
      >
        <div
          style={{
            transform: `scale(${pop})`,
            ...glass(`${COLORS.coral}30`),
            padding: "26px 66px",
            borderRadius: 32,
            fontFamily: "DejaVu Sans, sans-serif",
            fontWeight: 800,
            fontSize: 92,
            color: COLORS.white,
            letterSpacing: 4,
          }}
        >
          TOP {count}
        </div>
        <div
          style={{
            opacity: up,
            transform: `translateY(${(1 - up) * 60}px)`,
            fontFamily: "DejaVu Sans, sans-serif",
            fontWeight: 800,
            fontSize: 74,
            lineHeight: 1.15,
            textAlign: "center",
            color: COLORS.cream,
            textShadow: "0 4px 30px rgba(0,0,0,0.55)",
          }}
        >
          {theme}
        </div>
      </AbsoluteFill>
      <ShineSweep at={20} />
      <Grain />
      <Vignette />
    </AbsoluteFill>
  );
};

const RankScene: React.FC<{ item: RankItem; photo?: string | null; logo?: string }> = ({ item, photo, logo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isWinner = item.rank === 1;
  const accent = rankColor(item.rank);
  const numIn = spring({ frame, fps, config: { damping: 10, stiffness: 170 } });
  const cardIn = spring({ frame: frame - 5, fps, config: { damping: 13 } });
  const glow = isWinner ? 0.5 + Math.sin(frame / 9) * 0.2 : 0;
  return (
    <AbsoluteFill>
      <SceneBg photo={photo} hue={accent} />
      {isWinner && (
        <Confetti colors={["#F5C542", COLORS.coral, COLORS.teal, COLORS.cream]} />
      )}
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 44,
          padding: "0 64px",
        }}
      >
        <div
          style={{
            transform: `scale(${numIn})`,
            fontFamily: "DejaVu Sans, sans-serif",
            fontWeight: 800,
            fontSize: 300,
            lineHeight: 1,
            color: accent,
            textShadow: `0 0 ${60 + glow * 80}px ${accent}${isWinner ? "cc" : "55"}`,
          }}
        >
          {isWinner ? "#1" : `#${item.rank}`}
        </div>
        <div
          style={{
            opacity: cardIn,
            transform: `translateY(${(1 - cardIn) * 70}px)`,
            ...glass(`${accent}26`),
            borderRadius: 36,
            padding: "44px 54px",
            maxWidth: 900,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 24,
          }}
        >
          {logo ? (
            <Img
              src={staticFile(`ranking/${logo}`)}
              style={{
                width: 108,
                height: 108,
                borderRadius: 26,
                boxShadow: "0 10px 34px rgba(0,0,0,0.45)",
                backgroundColor: "rgba(255,255,255,0.92)",
                padding: 10,
              }}
            />
          ) : null}
          <div
            style={{
              fontFamily: "DejaVu Sans, sans-serif",
              fontWeight: 800,
              fontSize: 84,
              color: COLORS.white,
              textAlign: "center",
              lineHeight: 1.05,
            }}
          >
            {item.name}
          </div>
          <div
            style={{
              fontFamily: "DejaVu Sans, sans-serif",
              fontSize: 44,
              color: COLORS.cream,
              textAlign: "center",
              lineHeight: 1.3,
            }}
          >
            {item.reason}
          </div>
          <div
            style={{
              ...glass(`${accent}40`, 18),
              borderRadius: 999,
              padding: "12px 34px",
              fontFamily: "DejaVu Sans, sans-serif",
              fontWeight: 800,
              fontSize: 36,
              color: COLORS.white,
              letterSpacing: 1,
            }}
          >
            {item.tag}
          </div>
        </div>
      </AbsoluteFill>
      <ShineSweep at={30} />
      <Grain />
      <Vignette />
    </AbsoluteFill>
  );
};

const OutroScene: React.FC<{ items: RankItem[]; cta: string; photo?: string | null; logos?: Record<string, string> }> = ({ items, cta, photo, logos }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const byRank = [...items].sort((a, b) => a.rank - b.rank);
  return (
    <AbsoluteFill>
      <SceneBg photo={photo} hue={"#F5C542"} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 22,
          padding: "0 80px",
        }}
      >
        {byRank.map((it, i) => {
          const rowIn = spring({
            frame: frame - i * 5,
            fps,
            config: { damping: 13 },
          });
          const accent = rankColor(it.rank);
          return (
            <div
              key={it.rank}
              style={{
                opacity: rowIn,
                transform: `translateX(${(1 - rowIn) * 90}px)`,
                ...glass(it.rank === 1 ? `${accent}33` : "rgba(255,255,255,0.06)"),
                borderRadius: 26,
                width: "100%",
                maxWidth: 880,
                padding: it.rank === 1 ? "26px 40px" : "18px 40px",
                display: "flex",
                alignItems: "center",
                gap: 30,
              }}
            >
              <div
                style={{
                  fontFamily: "DejaVu Sans, sans-serif",
                  fontWeight: 800,
                  fontSize: it.rank === 1 ? 62 : 46,
                  color: accent,
                  width: 96,
                }}
              >
                #{it.rank}
              </div>
              {logos && logos[String(it.rank)] ? (
                <Img
                  src={staticFile(`ranking/${logos[String(it.rank)]}`)}
                  style={{
                    width: it.rank === 1 ? 64 : 50,
                    height: it.rank === 1 ? 64 : 50,
                    borderRadius: 14,
                    backgroundColor: "rgba(255,255,255,0.92)",
                    padding: 5,
                  }}
                />
              ) : null}
              <div
                style={{
                  fontFamily: "DejaVu Sans, sans-serif",
                  fontWeight: 800,
                  fontSize: it.rank === 1 ? 58 : 44,
                  color: COLORS.white,
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
            fontFamily: "DejaVu Sans, sans-serif",
            fontWeight: 800,
            fontSize: 46,
            color: COLORS.cream,
            textAlign: "center",
          }}
        >
          {cta}
        </div>
      </AbsoluteFill>
      <ShineSweep at={24} />
      <Grain />
      <Vignette />
    </AbsoluteFill>
  );
};

export const RankingVideo: React.FC<RankingProps> = (props) => {
  const frames = framesOfRanking(props);
  const seq: React.ReactNode[] = [
    <TransitionSeries.Sequence key="intro" durationInFrames={frames.intro}>
      <IntroScene theme={props.theme} count={props.items.length} photo={props.bgs?.[0]} />
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
        <RankScene item={it} photo={props.bgs?.[i + 1]} logo={props.logos?.[String(it.rank)]} />
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
        photo={props.bgs ? props.bgs[props.bgs.length - 1] : undefined}
        logos={props.logos}
      />
    </TransitionSeries.Sequence>,
  );
  return <TransitionSeries>{seq}</TransitionSeries>;
};
