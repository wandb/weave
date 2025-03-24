import {Button} from '@wandb/weave/components/Button';
import {IconNames} from '@wandb/weave/components/Icon';
import React, {useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {
  HUMAN_ANNOTATION_VALUE,
  NewScorerDrawer,
  ScorerType,
  scorerTypeRecord,
} from './NewScorerDrawer';
import {CombinedScorersTable} from './CombinedScorersTable';

export const ScorersPage: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedScorerType, setSelectedScorerType] = useState<ScorerType>(
    scorerTypeRecord.ANNOTATION.value
  );

  return (
    <>
      <SimplePageLayoutWithHeader
        title="Scorers"
        tabs={[
          {
            label: 'All Scorers',
            content: <CombinedScorersTable entity={entity} project={project} />
          }
        ]}
        hideTabsIfSingle
        headerExtra={
          <Button
            icon={IconNames.AddNew}
            onClick={() => setIsModalOpen(true)}
            variant="secondary">
            Create scorer
          </Button>
        }
        headerContent={undefined}
      />
      <NewScorerDrawer
        entity={entity}
        project={project}
        open={isModalOpen}
        initialScorerType={selectedScorerType}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  );
};
