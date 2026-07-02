import React from "react";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { BattleProps, TRANSITION_FRAMES, framesOf } from "./types";
import { VsIntro } from "./VsIntro";
import { RoundScene } from "./RoundScene";
import { VerdictScene } from "./VerdictScene";

export const BattleVideo: React.FC<BattleProps> = (props) => {
  const { toolA, toolB, tagline, rounds, verdict } = props;
  const frames = framesOf(props);
  const items: React.ReactNode[] = [
    <TransitionSeries.Sequence key="intro" durationInFrames={frames.intro}>
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
      <TransitionSeries.Sequence key={`r${i}`} durationInFrames={frames.rounds[i]}>
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
    <TransitionSeries.Sequence key="verdict" durationInFrames={frames.verdict}>
      <VerdictScene toolA={toolA} toolB={toolB} rounds={rounds} verdict={verdict} />
    </TransitionSeries.Sequence>,
  );
  return <TransitionSeries>{items}</TransitionSeries>;
};
