import "./index.css";
import { CalculateMetadataFunction, Composition } from "remotion";
import { BattleVideo } from "./battle/BattleVideo";
import { BattleProps, FPS, battleDuration, totalFrames } from "./battle/types";
import { ComicProps, ComicVideo, totalComicFrames } from "./comic/ComicVideo";

const sampleBattle: BattleProps = {
  toolA: "ElevenLabs",
  toolB: "Speechify",
  tagline: "Which AI voice sounds more human?",
  rounds: [
    {
      title: "Voice quality",
      aPoint: "Natural emotion, breathing, and pauses. Hard to tell from a human.",
      bPoint: "Clean and clear, but flatter delivery on long passages.",
      winner: "a",
    },
    {
      title: "Price",
      aPoint: "Starts at $5/mo for 30 minutes of audio.",
      bPoint: "Free tier available, premium unlocks all voices.",
      winner: "b",
    },
    {
      title: "Speed & workflow",
      aPoint: "API access, instant voice cloning, studio editor.",
      bPoint: "Great mobile apps, reads any document aloud.",
      winner: "a",
    },
  ],
  verdict:
    "ElevenLabs wins for creators who need human-sounding narration. Speechify is still the better pick for listening to documents on the go.",
};

// Duration follows the props: the render script passes per-scene frame counts
// (sceneFrames) computed from the narration audio lengths.
const battleMetadata: CalculateMetadataFunction<BattleProps> = ({ props }) => ({
  durationInFrames: totalFrames(props),
});

const sampleComic: ComicProps = {
  episodeTitle: "The Blank Page strikes. Two heroes answer.",
  threat: "The Blank Page",
  threatSlug: "the-blank-page",
  heroes: [
    {
      tool: "Writesonic",
      alias: "Scribe",
      color: "#4F8EF7",
      power: "Floods the empty page with copy at lightspeed",
      slug: "writesonic",
    },
    {
      tool: "ChatGPT",
      alias: "The Oracle",
      color: "#74AA9C",
      power: "Outlines the whole piece before the villain can blink",
      slug: "chatgpt",
    },
  ],
  resolution:
    "The page fills itself. Writesonic drafts, the Oracle plans, and the deadline never stood a chance.",
};

const comicMetadata: CalculateMetadataFunction<ComicProps> = ({ props }) => ({
  durationInFrames: totalComicFrames(props),
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="BattleLong"
        component={BattleVideo}
        durationInFrames={battleDuration(sampleBattle.rounds.length)}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={sampleBattle}
        calculateMetadata={battleMetadata}
      />
      <Composition
        id="BattleShort"
        component={BattleVideo}
        durationInFrames={battleDuration(sampleBattle.rounds.length)}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={sampleBattle}
        calculateMetadata={battleMetadata}
      />
      <Composition
        id="ComicShort"
        component={ComicVideo}
        durationInFrames={totalComicFrames(sampleComic)}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={sampleComic}
        calculateMetadata={comicMetadata}
      />
    </>
  );
};
