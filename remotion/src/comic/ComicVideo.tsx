import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { COLORS, TRANSITION_FRAMES } from "../battle/types";
import { fontFamily } from "../battle/font";
import { Confetti, Grain, SparkBurst, Vignette, glass } from "../battle/fx";
import { Emblem } from "./emblems";

export type ComicHero = {
  tool: string;
  alias: string;
  color: string;
  power: string;
  slug: string;            // art file key: hero-<slug>-idle/action.png
};

export type ComicProps = {
  episodeTitle: string;
  threat: string;
  threatSlug: string;      // art file key: villain-<slug>-menace/defeated.png
  heroes: ComicHero[];
  resolution: string;
  sceneFrames?: { intro: number; rounds: number[]; verdict: number };
};

// A transparent-keyed character PNG placed in public/toolverse/ by the render
// script. Returns null if no slug (keeps the text-only look as a fallback).
const Character: React.FC<{
  file?: string;
  style?: React.CSSProperties;
}> = ({ file, style }) => {
  if (!file) {
    return null;
  }
  return (
    <Img
      src={staticFile(`toolverse/${file}`)}
      style={{ objectFit: "contain", ...style }}
    />
  );
};

const MIN_SCENE = 2 * TRANSITION_FRAMES + 5;
const pop = Easing.bezier(0.34, 1.56, 0.64, 1);
const ease = Easing.bezier(0.16, 1, 0.3, 1);

export const framesOfComic = (p: ComicProps) => {
  const f =
    p.sceneFrames && p.sceneFrames.rounds.length === p.heroes.length
      ? p.sceneFrames
      : { intro: 160, rounds: p.heroes.map(() => 240), verdict: 240 };
  return {
    intro: Math.max(MIN_SCENE, f.intro),
    rounds: f.rounds.map((r) => Math.max(MIN_SCENE, r)),
    verdict: Math.max(MIN_SCENE, f.verdict),
  };
};

export const totalComicFrames = (p: ComicProps) => {
  const f = framesOfComic(p);
  return (
    f.intro +
    f.rounds.reduce((a, b) => a + b, 0) +
    f.verdict -
    (p.heroes.length + 1) * TRANSITION_FRAMES
  );
};

// White impact flash at a beat: sells the hit.
const Flash: React.FC<{ at: number }> = ({ at }) => {
  const frame = useCurrentFrame();
  if (frame < at || frame > at + 7) {
    return null;
  }
  const o = interpolate(frame, [at, at + 7], [0.85, 0]);
  return <AbsoluteFill style={{ backgroundColor: "#FFFFFF", opacity: o, pointerEvents: "none" }} />;
};

// Anime speed lines racing across the frame during action beats.
const SpeedLines: React.FC<{ from: number; duration: number; color?: string }> = ({
  from,
  duration,
  color = "rgba(255,255,255,0.22)",
}) => {
  const frame = useCurrentFrame();
  if (frame < from || frame > from + duration) {
    return null;
  }
  const fade = interpolate(frame, [from, from + 6, from + duration - 6, from + duration], [0, 1, 1, 0]);
  return (
    <AbsoluteFill
      style={{
        opacity: fade,
        background: `repeating-linear-gradient(104deg, transparent 0px, transparent 46px, ${color} 46px, ${color} 52px)`,
        backgroundPositionX: `${-frame * 38}px`,
        pointerEvents: "none",
      }}
    />
  );
};

// Classic comic halftone dot field, drifting slowly.
const Halftone: React.FC<{ tint?: string }> = ({ tint = "rgba(0,0,0,0.3)" }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        backgroundImage: `radial-gradient(circle, ${tint} 1.6px, transparent 1.6px)`,
        backgroundSize: "26px 26px",
        backgroundPosition: `${frame * 0.3}px ${frame * 0.2}px`,
        pointerEvents: "none",
      }}
    />
  );
};

// Manga-style action rays bursting from a focal point.
const ActionRays: React.FC<{ color: string; opacity?: number }> = ({
  color,
  opacity = 0.2,
}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        background: `repeating-conic-gradient(from ${frame * 0.6}deg at 50% 38%, ${color} 0deg 5deg, transparent 5deg 14deg)`,
        opacity,
        pointerEvents: "none",
      }}
    />
  );
};

