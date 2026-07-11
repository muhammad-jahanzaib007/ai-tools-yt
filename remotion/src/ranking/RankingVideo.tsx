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

// Vivid per-rank colour worlds (dull dark navy killed 2026-07-11, owner
// feedback: bright saturated scenes are what stops the swipe).
const WORLDS: Record<
  number,
  { a: string; b: string; accent: string; num: string }
> = {
  5: { a: "#0284C7", b: "#22D3EE", accent: "#BAE6FD", num: "#FFFFFF" },
  4: { a: "#7C3AED", b: "#6366F1", accent: "#DDD6FE", num: "#FFFFFF" },
  3: { a: "#EA580C", b: "#F43F5E", accent: "#FED7AA", num: "#FFFFFF" },
  2: { a: "#DB2777", b: "#A855F7", accent: "#FBCFE8", num: "#FFFFFF" },
  1: { a: "#D97706", b: "#FBBF24", accent: "#FEF3C7", num: "#FFFFFF" },
};
const INTRO_WORLD = { a: "#4338CA", b: "#9333EA" };
const OUTRO_WORLD = { a: "#312E81", b: "#7C3AED" };

const FONT = "DejaVu Sans, sans-serif";

const VividBg: React.FC<{ a: string; b: string }> = ({ a, b }) => {
  const frame = useCurrentFrame();
  const drift = Math.sin(frame / 40) * 60;
  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(160deg, ${a} 0%, ${b} 100%)`,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          width: 1000,
          height: 1000,
          borderRadius: "50%",
          left: -320 + drift,
          top: -260,
          background:
            "radial-gradient(circle, rgba(255,255,255,0.25) 0%, transparent 62%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 1100,
          height: 1100,
          borderRadius: "50%",
          right: -380 - drift,
          bottom: -320,
          background:
            "radial-gradient(circle, rgba(0,0,0,0.22) 0%, transparent 65%)",
        }}
      />
    </AbsoluteFill>
  );
};

// The tool's real homepage in a floating phone-style frame with a slow
// scroll-pan: real product on screen = the attention anchor of each scene.
const ScreenshotCard: React.FC<{ shot: string; accent: string }> = ({
  shot,
  accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const inSpring = spring({ frame: frame - 4, fps, config: { damping: 13 } });
  const float = Math.sin(frame / 26) * 7;
  const pan = interpolate(frame, [10, 190], [0, -140], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        opacity: inSpring,
        transform: `translateY(${(1 - inSpring) * 90 + float}px) rotate(-2deg)`,
        width: 560,
        height: 780,
        borderRadius: 34,
        border: "10px solid rgba(255,255,255,0.95)",
        boxShadow: `0 40px 90px rgba(0,0,0,0.45), 0 0 0 3px ${accent}66`,
        overflow: "hidden",
        backgroundColor: "#FFFFFF",
        position: "relative",
      }}
    >
      <Img
        src={staticFile(`ranking/${shot}`)}
        style={{
          width: "100%",
          transform: `translateY(${pan}px)`,
        }}
      />
    </div>
  );
};

const IntroScene: React.FC<{ theme: string; count: number }> = ({
  theme,
  count,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 10, stiffness: 170 } });
  const up = spring({ frame: frame - 6, fps, config: { damping: 14 } });
  return (
    <AbsoluteFill>
      <VividBg a={INTRO_WORLD.a} b={INTRO_WORLD.b} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          padding: "0 64px",
          flexDirection: "column",
          gap: 44,
        }}
      >
        <div
          style={{
            transform: `scale(${pop}) rotate(-3deg)`,
            backgroundColor: "#FDE047",
            color: "#1E1B4B",
            padding: "24px 62px",
            borderRadius: 28,
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: 96,
            letterSpacing: 3,
            boxShadow: "0 24px 60px rgba(0,0,0,0.35)",
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
            fontSize: 78,
            lineHeight: 1.12,
            textAlign: "center",
            color: "#FFFFFF",
            textShadow: "0 6px 30px rgba(0,0,0,0.5)",
          }}
        >
          {theme}
        </div>
      </AbsoluteFill>
      <ShineSweep at={18} />
      <Grain />
      <Vignette strength={0.25} />
    </AbsoluteFill>
  );
};

const RankScene: React.FC<{
  item: RankItem;
  shot?: string;
  logo?: string;
}> = ({ item, shot, logo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isWinner = item.rank === 1;
  const w = WORLDS[item.rank] ?? WORLDS[5];
  const numIn = spring({ frame, fps, config: { damping: 9, stiffness: 180 } });
  const rowIn = spring({ frame: frame - 8, fps, config: { damping: 13 } });
  const numFloat = Math.sin(frame / 22) * 5;
  return (
    <AbsoluteFill>
      <VividBg a={w.a} b={w.b} />
      {isWinner && (
        <Confetti colors={["#FDE047", "#FFFFFF", "#FB923C", "#A7F3D0"]} count={30} />
      )}
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 34,
          padding: "70px 60px 150px",
        }}
      >
        <div
          style={{
            transform: `scale(${numIn}) translateY(${numFloat}px)`,
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: isWinner ? 230 : 190,
            lineHeight: 1,
            color: w.num,
            textShadow: `0 14px 0 rgba(0,0,0,0.22), 0 0 ${isWinner ? 90 : 40}px rgba(255,255,255,0.55)`,
          }}
        >
          #{item.rank}
        </div>
        {shot ? (
          <ScreenshotCard shot={shot} accent={w.accent} />
        ) : null}
        <div
          style={{
            opacity: rowIn,
            transform: `translateY(${(1 - rowIn) * 70}px)`,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 18,
            maxWidth: 920,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 24,
              backgroundColor: "rgba(255,255,255,0.96)",
              borderRadius: 999,
              padding: "18px 44px",
              boxShadow: "0 18px 50px rgba(0,0,0,0.35)",
            }}
          >
            {logo ? (
              <Img
                src={staticFile(`ranking/${logo}`)}
                style={{ width: 76, height: 76, borderRadius: 18 }}
              />
            ) : null}
            <div
              style={{
                fontFamily: FONT,
                fontWeight: 800,
                fontSize: shot ? 66 : 84,
                color: "#111827",
                whiteSpace: "nowrap",
              }}
            >
              {item.name}
            </div>
            <div
              style={{
                backgroundColor: w.a,
                color: "#FFFFFF",
                borderRadius: 999,
                padding: "10px 26px",
                fontFamily: FONT,
                fontWeight: 800,
                fontSize: 30,
                whiteSpace: "nowrap",
              }}
            >
              {item.tag}
            </div>
          </div>
          {!shot ? (
            <div
              style={{
                fontFamily: FONT,
                fontWeight: 800,
                fontSize: 44,
                color: "#FFFFFF",
                textAlign: "center",
                lineHeight: 1.28,
                textShadow: "0 4px 20px rgba(0,0,0,0.45)",
              }}
            >
              {item.reason}
            </div>
          ) : null}
        </div>
      </AbsoluteFill>
      <ShineSweep at={26} />
      <Grain />
      <Vignette strength={0.22} />
    </AbsoluteFill>
  );
};

const OutroScene: React.FC<{
  items: RankItem[];
  cta: string;
  logos?: Record<string, string>;
}> = ({ items, cta, logos }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const byRank = [...items].sort((a, b) => a.rank - b.rank);
  return (
    <AbsoluteFill>
      <VividBg a={OUTRO_WORLD.a} b={OUTRO_WORLD.b} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 20,
          padding: "0 80px",
        }}
      >
        {byRank.map((it, i) => {
          const rowIn = spring({
            frame: frame - i * 5,
            fps,
            config: { damping: 13 },
          });
          const wld = WORLDS[it.rank] ?? WORLDS[5];
          const top = it.rank === 1;
          return (
            <div
              key={it.rank}
              style={{
                opacity: rowIn,
                transform: `translateX(${(1 - rowIn) * 90}px)`,
                backgroundColor: top ? "#FDE047" : "rgba(255,255,255,0.94)",
                borderRadius: 24,
                width: "100%",
                maxWidth: 880,
                padding: top ? "26px 38px" : "17px 38px",
                display: "flex",
                alignItems: "center",
                gap: 26,
                boxShadow: "0 14px 40px rgba(0,0,0,0.3)",
              }}
            >
              <div
                style={{
                  fontFamily: FONT,
                  fontWeight: 800,
                  fontSize: top ? 58 : 42,
                  color: wld.a,
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
                  color: "#111827",
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
            textAlign: "center",
            textShadow: "0 4px 20px rgba(0,0,0,0.5)",
          }}
        >
          {cta}
        </div>
      </AbsoluteFill>
      <ShineSweep at={30} />
      <Grain />
      <Vignette strength={0.22} />
    </AbsoluteFill>
  );
};

export const RankingVideo: React.FC<RankingProps> = (props) => {
  const frames = framesOfRanking(props);
  const seq: React.ReactNode[] = [
    <TransitionSeries.Sequence key="intro" durationInFrames={frames.intro}>
      <IntroScene theme={props.theme} count={props.items.length} />
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
      <OutroScene items={props.items} cta={props.cta} logos={props.logos} />
    </TransitionSeries.Sequence>,
  );
  return <TransitionSeries>{seq}</TransitionSeries>;
};
