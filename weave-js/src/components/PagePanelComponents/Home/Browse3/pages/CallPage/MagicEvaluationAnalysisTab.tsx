import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useMemo} from 'react';

import {useEvaluationComparisonState} from '../CompareEvaluationsPage/ecpState';
import {MagicAnalysisBase, MagicAnalysisConfig} from './MagicAnalysisBase';
import {SYSTEM_PROMPT_FN} from './magicEvaluationAnalysis';

const MAGIC_EVALUATION_ANALYSIS_FEEDBACK_TYPE = 'wandb.magic_analysis';

export const MagicEvaluationAnalysisTab: FC<{
  entity: string;
  project: string;
  evaluationCallId: string;
}> = props => {
  return (
    <Tailwind style={{height: '100%', width: '100%'}}>
      <MagicEvaluationAnalysisTabInner {...props} />
    </Tailwind>
  );
};

const MagicEvaluationAnalysisTabInner: FC<{
  entity: string;
  project: string;
  evaluationCallId: string;
}> = ({entity, project, evaluationCallId}) => {
  const evaluationComparisonStateQuery = useEvaluationComparisonState(
    entity,
    project,
    [evaluationCallId]
  );

  const systemPrompt = useMemo(() => {
    return SYSTEM_PROMPT_FN({
      evaluationState: evaluationComparisonStateQuery.result,
    });
  }, [evaluationComparisonStateQuery.result]);

  const config: MagicAnalysisConfig = {
    feedbackType: MAGIC_EVALUATION_ANALYSIS_FEEDBACK_TYPE,
    systemPrompt,
    emptyStateTitle: 'Generate Evaluation Analysis',
    emptyStateDescription:
      'Use AI to analyze this evaluation run and generate insights about model performance, patterns, and potential improvements.',
    analysisTitle: 'Generated Evaluation Analysis',
    tooltipPlaceholder:
      'Ask specific questions about the evaluation results, or leave empty for a comprehensive analysis...',
    regenerateTooltipPlaceholder:
      'Ask follow-up questions or leave empty to regenerate the analysis...',
    extraLogAttributes: {
      entity,
      project,
      evaluationCallId,
      evalLink: `https://wandb.ai/${entity}/${project}/weave/calls/${evaluationCallId}`,
    },
  };

  return (
    <MagicAnalysisBase
      entity={entity}
      project={project}
      callId={evaluationCallId}
      config={config}
    />
  );
};
