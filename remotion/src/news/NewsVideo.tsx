import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { TRANSITION_FRAMES } from "../battle/types";
import { fontFamily } from "../battle/font";
import { Grain, ShineSweep, SparkBurst, Vignette, glass } from "../battle/fx";

export type NewsStory = {
  title: string;      // short display headline, <=10 words
  source: string;     // outlet spoken/shown, e.g. "TechCrunch"
  category: string;   // chips | models | apps | money | policy | research
  detail: string;     // one display line of context, <=14 words
};

export type NewsProps = {
  dateLabel: string;  // e.g. "5 July 2026"
  headline: string;   // intro teaser, the day's biggest angle
  stories: NewsStory[];
  outro: string;      // CTA display line
  sceneFrames?: { intro: number; rounds: number[]; verdict: number };
};

const MIN_SCENE = 2 * TRANSITION_FRAMES + 5;
const pop = Easing.bezier(0.34, 1.56, 0.64, 1);
const ease = Easing.bezier(0.16, 1, 0.3, 1);

export const CATEGORY_META: Record<string, { color: string; label: string }> = {
  chips: { color: "#FB923C", label: "Chips & Compute" },
  models: { color: "#60A5FA", label: "Models" },
  apps: { color: "#2DD4BF", label: "Apps & Adoption" },
  money: { color: "#4ADE80", label: "Money" },
  policy: { color: "#F87171", label: "Policy" },
  research: { color: "#C084FC", label: "Research" },
};

const catMeta = (c: string) => CATEGORY_META[c] ?? CATEGORY_META.apps;

export const framesOfNews = (p: NewsProps) => {
  const f =
    p.sceneFrames && p.sceneFrames.rounds.length === p.stories.length
      ? p.sceneFrames
      : { intro: 150, rounds: p.stories.map(() => 240), verdict: 200 };
  return {
    intro: Math.max(MIN_SCENE, f.intro),
    rounds: f.rounds.map((r) => Math.max(MIN_SCENE, r)),
    verdict: Math.max(MIN_SCENE, f.verdict),
  };
};

export const totalNewsFrames = (p: NewsProps) => {
  const f = framesOfNews(p);
  return (
    f.intro +
    f.rounds.reduce((a, b) => a + b, 0) +
    f.verdict -
    (p.stories.length + 1) * TRANSITION_FRAMES
  );
};

