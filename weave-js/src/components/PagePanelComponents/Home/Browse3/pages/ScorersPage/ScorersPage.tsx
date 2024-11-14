import {Button} from '@wandb/weave/components/Button';
import {IconNames} from '@wandb/weave/components/Icon';
import React, {useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {ActionSpecsTab} from './ActionSpecsTab';
import {AnnotationsTab} from './AnnotationsTab';
import {ProgrammaticScorersTab} from './CoreScorersTab';
import {
  HUMAN_ANNOTATION_VALUE,
  NewScorerDrawer,
  ScorerType,
  scorerTypeRecord,
} from './NewScorerDrawer';

export const ScorersPage: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTab, setSelectedTab] = useState<ScorerType>(
    scorerTypeRecord.ANNOTATION.value
  );

  return (
    <>
      <SimplePageLayoutWithHeader
        title="Scorers"
        tabs={[
          {
            label: scorerTypeRecord.ANNOTATION.label,
            icon: scorerTypeRecord.ANNOTATION.icon,
            content: <AnnotationsTab entity={entity} project={project} />,
          },
          {
            label: scorerTypeRecord.ACTION.label,
            icon: scorerTypeRecord.ACTION.icon,
            content: <ActionSpecsTab entity={entity} project={project} />,
          },
          {
            label: scorerTypeRecord.PROGRAMMATIC.label,
            icon: scorerTypeRecord.PROGRAMMATIC.icon,
            content: (
              <ProgrammaticScorersTab entity={entity} project={project} />
            ),
          },
        ]}
        headerExtra={
          <Button
            icon={IconNames.AddNew}
            onClick={() => setIsModalOpen(true)}
            variant="secondary">
            Create scorer
          </Button>
        }
        headerContent={undefined}
        onTabSelectedCallback={tab =>
          setSelectedTab(
            Object.values(scorerTypeRecord).find(t => t.label === tab)?.value ??
              HUMAN_ANNOTATION_VALUE
          )
        }
      />
      <NewScorerDrawer
        open={isModalOpen}
        initialScorerType={selectedTab}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  );
};
