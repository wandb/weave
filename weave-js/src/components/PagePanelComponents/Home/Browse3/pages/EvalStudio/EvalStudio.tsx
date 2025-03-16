import React from 'react';

import {CreateDataset} from './components/CreateDataset';
import {CreateEvaluation} from './components/CreateEvaluation';
import {CreateScorer} from './components/CreateScorer';
import {EvaluationResults} from './components/EvaluationResults';
import {EvaluationsList} from './components/EvaluationsList';
import {EvalStudioProvider} from './context';
import {useEvalStudio} from './context';

type EvalStudioPageProps = {
  entity: string;
  project: string;
};

const EvalStudioContent: React.FC<EvalStudioPageProps> = ({
  entity,
  project,
}) => {
  const {
    selectedEvaluation,
    isCreatingNewEval,
    isCreatingNewDataset,
    isCreatingNewScorer,
  } = useEvalStudio();

  if (isCreatingNewDataset) {
    return <CreateDataset />;
  }

  if (isCreatingNewScorer) {
    return <CreateScorer />;
  }

  if (isCreatingNewEval) {
    return <CreateEvaluation />;
  }

  return (
    <div style={{display: 'flex', height: '100%'}}>
      <div
        style={{
          width: '300px',
          borderRight: '1px solid #ccc',
          overflow: 'auto',
        }}>
        <EvaluationsList entity={entity} project={project} />
      </div>
      <div style={{flex: 1, overflow: 'auto'}}>
        {selectedEvaluation ? (
          <EvaluationResults />
        ) : (
          <div style={{padding: '1rem'}}>
            Select an evaluation from the list or create a new one
          </div>
        )}
      </div>
    </div>
  );
};

export const EvalStudioPage: React.FC<EvalStudioPageProps> = ({
  entity,
  project,
}) => {
  return (
    <EvalStudioProvider>
      <div style={{height: '100vh', display: 'flex', flexDirection: 'column'}}>
        <EvalStudioContent entity={entity} project={project} />
      </div>
    </EvalStudioProvider>
  );
};
