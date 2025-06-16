import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';

export type EvaluationExplorerPageProps = {
  entity: string;
  project: string;
};

export const EvaluationExplorerPage = (props: EvaluationExplorerPageProps) => {
  return (
    <SimplePageLayoutWithHeader
      title="EvaluationExplorer"
      hideTabsIfSingle
      headerContent={null}
      tabs={[
        {
          label: 'main',
          content: (
            <Tailwind style={{width: '100%', height: '100%'}}>
              <EvaluationExplorerPageInner {...props} />
            </Tailwind>
          ),
        },
      ]}
      headerExtra={null}
    />
  );
};

export const EvaluationExplorerPageInner: React.FC<
  EvaluationExplorerPageProps
> = ({entity, project}) => {
  return (
    <div>
      <h1>Evaluation Explorer</h1>
    </div>
  );
};
