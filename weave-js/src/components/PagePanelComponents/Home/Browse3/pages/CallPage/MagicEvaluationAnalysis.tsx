import {MagicButton, MagicTooltip} from '@wandb/weave/WBMagician2';
import React, {FC, useState} from 'react';

const useEvaluationAnalysisLLMContext = () => {
  return 'TODO';
};

export const MagicEvaluationAnalysis: FC<{
  entity: string;
  project: string;
  evaluationCallId: string;
}> = ({
  entity,
  project,
  evaluationCallId,
}: {
  entity: string;
  project: string;
  evaluationCallId: string;
}) => {
  const [magicSummary, setMagicSummary] = useState<string | null>(null);
  const llmContext = useEvaluationAnalysisLLMContext();
  return (
    <div>
      <h1>Magic Evaluation Analysis</h1>
      <MagicTooltip
        entityProject={{entity, project}}
        onStream={setMagicSummary}
        systemPrompt={`You are a helpful assistant that summarizes the evaluation. Evaluation data: ${llmContext}`}
        placeholder={`Provide any additional context or questions about the evaluation.`}>
        <MagicButton>Summarize</MagicButton>
      </MagicTooltip>
      <p>{magicSummary}</p>
    </div>
  );
};
