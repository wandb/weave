import {Button} from '@wandb/weave/components/Button';
import {IconNames} from '@wandb/weave/components/Icon';
import React, {useState} from 'react';

import {useShowRunnableUI} from '../CallPage/CallPage';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {AnnotationsTab} from './AnnotationsTab';
import {ProgrammaticScorersTab} from './CoreScorersTab';
import {LLMJudgesTab} from './LLMJudgesTab';
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

  const showRunnableUI = useShowRunnableUI();

  return (
    <>
      <SimplePageLayoutWithHeader
        title="Scorers"
        tabs={[
          {
            label: scorerTypeRecord.ANNOTATION.label + 's',
            icon: scorerTypeRecord.ANNOTATION.icon,
            content: <AnnotationsTab entity={entity} project={project} />,
          },
          ...(showRunnableUI
            ? [
                {
                  label: scorerTypeRecord.LLM_JUDGE.label + 's',
                  icon: scorerTypeRecord.LLM_JUDGE.icon,
                  content: <LLMJudgesTab entity={entity} project={project} />,
                },
              ]
            : []),
          {
            label: scorerTypeRecord.PROGRAMMATIC.label + 's',
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
            // Hacky that we have to do the `"s"` thing, but it works
            Object.values(scorerTypeRecord).find(t => t.label + 's' === tab)
              ?.value ?? HUMAN_ANNOTATION_VALUE
          )
        }
      />
      <NewScorerDrawer
        entity={entity}
        project={project}
        open={isModalOpen}
        initialScorerType={selectedTab}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  );
};
