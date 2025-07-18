import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useMemo} from 'react';

import {useEvaluationComparisonState} from '../CompareEvaluationsPage/ecpState';
import {MagicAnalysisBase, MagicAnalysisConfig} from './MagicAnalysisBase';
import {createEvaluationAnalysisContext,MAGIC_EVALUATION_ANALYSIS_SYSTEM_PROMPT} from './magicEvaluationAnalysis';

const MAGIC_EVALUATION_ANALYSIS_FEEDBACK_TYPE = 'wandb.magic_analysis';

const EMPTY_STATE_TITLE = 'Generate Evaluation Analysis';
const EMPTY_STATE_DESCRIPTION = 'Use AI to analyze this evaluation run and generate insights about model performance, patterns, and potential improvements.';
const ANALYSIS_TITLE = 'Generated Evaluation Analysis';
const PLACEHOLDER = 'Ask specific questions about the evaluation results, or leave empty for a comprehensive analysis...';
const REVISION_PLACEHOLDER = 'Ask follow-up questions or leave empty to regenerate the analysis...';

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

  const additionalContext = useMemo(() => {
    return createEvaluationAnalysisContext(evaluationComparisonStateQuery.result);
  }, [evaluationComparisonStateQuery.result]);

  const config: MagicAnalysisConfig = {
    feedbackType: MAGIC_EVALUATION_ANALYSIS_FEEDBACK_TYPE,
    emptyStateTitle: EMPTY_STATE_TITLE,
    emptyStateDescription: EMPTY_STATE_DESCRIPTION,
    analysisTitle: ANALYSIS_TITLE,
    magicButtonProps: {
      systemPrompt: MAGIC_EVALUATION_ANALYSIS_SYSTEM_PROMPT,
      placeholder: PLACEHOLDER,
      revisionPlaceholder: REVISION_PLACEHOLDER,
      additionalContext,
      showModelSelector: true,
      width: 450,
      textareaLines: 6,
      _dangerousExtraAttributesToLog: {
        entity,
        project,
        evaluationCallId,
        evalLink: `https://wandb.ai/${entity}/${project}/weave/calls/${evaluationCallId}`,
        feature: 'evaluation_analysis',
      },
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