// Yellow narration caption box, the comic staple.
const CaptionBox: React.FC<{
  children: React.ReactNode;
  at: number;
  rotate?: number;
}> = ({ children, at, rotate = -2 }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  return (
    <div
      style={{
        opacity: p,
        scale: String(0.7 + 0.3 * p),
        rotate: `${rotate}deg`,
        backgroundColor: "#FFE24A",
        color: "#1A1915",
        border: "6px solid #1A1915",
        boxShadow: "10px 10px 0 rgba(0,0,0,0.55)",
        fontFamily,
        fontWeight: 800,
        fontSize: 42,
        padding: "18px 30px",
        maxWidth: "82%",
        textAlign: "center",
      }}
    >
      {children}
    </div>
  );
};

// Starburst badge with impact text (POW! style).
const Burst: React.FC<{
  text: string;
  color: string;
  at: number;
  size?: number;
}> = ({ text, color, at, size = 340 }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  if (frame < at) {
    return null;
  }
  const spikes = 12;
  const pts: string[] = [];
  for (let i = 0; i < spikes * 2; i++) {
    const r = i % 2 === 0 ? 50 : 32;
    const a = (Math.PI * i) / spikes;
    pts.push(`${50 + r * Math.sin(a)},${50 - r * Math.cos(a)}`);
  }
  return (
    <div
      style={{
        position: "absolute",
        width: size,
        height: size,
        scale: String(p),
        rotate: `${-8 + p * 8}deg`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <svg viewBox="0 0 100 100" style={{ position: "absolute", inset: 0 }}>
        <polygon points={pts.join(" ")} fill={color} stroke="#1A1915" strokeWidth={2.5} />
      </svg>
      {text ? (
        <span
          style={{
            position: "relative",
            fontFamily,
            fontWeight: 900,
            fontSize: size * 0.19,
            color: "#1A1915",
            rotate: "-6deg",
          }}
        >
          {text}
        </span>
      ) : null}
    </div>
  );
};

const ThreatScene: React.FC<{ threat: string; threatSlug?: string }> = ({ threat, threatSlug }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const slamAt = 0.5 * fps;
  const slam = interpolate(frame, [slamAt, slamAt + 0.35 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  const shakeAmp = interpolate(frame, [slamAt, slamAt + 0.4 * fps], [16, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelIn = interpolate(frame, [0, 0.35 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const menace = 1 + 0.02 * Math.sin(frame / 5);           // idle pulse after the slam
  return (
    <AbsoluteFill style={{ backgroundColor: "#160A0C", scale: String(1 + frame * 0.0009) }}>
      <ActionRays color="#B3261E" opacity={0.25} />
      <Halftone tint="rgba(255,80,60,0.16)" />
      <SpeedLines from={slamAt} duration={0.9 * fps} color="rgba(255,90,70,0.20)" />
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          gap: 44,
          translate: `${Math.sin(frame * 2.9) * shakeAmp}px ${Math.cos(frame * 3.4) * shakeAmp * 0.6}px`,
        }}
      >
        <div
          style={{
            opacity: labelIn,
            fontFamily,
            fontWeight: 900,
            fontSize: 44,
            letterSpacing: "0.35em",
            color: "#FF6B5E",
            textTransform: "uppercase",
          }}
        >
          A threat appears
        </div>
        <Character
          file={threatSlug ? `villain-${threatSlug}-menace.png` : undefined}
          style={{
            width: "82%",
            height: 900,
            scale: String(slam * menace),
            translate: `0px ${(1 - slam) * -260}px`,
            rotate: `${Math.sin(frame / 7) * 1.4}deg`,
            filter: "drop-shadow(0 0 50px rgba(255,60,50,0.6))",
          }}
        />
        <div
          style={{
            scale: String(slam),
            rotate: `${(1 - slam) * -4 - 2}deg`,
            fontFamily,
            fontWeight: 900,
            fontSize: threatSlug ? 84 : 128,
            lineHeight: 1.02,
            textAlign: "center",
            maxWidth: "92%",
            color: "#FFF3EE",
            textShadow: "0 0 60px rgba(255,80,60,0.55), 6px 6px 0 #7A1410",
            textTransform: "uppercase",
            marginTop: threatSlug ? -40 : 0,
          }}
        >
          {threat}
        </div>
        <SparkBurst at={slamAt + 2} color="#FF6B5E" size={420} count={14} seed="threat" />
        <CaptionBox at={1.1 * fps}>THE TOOLVERSE · TONIGHT'S EPISODE</CaptionBox>
      </AbsoluteFill>
      <Flash at={slamAt} />
      <Grain opacity={0.07} />
      <Vignette strength={0.55} />
    </AbsoluteFill>
  );
};

const HeroScene: React.FC<{ hero: ComicHero; index: number }> = ({ hero, index }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const fromLeft = index % 2 === 0;
  const inAt = 0.35 * fps;
  const actionAt = 1.4 * fps;                 // pose swap: idle -> attack + lunge

  // fly in from the side, settle, then lunge forward on the attack beat
  const arrive = interpolate(frame, [inAt, inAt + 0.45 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  const lunge = interpolate(frame, [actionAt, actionAt + 0.28 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  const startX = fromLeft ? -width : width;
  const x = startX * (1 - arrive) + lunge * (fromLeft ? 70 : -70);
  const attacking = frame >= actionAt;
  const breathe = 1 + 0.02 * Math.sin(frame / 6);
  const bob = Math.sin(frame / 9) * 8;
  const bubbleAt = 0.6 * fps;
  const bubble = interpolate(frame, [bubbleAt, bubbleAt + 0.35 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#0b0b14", scale: String(1 + frame * 0.0009) }}>
      <ActionRays color={hero.color} opacity={0.32} />
      <Halftone tint="rgba(255,255,255,0.10)" />
      <SpeedLines from={actionAt} duration={0.8 * fps} color={`${hero.color}55`} />

      {/* the hero body: flies in, swaps idle -> action pose on the attack beat */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-end" }}>
        <div
          style={{
            position: "relative",
            width: "94%",
            height: 1250,
            translate: `${x}px ${bob}px`,
            scale: String((0.9 + 0.1 * arrive) * (attacking ? 1.04 : breathe)),
          }}
        >
          <Character
            file={hero.slug ? `hero-${hero.slug}-${attacking ? "action" : "idle"}.png` : undefined}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              filter: `drop-shadow(0 0 55px ${hero.color}bb)`,
              transform: fromLeft ? "none" : "scaleX(-1)",
            }}
          />
          {/* emblem crest over the chest */}
          <div style={{ position: "absolute", top: "27%", left: "50%", translate: "-50% 0", opacity: arrive }}>
            <Emblem slug={hero.slug} color={hero.color} size={150} />
          </div>
        </div>
      </AbsoluteFill>

      <Burst text="" color={hero.color} at={actionAt} size={620} />
      <SparkBurst at={actionAt} color={hero.color} size={360} count={12} seed={`h${index}`} />

      {/* nameplate: alias + tool */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: 90 }}>
        <div
          style={{
            opacity: interpolate(frame, [0, 0.3 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
            fontFamily,
            fontWeight: 900,
            fontSize: 40,
            letterSpacing: "0.3em",
            color: hero.color,
            textShadow: "3px 3px 0 #1A1915",
            textTransform: "uppercase",
          }}
        >
          Summoning
        </div>
        <div
          style={{
            scale: String(arrive),
            fontFamily,
            fontWeight: 900,
            fontSize: 104,
            color: "#FFFFFF",
            textShadow: `0 0 70px ${hero.color}, 5px 5px 0 #1A1915`,
            textTransform: "uppercase",
            textAlign: "center",
            maxWidth: "92%",
            marginTop: 6,
          }}
        >
          {hero.alias}
        </div>
        <div
          style={{
            ...glass(`${hero.color}CC`, 22),
            opacity: arrive,
            fontFamily,
            fontWeight: 800,
            fontSize: 44,
            color: COLORS.white,
            padding: "10px 34px",
            borderRadius: 999,
            marginTop: 14,
          }}
        >
          {hero.tool}
        </div>
      </AbsoluteFill>

      {/* speech bubble: the hero's power line */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-end", paddingBottom: 150 }}>
        <div
          style={{
            opacity: bubble,
            scale: String(0.8 + 0.2 * bubble),
            position: "relative",
            backgroundColor: "#FFFFFF",
            color: "#1A1915",
            border: "6px solid #1A1915",
            borderRadius: 34,
            boxShadow: "10px 10px 0 rgba(0,0,0,0.5)",
            fontFamily,
            fontWeight: 800,
            fontSize: 42,
            padding: "22px 36px",
            maxWidth: "82%",
            textAlign: "center",
          }}
        >
          {hero.power}
          <div
            style={{
              position: "absolute",
              bottom: -26,
              left: fromLeft ? "18%" : "72%",
              width: 0,
              height: 0,
              borderLeft: "16px solid transparent",
              borderRight: "16px solid transparent",
              borderTop: "26px solid #1A1915",
            }}
          />
        </div>
      </AbsoluteFill>
      <Flash at={actionAt} />
      <Grain opacity={0.06} />
      <Vignette strength={0.45} />
    </AbsoluteFill>
  );
};

const VictoryScene: React.FC<{ heroes: ComicHero[]; resolution: string; threatSlug?: string }> = ({
  heroes,
  resolution,
  threatSlug,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const stamp = interpolate(frame, [0.3 * fps, 0.7 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: pop,
  });
  // the beaten villain fades and sinks as it crumbles away
  const crumble = interpolate(frame, [0, 0.9 * fps], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const textIn = interpolate(frame, [0.9 * fps, 1.4 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const ctaAt = Math.max(1.8 * fps, Math.min(3 * fps, durationInFrames * 0.35));
  const cta = interpolate(frame, [ctaAt, ctaAt + 0.5 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.cream }}>
      <Halftone tint="rgba(26,25,21,0.08)" />
      <Confetti colors={[COLORS.coral, COLORS.teal, "#FFE24A", COLORS.dark]} />
      {/* the defeated villain crumbling away behind the victory stamp */}
      {threatSlug ? (
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <Character
            file={`villain-${threatSlug}-defeated.png`}
            style={{
              width: "70%",
              height: 820,
              opacity: crumble * 0.5,
              scale: String(0.8 + crumble * 0.2),
              translate: `0px ${(1 - crumble) * 120}px`,
              filter: "grayscale(0.3)",
            }}
          />
        </AbsoluteFill>
      ) : null}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 36 }}>
        <div
          style={{
            scale: String(stamp),
            rotate: "-6deg",
            border: "9px solid #1D8C4C",
            color: "#1D8C4C",
            fontFamily,
            fontWeight: 900,
            fontSize: 56,
            letterSpacing: "0.08em",
            padding: "14px 34px",
            borderRadius: 18,
            textTransform: "uppercase",
            maxWidth: "86%",
            textAlign: "center",
            boxShadow: "8px 8px 0 rgba(29,140,76,0.25)",
          }}
        >
          Threat neutralised
        </div>
        <div style={{ display: "flex", gap: 24, opacity: textIn }}>
          {heroes.map((h) => (
            <div
              key={h.tool}
              style={{
                ...glass(`${h.color}E6`, 20),
                fontFamily,
                fontWeight: 800,
                fontSize: 40,
                color: "#FFFFFF",
                padding: "12px 30px",
                borderRadius: 999,
              }}
            >
              {h.alias} · {h.tool}
            </div>
          ))}
        </div>
        <div
          style={{
            opacity: textIn,
            fontFamily,
            fontWeight: 500,
            fontSize: 46,
            color: COLORS.dark,
            maxWidth: "80%",
            textAlign: "center",
            lineHeight: 1.35,
          }}
        >
          {resolution}
        </div>
        <div
          style={{
            ...glass("rgba(184,74,40,0.97)", 20),
            opacity: cta,
            fontFamily,
            fontWeight: 800,
            fontSize: 42,
            color: "#FFF6EC",
            padding: "20px 42px",
            borderRadius: 999,
          }}
        >
          Which hero next? Comment ↓
        </div>
        <div
          style={{
            opacity: cta,
            fontFamily,
            fontWeight: 700,
            fontSize: 36,
            color: COLORS.dark,
          }}
        >
          Snackbyte AI · The AI Toolverse
        </div>
      </AbsoluteFill>
      <Grain opacity={0.04} />
    </AbsoluteFill>
  );
};

export const ComicVideo: React.FC<ComicProps> = (props) => {
  const { threat, threatSlug, heroes, resolution } = props;
  const frames = framesOfComic(props);
  const items: React.ReactNode[] = [
    <TransitionSeries.Sequence key="intro" durationInFrames={frames.intro}>
      <ThreatScene threat={threat} threatSlug={threatSlug} />
    </TransitionSeries.Sequence>,
  ];
  heroes.forEach((hero, i) => {
    items.push(
      <TransitionSeries.Transition
        key={`t${i}`}
        presentation={slide({ direction: i % 2 === 0 ? "from-right" : "from-left" })}
        timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
      />,
      <TransitionSeries.Sequence key={`h${i}`} durationInFrames={frames.rounds[i]}>
        <HeroScene hero={hero} index={i} />
      </TransitionSeries.Sequence>,
    );
  });
  items.push(
    <TransitionSeries.Transition
      key="tv"
      presentation={fade()}
      timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
    />,
    <TransitionSeries.Sequence key="victory" durationInFrames={frames.verdict}>
      <VictoryScene heroes={heroes} resolution={resolution} threatSlug={threatSlug} />
    </TransitionSeries.Sequence>,
  );
  return <TransitionSeries>{items}</TransitionSeries>;
};
