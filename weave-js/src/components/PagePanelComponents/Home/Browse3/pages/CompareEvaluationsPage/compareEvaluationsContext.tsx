import React, {useEffect, useMemo, useState} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {
  EvaluationComparisonData,
  fetchEvaluationComparisonData,
} from './evaluationResults';

const CompareEvaluationsContext =
  React.createContext<EvaluationComparisonState | null>(null);

export type EvaluationComparisonState = {
  data: EvaluationComparisonData;
  baselineEvaluationCallId: string;
};

export const useCompareEvaluationsState = () => {
  const ctx = React.useContext(CompareEvaluationsContext);
  if (ctx === null) {
    throw new Error('No CompareEvaluationsProvider');
  }
  return ctx;
};

export const CompareEvaluationsProvider: React.FC<{
  entity: string;
  project: string;
  evaluationCallIds: string[];
  baselineEvaluationCallId: string;
}> = ({
  entity,
  project,
  evaluationCallIds,
  baselineEvaluationCallId,
  children,
}) => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [data, setData] = useState<EvaluationComparisonData | null>(null);
  const evaluationCallIdsMemo = useDeepMemo(evaluationCallIds);
  useEffect(() => {
    setData(null);
    let mounted = true;
    fetchEvaluationComparisonData(
      getTraceServerClient(),
      entity,
      project,
      evaluationCallIdsMemo
    ).then(dataRes => {
      if (mounted) {
        setData(dataRes);
      }
    });
    return () => {
      mounted = false;
    };
  }, [entity, evaluationCallIdsMemo, project, getTraceServerClient]);

  const value = useMemo(() => {
    if (data == null) {
      return null;
    }
    return {data, baselineEvaluationCallId};
  }, [data, baselineEvaluationCallId]);

  if (value == null) {
    return <div>Loading...</div>;
  }

  return (
    <CompareEvaluationsContext.Provider value={value}>
      {children}
    </CompareEvaluationsContext.Provider>
  );
};