// Slow-drifting colour blobs on near-black: newsroom-dark, not gloomy.
const NewsBg: React.FC<{ accent?: string }> = ({ accent = "#38BDF8" }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: "#070A12", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          width: 1300,
          height: 1300,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accent}2E, transparent 62%)`,
          left: -420 + Math.sin(frame / 95) * 60,
          top: -320 + Math.cos(frame / 110) * 50,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 1100,
          height: 1100,
          borderRadius: "50%",
          background: "radial-gradient(circle, #E1306C1F, transparent 60%)",
          right: -380 - Math.sin(frame / 120) * 50,
          bottom: -300 + Math.sin(frame / 100) * 60,
        }}
      />
      {/* faint grid, drifting: control-room feel */}
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(148,163,184,0.06) 1px, transparent 1px)," +
            "linear-gradient(90deg, rgba(148,163,184,0.06) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
          backgroundPosition: `${frame * 0.15}px 0px`,
        }}
      />
    </AbsoluteFill>
  );
};

// Bottom breaking-news ticker scrolling the day's headlines.
const Ticker: React.FC<{ items: string[] }> = ({ items }) => {
  const frame = useCurrentFrame();
  const line = items.map((t) => t.toUpperCase()).join("   •   ");
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        height: 92,
        display: "flex",
        alignItems: "center",
        overflow: "hidden",
        backgroundColor: "rgba(7,10,18,0.88)",
        borderTop: "1px solid rgba(148,163,184,0.25)",
      }}
    >
      <div
        style={{
          fontFamily,
          fontWeight: 700,
          fontSize: 34,
          color: "#93C5FD",
          whiteSpace: "nowrap",
          translate: `${-frame * 3.2}px 0px`,
          paddingLeft: 1080,
        }}
      >
        {line} • {line}
      </div>
    </div>
  );
};

const IntroScene: React.FC<{
  dateLabel: string;
  headline: string;
  stories: NewsStory[];
}> = ({ dateLabel, headline, stories }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const stampAt = 0.35 * fps;
  const stamp = interpolate(frame, [stampAt, stampAt + 0.3 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  const cardIn = interpolate(frame, [0.9 * fps, 1.35 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const brandIn = interpolate(frame, [0, 0.3 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill>
      <NewsBg />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 34, paddingBottom: 80 }}>
        <div
          style={{
            ...glass("rgba(56,189,248,0.16)", 20),
            opacity: brandIn,
            fontFamily,
            fontWeight: 800,
            fontSize: 38,
            letterSpacing: "0.32em",
            color: "#7DD3FC",
            padding: "12px 34px",
            borderRadius: 999,
            textTransform: "uppercase",
          }}
        >
          Snackbyte AI
        </div>
        <div style={{ position: "relative", textAlign: "center" }}>
          <div
            style={{
              scale: String(stamp),
              fontFamily,
              fontWeight: 900,
              fontSize: 172,
              lineHeight: 0.98,
              color: "#F8FAFC",
              textShadow: "0 0 90px rgba(56,189,248,0.45)",
              textTransform: "uppercase",
              letterSpacing: "-0.02em",
            }}
          >
            AI News
          </div>
          <div
            style={{
              scale: String(stamp),
              fontFamily,
              fontWeight: 900,
              fontSize: 96,
              background: "linear-gradient(110deg, #38BDF8, #818CF8, #E879F9)",
              backgroundClip: "text",
              WebkitBackgroundClip: "text",
              color: "transparent",
              textTransform: "uppercase",
              letterSpacing: "0.14em",
              marginTop: 6,
            }}
          >
            Today
          </div>
          <ShineSweep at={0.7 * fps} duration={24} />
        </div>
        <div
          style={{
            opacity: stamp,
            fontFamily,
            fontWeight: 700,
            fontSize: 40,
            color: "#CBD5E1",
            border: "1px solid rgba(148,163,184,0.35)",
            padding: "10px 30px",
            borderRadius: 999,
          }}
        >
          {dateLabel}
        </div>
        <div
          style={{
            ...glass("rgba(15,23,42,0.72)", 26),
            opacity: cardIn,
            translate: `0px ${(1 - cardIn) * 60}px`,
            fontFamily,
            fontWeight: 800,
            fontSize: 52,
            lineHeight: 1.25,
            color: "#F1F5F9",
            padding: "30px 42px",
            borderRadius: 26,
            maxWidth: "86%",
            textAlign: "center",
            borderLeft: "10px solid #F87171",
          }}
        >
          {headline}
        </div>
        <SparkBurst at={stampAt + 2} color="#38BDF8" size={420} count={12} seed="news-intro" />
      </AbsoluteFill>
      <Ticker items={stories.map((s) => s.title)} />
      <Grain opacity={0.06} />
      <Vignette strength={0.5} />
    </AbsoluteFill>
  );
};

const StoryScene: React.FC<{ story: NewsStory; index: number; total: number }> = ({
  story,
  index,
  total,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const meta = catMeta(story.category);
  const headIn = interpolate(frame, [0.35 * fps, 0.75 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const chipIn = interpolate(frame, [0.15 * fps, 0.45 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  const detailIn = interpolate(frame, [0.9 * fps, 1.3 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  return (
    <AbsoluteFill>
      <NewsBg accent={meta.color} />
      {/* giant story number, backdrop */}
      <div
        style={{
          position: "absolute",
          top: 60,
          right: 40,
          fontFamily,
          fontWeight: 900,
          fontSize: 380,
          lineHeight: 1,
          color: `${meta.color}1A`,
        }}
      >
        {String(index + 1).padStart(2, "0")}
      </div>
      <AbsoluteFill style={{ justifyContent: "center", padding: "0 84px", gap: 38 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
          <div
            style={{
              scale: String(chipIn),
              backgroundColor: meta.color,
              color: "#0B1020",
              fontFamily,
              fontWeight: 900,
              fontSize: 38,
              letterSpacing: "0.14em",
              padding: "12px 30px",
              borderRadius: 12,
              textTransform: "uppercase",
            }}
          >
            {meta.label}
          </div>
          <div
            style={{
              opacity: chipIn,
              fontFamily,
              fontWeight: 700,
              fontSize: 36,
              color: "#94A3B8",
            }}
          >
            {index + 1} / {total}
          </div>
        </div>
        <div
          style={{
            opacity: headIn,
            translate: `0px ${(1 - headIn) * 70}px`,
            fontFamily,
            fontWeight: 900,
            fontSize: 88,
            lineHeight: 1.08,
            color: "#F8FAFC",
            letterSpacing: "-0.015em",
            textShadow: `0 0 70px ${meta.color}40`,
          }}
        >
          {story.title}
        </div>
        <div
          style={{
            opacity: detailIn,
            translate: `0px ${(1 - detailIn) * 50}px`,
            ...glass("rgba(15,23,42,0.7)", 24),
            borderLeft: `10px solid ${meta.color}`,
            fontFamily,
            fontWeight: 600,
            fontSize: 48,
            lineHeight: 1.3,
            color: "#E2E8F0",
            padding: "28px 38px",
            borderRadius: 24,
            maxWidth: "94%",
          }}
        >
          {story.detail}
        </div>
        <div
          style={{
            opacity: detailIn,
            display: "flex",
            alignItems: "center",
            gap: 14,
            fontFamily,
            fontWeight: 700,
            fontSize: 36,
            color: "#94A3B8",
          }}
        >
          <span
            style={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              backgroundColor: meta.color,
              display: "inline-block",
            }}
          />
          via {story.source}
        </div>
      </AbsoluteFill>
      <SparkBurst at={0.35 * fps} color={meta.color} size={360} count={10} seed={`story${index}`} />
      <Grain opacity={0.06} />
      <Vignette strength={0.5} />
    </AbsoluteFill>
  );
};

const OutroScene: React.FC<{ stories: NewsStory[]; outro: string; dateLabel: string }> = ({
  stories,
  outro,
  dateLabel,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const titleIn = interpolate(frame, [0.2 * fps, 0.55 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  const ctaAt = 1.1 * fps;
  const cta = interpolate(frame, [ctaAt, ctaAt + 0.4 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  return (
    <AbsoluteFill>
      <NewsBg accent="#818CF8" />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 40 }}>
        <div
          style={{
            scale: String(titleIn),
            fontFamily,
            fontWeight: 900,
            fontSize: 100,
            color: "#F8FAFC",
            textTransform: "uppercase",
            textShadow: "0 0 80px rgba(129,140,248,0.5)",
            textAlign: "center",
          }}
        >
          That's the brief
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, width: "84%" }}>
          {stories.map((s, i) => {
            const rowIn = interpolate(
              frame,
              [0.5 * fps + i * 6, 0.8 * fps + i * 6],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease },
            );
            const meta = catMeta(s.category);
            return (
              <div
                key={i}
                style={{
                  opacity: rowIn,
                  translate: `${(1 - rowIn) * -50}px 0px`,
                  ...glass("rgba(15,23,42,0.66)", 20),
                  display: "flex",
                  alignItems: "center",
                  gap: 18,
                  fontFamily,
                  fontWeight: 700,
                  fontSize: 36,
                  color: "#E2E8F0",
                  padding: "16px 26px",
                  borderRadius: 18,
                }}
              >
                <span
                  style={{
                    minWidth: 16,
                    height: 16,
                    borderRadius: "50%",
                    backgroundColor: meta.color,
                    display: "inline-block",
                  }}
                />
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {s.title}
                </span>
              </div>
            );
          })}
        </div>
        <div
          style={{
            ...glass("rgba(56,189,248,0.9)", 22),
            opacity: cta,
            scale: String(0.9 + cta * 0.1),
            fontFamily,
            fontWeight: 800,
            fontSize: 46,
            color: "#06121F",
            padding: "22px 46px",
            borderRadius: 999,
            textAlign: "center",
            maxWidth: "88%",
          }}
        >
          {outro}
        </div>
        <div
          style={{
            opacity: cta,
            fontFamily,
            fontWeight: 700,
            fontSize: 34,
            color: "#94A3B8",
          }}
        >
          Snackbyte AI · Daily AI News · {dateLabel}
        </div>
      </AbsoluteFill>
      <Grain opacity={0.05} />
      <Vignette strength={0.45} />
    </AbsoluteFill>
  );
};

export const NewsVideo: React.FC<NewsProps> = (props) => {
  const { dateLabel, headline, stories, outro } = props;
  const frames = framesOfNews(props);
  const items: React.ReactNode[] = [
    <TransitionSeries.Sequence key="intro" durationInFrames={frames.intro}>
      <IntroScene dateLabel={dateLabel} headline={headline} stories={stories} />
    </TransitionSeries.Sequence>,
  ];
  stories.forEach((story, i) => {
    items.push(
      <TransitionSeries.Transition
        key={`t${i}`}
        presentation={slide({ direction: i % 2 === 0 ? "from-right" : "from-left" })}
        timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
      />,
      <TransitionSeries.Sequence key={`s${i}`} durationInFrames={frames.rounds[i]}>
        <StoryScene story={story} index={i} total={stories.length} />
      </TransitionSeries.Sequence>,
    );
  });
  items.push(
    <TransitionSeries.Transition
      key="to"
      presentation={fade()}
      timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
    />,
    <TransitionSeries.Sequence key="outro" durationInFrames={frames.verdict}>
      <OutroScene stories={stories} outro={outro} dateLabel={dateLabel} />
    </TransitionSeries.Sequence>,
  );
  return <TransitionSeries>{items}</TransitionSeries>;
};
