import React from "react";
import {
  AbsoluteFill,
  interpolate,
  random,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// Film grain: static SVG turbulence tile, adds texture so flats never look flat.
const GRAIN =
  "data:image/svg+xml," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'>" +
      "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter>" +
      "<rect width='300' height='300' filter='url(#n)' opacity='0.6'/></svg>",
  );

export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.05 }) => (
  <AbsoluteFill
    style={{
      backgroundImage: `url("${GRAIN}")`,
      backgroundRepeat: "repeat",
      opacity,
      pointerEvents: "none",
    }}
  />
);

export const Vignette: React.FC<{ strength?: number }> = ({
  strength = 0.4,
}) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,${strength}) 100%)`,
      pointerEvents: "none",
    }}
  />
);

// A light band sweeping across the parent (parent needs overflow:hidden).
export const ShineSweep: React.FC<{
  at: number;
  duration?: number;
  strength?: number;
}> = ({ at, duration = 20, strength = 0.30 }) => {
  const frame = useCurrentFrame();
  if (frame < at || frame > at + duration) {
    return null;
  }
  const x = interpolate(frame, [at, at + duration], [-70, 170]);
  return (
    <div
      style={{
        position: "absolute",
        top: "-30%",
        bottom: "-30%",
        width: "26%",
        left: `${x}%`,
        rotate: "18deg",
        background: `linear-gradient(90deg, transparent, rgba(255,255,255,${strength}), transparent)`,
        pointerEvents: "none",
      }}
    />
  );
};

// Radial spark burst for impact moments (VS pop, winner reveal).
export const SparkBurst: React.FC<{
  at: number;
  color: string;
  size?: number;
  count?: number;
  seed?: string;
}> = ({ at, color, size = 260, count = 10, seed = "spark" }) => {
  const frame = useCurrentFrame();
  const p = (frame - at) / 16;
  if (p <= 0 || p >= 1) {
    return null;
  }
  const eased = 1 - (1 - p) * (1 - p);
  return (
    <div style={{ position: "absolute", width: 0, height: 0 }}>
      {Array.from({ length: count }).map((_, i) => {
        const ang = (360 / count) * i + random(`${seed}-${i}`) * 20;
        const dist = eased * size * (0.7 + random(`${seed}-d${i}`) * 0.5);
        const len = (1 - eased) * 46 + 10;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              width: 7,
              height: len,
              borderRadius: 4,
              backgroundColor: color,
              opacity: 1 - p,
              rotate: `${ang}deg`,
              translate: `${Math.sin((ang * Math.PI) / 180) * dist}px ${-Math.cos((ang * Math.PI) / 180) * dist}px`,
            }}
          />
        );
      })}
    </div>
  );
};

// Falling confetti for the verdict scene. Deterministic via random(seed).
export const Confetti: React.FC<{
  colors: string[];
  count?: number;
}> = ({ colors, count = 22 }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ overflow: "hidden", pointerEvents: "none" }}>
      {Array.from({ length: count }).map((_, i) => {
        const x = random(`cx${i}`) * 100;
        const delay = random(`cd${i}`) * fps;
        const speed = (0.35 + random(`cs${i}`) * 0.4) * (height / (4 * fps));
        const size = 12 + random(`cz${i}`) * 14;
        const color = colors[i % colors.length];
        const t = Math.max(0, frame - delay);
        const y = ((t * speed) % (height * 1.15)) - height * 0.08;
        const rot = random(`cr${i}`) * 360 + t * (2 + random(`cv${i}`) * 4);
        const sway = Math.sin(t / 9 + i) * width * 0.02;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `calc(${x}% + ${sway}px)`,
              top: y,
              width: size,
              height: size * 0.45,
              borderRadius: 3,
              backgroundColor: color,
              opacity: 0.85,
              rotate: `${rot}deg`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
