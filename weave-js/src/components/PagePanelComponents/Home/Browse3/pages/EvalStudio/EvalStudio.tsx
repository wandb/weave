import React from 'react';

import {CreateDataset} from './components/CreateDataset';
import {CreateEvaluation} from './components/CreateEvaluation';
import {CreateScorer} from './components/CreateScorer';
import {EvalStudioMainView} from './components/EvalStudioPage';
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
  const {isCreatingNewDataset, isCreatingNewScorer, isCreatingNewEval} =
    useEvalStudio();

  if (isCreatingNewDataset) {
    return <CreateDataset />;
  }

  if (isCreatingNewScorer) {
    return <CreateScorer />;
  }

  if (isCreatingNewEval) {
    return <CreateEvaluation />;
  }

  return <EvalStudioMainView entity={entity} project={project} />;
};

export const EvalStudioPage: React.FC<EvalStudioPageProps> = ({
  entity,
  project,
}) => {
  return (
    <EvalStudioProvider>
      <div style={{height: '100%', display: 'flex', flexDirection: 'column'}}>
        <EvalStudioContent entity={entity} project={project} />
      </div>
    </EvalStudioProvider>
  );
};
