import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useState} from 'react';

import {EditOrCreateAnnotationSpec} from '../../feedback/HumanFeedback/EditOrCreateAnnotationSpec';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {ActionSpecsTab} from './ActionSpecsTab';
import {AnnotationsTab} from './AnnotationsTab';
import {ProgrammaticScorersTab} from './CoreScorersTab';

export const ScorersPage: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
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
      headerExtra={
        <Button
          className="p-5 pr-8"
          icon="add-new"
          onClick={() => setIsDrawerOpen(true)}>
          Create scorer
        </Button>
      }
      isRightSidebarOpen={isDrawerOpen}
      rightSidebarContent={
        <CreateScorerDrawer
          entityName={entity}
          projectName={project}
          onClose={() => setIsDrawerOpen(false)}
        />
      }
    />
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
