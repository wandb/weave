import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useMemo} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {MagicAnalysisBase, MagicAnalysisConfig} from './MagicAnalysisBase';
import {SYSTEM_PROMPT_FN} from './magicCallAnalysis';

const MAGIC_CALL_ANALYSIS_FEEDBACK_TYPE = 'wandb.magic_call_analysis';

export const MagicCallAnalysisTab: FC<{
  entity: string;
  project: string;
  callId: string;
}> = props => {
  return (
    <Tailwind style={{height: '100%', width: '100%'}}>
      <MagicCallAnalysisTabInner {...props} />
    </Tailwind>
  );
};

const MagicCallAnalysisTabInner: FC<{
  entity: string;
  project: string;
  callId: string;
}> = ({entity, project, callId}) => {
  const {useCall} = useWFHooks();

  // Fetch the call data
  const callQuery = useCall({
    key: {
      entity,
      project,
      callId,
    },
    includeCosts: true,
    includeTotalStorageSize: true,
  });

  const call = callQuery.result;

  const systemPrompt = useMemo(() => {
    return SYSTEM_PROMPT_FN({
      call: call as CallSchema | null,
    });
  }, [call]);

  const config: MagicAnalysisConfig = {
    feedbackType: MAGIC_CALL_ANALYSIS_FEEDBACK_TYPE,
    systemPrompt,
    emptyStateTitle: 'Generate Call Analysis',
    emptyStateDescription:
      'Use AI to analyze this call and generate insights about performance, patterns, and potential improvements.',
    analysisTitle: 'Generated Call Analysis',
    tooltipPlaceholder:
      'Ask specific questions about the call, or leave empty for a comprehensive analysis...',
    regenerateTooltipPlaceholder:
      'Ask follow-up questions or leave empty to regenerate the analysis...',
    extraLogAttributes: {
      entity,
      project,
      callId,
      callLink: `https://wandb.ai/${entity}/${project}/weave/calls/${callId}`,
      feature: 'call_analysis',
    },
  };

  return (
    <MagicAnalysisBase
      entity={entity}
      project={project}
      callId={callId}
      config={config}
    />
  );
};
