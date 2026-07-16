export type RoundData = {
  title: string;
  aPoint: string;
  bPoint: string;
  winner: "a" | "b";
};

export type SceneFrames = {
  intro: number;
  rounds: number[];
  verdict: number;
};

export type BattleProps = {
  toolA: string;
  toolB: string;
  tagline: string;
  rounds: RoundData[];
  verdict: string;
  // Overall winner declared by the brief. The round score can split 1-1
  // (2-round battles usually do) and the spoken verdict is free to name
  // either tool, so the crown must follow this, not the score.
  champion?: "a" | "b";
  // Per-scene durations in frames, computed by the render script from the
  // narration audio lengths. Absent = the fixed preview defaults below.
  sceneFrames?: SceneFrames;
};

export const COLORS = {
  bg: "#0b0b14",
  cream: "#F2EEE4",
  coral: "#D97757",
  dark: "#1A1915",
  teal: "#2AA198",
  white: "#FFFFFF",
};

export const FPS = 30;
export const INTRO_FRAMES = 4 * FPS;
export const ROUND_FRAMES = 8 * FPS;
export const VERDICT_FRAMES = 7 * FPS;
export const TRANSITION_FRAMES = 15;

export const battleDuration = (rounds: number) =>
  INTRO_FRAMES +
  rounds * ROUND_FRAMES +
  VERDICT_FRAMES -
  (rounds + 1) * TRANSITION_FRAMES;

const MIN_SCENE = 2 * TRANSITION_FRAMES + 5;

export const framesOf = (p: BattleProps): SceneFrames => {
  const f =
    p.sceneFrames && p.sceneFrames.rounds.length === p.rounds.length
      ? p.sceneFrames
      : {
          intro: INTRO_FRAMES,
          rounds: p.rounds.map(() => ROUND_FRAMES),
          verdict: VERDICT_FRAMES,
        };
  return {
    intro: Math.max(MIN_SCENE, f.intro),
    rounds: f.rounds.map((r) => Math.max(MIN_SCENE, r)),
    verdict: Math.max(MIN_SCENE, f.verdict),
  };
};

export const totalFrames = (p: BattleProps) => {
  const f = framesOf(p);
  return (
    f.intro +
    f.rounds.reduce((a, b) => a + b, 0) +
    f.verdict -
    (p.rounds.length + 1) * TRANSITION_FRAMES
  );
};

export const scoreAfter = (rounds: RoundData[], uptoIndex: number) => {
  let a = 0;
  let b = 0;
  for (let i = 0; i <= uptoIndex && i < rounds.length; i++) {
    if (rounds[i].winner === "a") a++;
    else b++;
  }
  return { a, b };
};
