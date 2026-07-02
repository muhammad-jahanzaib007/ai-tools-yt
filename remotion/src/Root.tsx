import "./index.css";
import { Composition } from "remotion";
import { BattleVideo } from "./battle/BattleVideo";
import { BattleProps, FPS, battleDuration } from "./battle/types";

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
      />
      <Composition
        id="BattleShort"
        component={BattleVideo}
        durationInFrames={battleDuration(sampleBattle.rounds.length)}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={sampleBattle}
      />
    </>
  );
};
