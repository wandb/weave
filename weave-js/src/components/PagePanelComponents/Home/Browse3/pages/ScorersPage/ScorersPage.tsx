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
          className="mx-8 my-4"
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

const CreateScorerDrawer = ({
  entityName,
  projectName,
  onClose,
}: {
  entityName: string;
  projectName: string;
  onClose: () => void;
}) => {
  const [selectedType, setSelectedType] = useState<ScorerType>('programmatic');
  const options: Array<{label: string; value: ScorerType}> = [
    {label: 'Programmatic scorer', value: 'programmatic'},
    {label: 'Action spec scorer', value: 'action_spec'},
    {label: 'Human annotation', value: 'human_annotation'},
  ];

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
        <div className="my-12">
          <div className="text-md mb-4 font-semibold">Select a scorer type</div>
          <Select
            value={options.find(opt => opt.value === selectedType)}
            onChange={option =>
              setSelectedType(option?.value ?? 'programmatic')
            }
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
  return <div>Programmatic Scorer Form (TODO)</div>;
};

const CreateActionSpecScorer: React.FC = () => {
  return <div>Action Spec Scorer Form (TODO)</div>;
};
