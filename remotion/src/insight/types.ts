export const FPS = 30;
export const W = 1080;
export const H = 1920;

export type Word = {
  word: string;
  start: number; // seconds, from Whisper-aligned timing
  end: number;
};

export type KeywordImage = {
  start: number; // seconds
  end: number;
  file: string; // top card image, filename under public/insight/
  file2?: string; // bottom card - a DIFFERENT photo of the same keyword
};

export type InsightProps = {
  hook: string;
  words: Word[];
  accentSeed: string; // hashed into an accent color, one per video (see pickAccent)
  durationInFrames: number; // computed in render_video.py from the real audio length
  keywordImages?: KeywordImage[]; // 2026-07-23: one photo per stand-out keyword chunk
};

// One saturated accent per video, hashed from the slug — same idea the
// bold-poster ranking style already uses, so the channel's look stays
// varied video-to-video but each video reads as one cohesive palette.
const ACCENTS = [
  "#e6a95c", // gold (Snackbyte Human brand)
  "#FFB23D", // amber
  "#d97757", // coral
  "#f0b46a", // light amber
  "#c9822e", // caramel
  "#e8b923", // warm yellow
];

export function pickAccent(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return ACCENTS[h % ACCENTS.length];
}

// Group words into 2-4 word caption chunks, breaking on the biggest timing
// gap within a window so a chunk boundary tends to land on a natural pause
// rather than a fixed word-count - reads closer to how the sentence is
// actually spoken.
export interface Chunk {
  text: string;
  start: number;
  end: number;
  emphasisIndex: number; // index into this chunk's words - the accent-colored one
}

export function chunkWords(words: Word[]): Chunk[] {
  const chunks: Chunk[] = [];
  let i = 0;
  while (i < words.length) {
    const size = Math.min(3, words.length - i);
    const slice = words.slice(i, i + size);
    // emphasis = the longest word in the chunk (a crude but reliable proxy
    // for the "important" word - numbers and specific nouns tend to be longer
    // than function words like "the"/"a"/"is").
    let ei = 0;
    for (let k = 1; k < slice.length; k++) {
      if (slice[k].word.length > slice[ei].word.length) ei = k;
    }
    chunks.push({
      text: slice.map((w) => w.word).join(" "),
      start: slice[0].start,
      end: slice[slice.length - 1].end,
      emphasisIndex: ei,
    });
    i += size;
  }
  return chunks;
}
