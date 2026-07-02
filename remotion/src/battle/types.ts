export type RoundData = {
  title: string;
  aPoint: string;
  bPoint: string;
  winner: "a" | "b";
};

export type BattleProps = {
  toolA: string;
  toolB: string;
  tagline: string;
  rounds: RoundData[];
  verdict: string;
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

export const scoreAfter = (rounds: RoundData[], uptoIndex: number) => {
  let a = 0;
  let b = 0;
  for (let i = 0; i <= uptoIndex && i < rounds.length; i++) {
    if (rounds[i].winner === "a") a++;
    else b++;
  }
  return { a, b };
};
