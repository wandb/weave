import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useMemo} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {MagicAnalysisBase, MagicAnalysisConfig} from './MagicAnalysisBase';
import {createCallAnalysisContext,MAGIC_CALL_ANALYSIS_SYSTEM_PROMPT} from './magicCallAnalysis';

const MAGIC_CALL_ANALYSIS_FEEDBACK_TYPE = 'wandb.magic_call_analysis';

const EMPTY_STATE_TITLE = 'Generate Call Analysis';
const EMPTY_STATE_DESCRIPTION = 'Use AI to analyze this call and generate insights about performance, patterns, and potential improvements.';
const ANALYSIS_TITLE = 'Generated Call Analysis';
const PLACEHOLDER = 'Ask specific questions about the call, or leave empty for a comprehensive analysis...';
const REVISION_PLACEHOLDER = 'Ask follow-up questions or leave empty to regenerate the analysis...';

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

  const additionalContext = useMemo(() => {
    return createCallAnalysisContext(call as CallSchema | null);
  }, [call]);

  const config: MagicAnalysisConfig = {
    feedbackType: MAGIC_CALL_ANALYSIS_FEEDBACK_TYPE,
    emptyStateTitle: EMPTY_STATE_TITLE,
    emptyStateDescription: EMPTY_STATE_DESCRIPTION,
    analysisTitle: ANALYSIS_TITLE,
    magicButtonProps: {
      systemPrompt: MAGIC_CALL_ANALYSIS_SYSTEM_PROMPT,
      placeholder: PLACEHOLDER,
      revisionPlaceholder: REVISION_PLACEHOLDER,
      additionalContext,
      showModelSelector: true,
      width: 450,
      textareaLines: 6,
      _dangerousExtraAttributesToLog: {
        entity,
        project,
        callId,
        callLink: `https://wandb.ai/${entity}/${project}/weave/calls/${callId}`,
        feature: 'call_analysis',
      },
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
