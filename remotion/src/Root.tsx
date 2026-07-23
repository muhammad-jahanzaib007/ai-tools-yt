import "./index.css";
import { CalculateMetadataFunction, Composition } from "remotion";
import { BattleVideo } from "./battle/BattleVideo";
import { BattleProps, FPS, battleDuration, totalFrames } from "./battle/types";
import { ComicProps, ComicVideo, totalComicFrames } from "./comic/ComicVideo";
import { NewsProps, NewsVideo, totalNewsFrames } from "./news/NewsVideo";
import { RankingProps, RankingVideo, totalRankingFrames } from "./ranking/RankingVideo";
import { Thumb, ThumbProps } from "./thumb/Thumb";
import { InsightVideo } from "./insight/InsightVideo";
import { InsightProps } from "./insight/types";
import { ChannelBanner } from "./banner/ChannelBanner";

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

const sampleNews: NewsProps = {
  dateLabel: "5 July 2026",
  headline: "Alibaba bans Claude Code as the AI tool wars heat up",
  stories: [
    {
      title: "Alibaba bans employees from using Claude Code",
      source: "TechCrunch",
      category: "policy",
      detail: "The tool was reportedly classified as high-risk software internally.",
    },
    {
      title: "Anthropic unveils Claude Science for researchers",
      source: "The Verge",
      category: "models",
      detail: "A new AI workbench aimed squarely at scientific discovery.",
    },
    {
      title: "Midjourney demands studios reveal their AI usage",
      source: "TechCrunch",
      category: "policy",
      detail: "The legal fight with three Hollywood studios escalates.",
    },
  ],
  outro: "Follow for tomorrow's AI brief. One minute, every day.",
};

const newsMetadata: CalculateMetadataFunction<NewsProps> = ({ props }) => ({
  durationInFrames: totalNewsFrames(props),
});

const sampleRanking: RankingProps = {
  theme: "Free AI tools that beat the paid ones",
  items: [
    { rank: 5, name: "Rytr", reason: "Solid short copy on a generous free plan", tag: "Free plan" },
    { rank: 4, name: "Canva AI", reason: "Design plus AI images in one free editor", tag: "Free plan" },
    { rank: 3, name: "CapCut", reason: "Full video editor with AI captions, free", tag: "Free" },
    { rank: 2, name: "Gemini", reason: "Frontier-level answers without a subscription", tag: "Free" },
    { rank: 1, name: "ChatGPT", reason: "Still the most capable free all-rounder", tag: "Free tier" },
  ],
  cta: "Disagree with number one? Comment your pick.",
};

const rankingMetadata: CalculateMetadataFunction<RankingProps> = ({ props }) => ({
  durationInFrames: totalRankingFrames(props),
});

const sampleInsight: InsightProps = {
  hook: "You can't tickle yourself, and there's a real reason why.",
  words: [
    { word: "Your", start: 1.0, end: 1.15 },
    { word: "brain", start: 1.15, end: 1.45 },
    { word: "cancels", start: 1.45, end: 1.85 },
    { word: "out", start: 1.85, end: 2.0 },
    { word: "any", start: 2.0, end: 2.2 },
    { word: "touch", start: 2.2, end: 2.55 },
    { word: "it", start: 2.55, end: 2.65 },
    { word: "predicts", start: 2.65, end: 3.1 },
  ],
  accentSeed: "sample-insight",
  durationInFrames: 150,
  keywordImages: [{ start: 1.15, end: 1.45, file: "kw0a.jpg", file2: "kw0b.jpg" }],
};

const insightMetadata: CalculateMetadataFunction<InsightProps> = ({ props }) => ({
  durationInFrames: props.durationInFrames,
});

const sampleThumb: ThumbProps = {
  kind: "ranking",
  title: "Free AI tools that beat the paid ones",
  badge: "TOP 5",
  logos: [],
  logoDir: "ranking",
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
        id="NewsShort"
        component={NewsVideo}
        durationInFrames={totalNewsFrames(sampleNews)}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={sampleNews}
        calculateMetadata={newsMetadata}
      />
      <Composition
        id="RankingShort"
        component={RankingVideo}
        durationInFrames={totalRankingFrames(sampleRanking)}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={sampleRanking}
        calculateMetadata={rankingMetadata}
      />
      <Composition
        id="InsightShort"
        component={InsightVideo}
        durationInFrames={sampleInsight.durationInFrames}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={sampleInsight}
        calculateMetadata={insightMetadata}
      />
      <Composition
        id="Thumb"
        component={Thumb}
        durationInFrames={1}
        fps={FPS}
        width={1280}
        height={720}
        defaultProps={sampleThumb}
      />
      <Composition
        id="ChannelBanner"
        component={ChannelBanner}
        durationInFrames={1}
        fps={FPS}
        width={2560}
        height={1440}
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
