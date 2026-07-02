import React from "react";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import {
  BattleProps,
  INTRO_FRAMES,
  ROUND_FRAMES,
  TRANSITION_FRAMES,
  VERDICT_FRAMES,
} from "./types";
import { VsIntro } from "./VsIntro";
import { RoundScene } from "./RoundScene";
import { VerdictScene } from "./VerdictScene";

export const BattleVideo: React.FC<BattleProps> = ({
  toolA,
  toolB,
  tagline,
  rounds,
  verdict,
}) => {
  const items: React.ReactNode[] = [
    <TransitionSeries.Sequence key="intro" durationInFrames={INTRO_FRAMES}>
      <VsIntro toolA={toolA} toolB={toolB} tagline={tagline} />
    </TransitionSeries.Sequence>,
  ];
  rounds.forEach((round, i) => {
    items.push(
      <TransitionSeries.Transition
        key={`t${i}`}
        presentation={slide({ direction: i % 2 === 0 ? "from-right" : "from-left" })}
        timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
      />,
      <TransitionSeries.Sequence key={`r${i}`} durationInFrames={ROUND_FRAMES}>
        <RoundScene toolA={toolA} toolB={toolB} rounds={rounds} index={i} />
      </TransitionSeries.Sequence>,
    );
  });
  items.push(
    <TransitionSeries.Transition
      key="tv"
      presentation={fade()}
      timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
    />,
    <TransitionSeries.Sequence key="verdict" durationInFrames={VERDICT_FRAMES}>
      <VerdictScene toolA={toolA} toolB={toolB} rounds={rounds} verdict={verdict} />
    </TransitionSeries.Sequence>,
  );
  return <TransitionSeries>{items}</TransitionSeries>;
};
