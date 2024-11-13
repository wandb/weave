import React from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {ActionSpecsTab} from './ActionSpecsTab';
import {AnnotationsTab} from './AnnotationsTab';
import {ProgrammaticScorersTab} from './CoreScorersTab';

export const ScorersPage: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <SimplePageLayoutWithHeader
      title="Scorers"
      tabs={[
        {
          label: 'Programmatic Scorers',
          content: <ProgrammaticScorersTab entity={entity} project={project} />,
        },
        {
          label: 'Human Annotations',
          content: <AnnotationsTab entity={entity} project={project} />,
        },
        {
          label: 'Configurable Scorers',
          content: <ActionSpecsTab entity={entity} project={project} />,
        },
      ]}
      headerContent={undefined}
    />
  );
};
