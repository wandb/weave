import { Button } from '@wandb/weave/components/Button';
import { IconNames } from '@wandb/weave/components/Icon';
import React, { useState } from 'react';

import { EditOrCreateAnnotationSpec } from '../../feedback/HumanFeedback/EditOrCreateAnnotationSpec';
import { SimplePageLayoutWithHeader } from '../common/SimplePageLayout';
import { AnnotationsTab } from './AnnotationsTab';
import { ProgrammaticScorersTab } from './CoreScorersTab';
import { LLMJudgesTab } from './LLMJudgesTab';
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
            label: scorerTypeRecord.ANNOTATION.label + 's',
            icon: scorerTypeRecord.ANNOTATION.icon,
            content: <AnnotationsTab entity={entity} project={project} />,
          },
          {
            label: scorerTypeRecord.LLM_JUDGE.label + 's',
            icon: scorerTypeRecord.LLM_JUDGE.icon,
            content: <LLMJudgesTab entity={entity} project={project} />,
          },
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
        open={isModalOpen}
        initialScorerType={selectedTab}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  );
};

type ScorerType = 'programmatic' | 'action_spec' | 'human_annotation';
type OptionType = {
  label: string;
  value: ScorerType;
  isDisabled: boolean;
};

const CreateScorerDrawer = ({
  entityName,
  projectName,
  onClose,
}: {
  entityName: string;
  projectName: string;
  onClose: () => void;
}) => {
  const options: OptionType[] = [
    {label: 'Programmatic scorer', value: 'programmatic', isDisabled: true},
    {label: 'Human annotation', value: 'human_annotation', isDisabled: false},
    {label: 'Action spec scorer', value: 'action_spec', isDisabled: true},
  ];
  const defaultScorerType = options.find(opt => !opt.isDisabled);
  const [selectedType, setSelectedType] = useState<ScorerType>(
    defaultScorerType!.value
  );

  const renderContent = () => {
    switch (selectedType) {
      case 'programmatic':
        return <CreateProgrammaticScorer />;
      case 'action_spec':
        return <CreateActionSpecScorer />;
      case 'human_annotation':
        return (
          <EditOrCreateAnnotationSpec
            entityName={entityName}
            projectName={projectName}
            onSaveCB={onClose}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Tailwind>
      <div className="h-full p-12">
        <div className="flex items-center">
          <div className="mb-4 text-lg font-semibold">Create scorer</div>
          <div className="flex-grow" />
          <Button icon="close" onClick={onClose} variant="ghost" />
        </div>
        <div className="my-8">
          <div className="text-md mb-4 font-semibold">Scorer type</div>
          <Select<{label: string; value: ScorerType}>
            value={options.find(opt => opt.value === selectedType)}
            onChange={option => {
              if (option) {
                setSelectedType(option.value);
              }
            }}
            defaultValue={defaultScorerType}
            options={options}
          />
        </div>
        {renderContent()}
      </div>
    </Tailwind>
  );
};

// Stub components for each scorer type
const CreateProgrammaticScorer: React.FC = () => {
  return <div>Programmatic Scorer Form</div>;
};

const CreateActionSpecScorer: React.FC = () => {
  return <div>Action Spec Scorer Form</div>;
};
