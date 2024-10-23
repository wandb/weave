import { Box } from '@material-ui/core';
import { Button } from '@wandb/weave/components/Button/Button';
import React, { FC, useState } from 'react';

import { SimplePageLayout, SimplePageLayoutWithHeader } from '../common/SimplePageLayout';
import { FilterableObjectVersionsTable } from '../ObjectVersionsPage';
import { NewBuiltInActionScorerModal } from './NewBuiltInActionScorerModal';
import { ActionWithConfigSchema } from '../../collections/actionCollection';

export const ScorersPage: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <SimplePageLayoutWithHeader
      title="Scorers"
      // hideTabsIfSingle
      tabs={[
        {
          label: 'Code Scorers',
          content: <CodeScorersTab entity={entity} project={project} />,
        },
        {
          label: 'Human Review',
          content: <HumanScorersTab entity={entity} project={project} />,
        },
        {
          label: 'Built-In Actions',
          content: <OnlineScorersTab entity={entity} project={project} />,
        },
      ]} 
      headerContent={undefined}      
    />
  );
};

const CodeScorersTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  // return <div>Placeholder - Add All the saved scorers here! - complexity - missing oponly scorers</div>; 
  return <FilterableObjectVersionsTable
    entity={entity}
    project={project}
    initialFilter={{
      baseObjectClass: 'Scorer',
    }}
  />
};

const HumanScorersTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return <FilterableObjectVersionsTable
  entity={entity}
  project={project}
  initialFilter={{
    baseObjectClass: 'PLACEHOLDER_FOR_COLUMN_CONFIG',
  }}
/>
};

const OnlineScorersTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleOpenModal = () => setIsModalOpen(true);
  const handleCloseModal = () => setIsModalOpen(false);
  const handleSaveModal = (newAction: ActionWithConfigSchema) => {
    // Implement save logic here
    console.log('New action:', newAction);
    // TODO: Save the new action to the backend or update the state
    handleCloseModal();
  };

  return (
    <Box sx={{
      display: 'flex',
      flexDirection: 'column',
      flex: '1 1 auto',
      width: '100%',
    }}>
      <Box sx={{
        display: 'flex',
        flexDirection: 'row',
        justifyContent: 'flex-end',
        p: 2,
        width: '100%',
      }}>
        <AddNewButton onClick={handleOpenModal} />
      </Box>
      <FilterableObjectVersionsTable
        entity={entity}
        project={project}
        initialFilter={{
          baseObjectClass: 'ActionWithConfig',
        }}
      />
      <NewBuiltInActionScorerModal
        open={isModalOpen}
        onClose={handleCloseModal}
        onSave={handleSaveModal}
      />
    </Box>
  );
};

export const AddNewButton: FC<{
  onClick: () => void;
  disabled?: boolean;
  tooltipText?: string;
}> = ({onClick, disabled, tooltipText}) => (
  <Box
    sx={{
      height: '100%',
      display: 'flex',
      alignItems: 'center',
    }}>
    <Button
      className="mx-4"
      size="medium"
      variant="primary"
      disabled={disabled}
      onClick={onClick}
      icon="add-new"
      tooltip={tooltipText}>
      Create New
    </Button>
  </Box>
);
