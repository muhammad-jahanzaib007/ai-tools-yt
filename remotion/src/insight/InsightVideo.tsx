import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring, Sequence } from "remotion";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { loadFont as loadMontserrat } from "@remotion/google-fonts/Montserrat";
import { InsightProps, KeywordImage, FPS, chunkWords, pickAccent } from "./types";

const { fontFamily: antonFont } = loadAnton();
const { fontFamily: montserratFont } = loadMontserrat();

// Kinetic-typography-as-hero replaces the old stock-b-roll + basic karaoke
// caption approach (2026-07-23: owner rejected the b-roll style as "looks
// so 2018" — research confirmed current best-in-class explainer Shorts use
// text/motion graphics as the actual visual, not a caption layer over
// stock footage). No Pexels footage in this composition at all.

function Backdrop({ accent }: { accent: string }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  // Two slow-drifting blurred blobs (same "aurora" idea as the portfolio
  // site's hero background) so the frame never looks static, without
  // competing with the typography for attention.
  const t = frame / durationInFrames;
  const x1 = 20 + 15 * Math.sin(t * Math.PI * 2);
  const y1 = 25 + 10 * Math.cos(t * Math.PI * 1.3);
  const x2 = 75 + 12 * Math.cos(t * Math.PI * 1.7);
  const y2 = 70 + 14 * Math.sin(t * Math.PI * 2.1);
  return (
    <AbsoluteFill style={{ background: "#07070b", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: `${x1}%`,
          top: `${y1}%`,
          width: 900,
          height: 900,
          borderRadius: "50%",
          background: accent,
          opacity: 0.28,
          filter: "blur(160px)",
          transform: "translate(-50%,-50%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: `${x2}%`,
          top: `${y2}%`,
          width: 700,
          height: 700,
          borderRadius: "50%",
          background: accent,
          opacity: 0.16,
          filter: "blur(140px)",
          transform: "translate(-50%,-50%)",
        }}
      />
      {/* subtle grain */}
      <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0.05 }}>
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" />
        </filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
      {/* vignette */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "radial-gradient(ellipse at center, rgba(0,0,0,0) 45%, rgba(0,0,0,0.55) 100%)",
        }}
      />
    </AbsoluteFill>
  );
}

function HookCard({ hook, accent }: { hook: string; accent: string }) {
  const frame = useCurrentFrame();
  const scale = spring({ frame, fps: FPS, config: { damping: 14, stiffness: 140 }, durationInFrames: 18 });
  const opacity = interpolate(frame, [0, 8, 22, 27], [0, 1, 1, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: "0 90px" }}>
      <div
        style={{
          fontFamily: antonFont,
          fontSize: 92,
          lineHeight: 1.05,
          textAlign: "center",
          color: "#fff",
          textTransform: "uppercase",
          letterSpacing: -1,
          transform: `scale(${scale})`,
          opacity,
          textShadow: `0 0 60px ${accent}88`,
        }}
      >
        {hook}
      </div>
    </AbsoluteFill>
  );
}

function CaptionChunk({
  text,
  emphasisIndex,
  accent,
  startFrame,
  durFrames,
}: {
  text: string;
  emphasisIndex: number;
  accent: string;
  startFrame: number;
  durFrames: number;
}) {
  const frame = useCurrentFrame() - startFrame;
  const pop = spring({ frame, fps: FPS, config: { damping: 12, stiffness: 200 }, durationInFrames: 10 });
  const fadeOut = interpolate(frame, [durFrames - 6, durFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const words = text.split(" ");
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: "0 70px" }}>
      <div
        style={{
          fontFamily: montserratFont,
          fontWeight: 800,
          fontSize: 68,
          lineHeight: 1.15,
          textAlign: "center",
          color: "#fff",
          WebkitTextStroke: "2px rgba(0,0,0,0.55)",
          transform: `scale(${0.85 + pop * 0.15})`,
          opacity: Math.min(pop, 1) * fadeOut,
        }}
      >
        {words.map((w, i) => (
          <span key={i} style={{ color: i === emphasisIndex ? accent : "#fff" }}>
            {w}
            {i < words.length - 1 ? " " : ""}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
}

function KeywordCard({ file, accent, startFrame, durFrames }: { file: string; accent: string; startFrame: number; durFrames: number }) {
  // Owner's 2026-07-23 differentiator: pop a real photo next to the caption
  // for each stand-out keyword, timed to that word's own chunk - a small
  // framed card above the caption, not a full-bleed cutaway, so the
  // typography stays the hero and this reads as an accent, not a slideshow.
  const frame = useCurrentFrame() - startFrame;
  const pop = spring({ frame, fps: FPS, config: { damping: 13, stiffness: 180 }, durationInFrames: 10 });
  const fadeOut = interpolate(frame, [durFrames - 6, durFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: 160 }}>
      <div
        style={{
          width: 460,
          height: 460,
          borderRadius: 28,
          overflow: "hidden",
          border: `5px solid ${accent}`,
          boxShadow: `0 0 70px ${accent}77`,
          transform: `scale(${0.7 + pop * 0.3}) rotate(${(1 - pop) * -6}deg)`,
          opacity: Math.min(pop, 1) * fadeOut,
        }}
      >
        <Img src={staticFile(`insight/${file}`)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
    </AbsoluteFill>
  );
}

export const InsightVideo: React.FC<InsightProps> = ({ hook, words, accentSeed, keywordImages }) => {
  const accent = pickAccent(accentSeed);
  const chunks = chunkWords(words);
  const hookFrames = 27; // ~0.9s hard-cut hook card, then straight into captions

  return (
    <AbsoluteFill>
      <Backdrop accent={accent} />
      <Sequence from={0} durationInFrames={hookFrames}>
        <HookCard hook={hook} accent={accent} />
      </Sequence>
      {(() => {
        // Clamp each chunk's start to at least the previous chunk's end so
        // two word-groups never render on screen at once - the "2018"
        // overlap artifact came from adjacent Sequences bleeding into each
        // other's fade window.
        let prevEnd = hookFrames;
        return chunks.map((c, i) => {
          const rawStart = Math.round(c.start * FPS);
          const startFrame = Math.max(prevEnd, rawStart);
          const endFrame = Math.max(startFrame + 6, Math.round(c.end * FPS) + 2);
          const durFrames = endFrame - startFrame;
          prevEnd = endFrame;
          return (
            <Sequence key={i} from={startFrame} durationInFrames={durFrames}>
              <CaptionChunk text={c.text} emphasisIndex={c.emphasisIndex} accent={accent} startFrame={0} durFrames={durFrames} />
            </Sequence>
          );
        });
      })()}
      {(keywordImages ?? []).map((k: KeywordImage, i: number) => {
        const startFrame = Math.round(k.start * FPS);
        const endFrame = Math.max(startFrame + 6, Math.round(k.end * FPS) + 2);
        return (
          <Sequence key={`kw${i}`} from={startFrame} durationInFrames={endFrame - startFrame}>
            <KeywordCard file={k.file} accent={accent} startFrame={0} durFrames={endFrame - startFrame} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
