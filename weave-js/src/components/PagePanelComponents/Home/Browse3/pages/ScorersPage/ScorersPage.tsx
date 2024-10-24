import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import {Button} from '@wandb/weave/components/Button/Button';
import React, {FC, useState} from 'react';

import {ActionWithConfig} from '../../collections/actionCollection';
import {useCreateCollectionObject} from '../../collections/getCollectionObjects';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {FilterableObjectVersionsTable} from '../ObjectVersionsPage';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {NewBuiltInActionScorerModal} from './NewBuiltInActionScorerModal';

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
          label: 'Built-In Actions',
          content: <OnlineScorersTab entity={entity} project={project} />,
        },
        {
          label: 'Human Review',
          content: <HumanScorersTab entity={entity} project={project} />,
        },
        {
          label: 'Code Scorers',
          content: <CodeScorersTab entity={entity} project={project} />,
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
  return (
    <FilterableObjectVersionsTable
      entity={entity}
      project={project}
      initialFilter={{
        baseObjectClass: 'Scorer',
      }}
    />
  );
};

const HumanScorersTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <Box sx={{p: 3}}>
      <Alert severity="info">Human Review coming soon</Alert>
    </Box>
  );
  // return (
  //   <FilterableObjectVersionsTable
  //     entity={entity}
  //     project={project}
  //     initialFilter={{
  //       baseObjectClass: 'PLACEHOLDER_FOR_COLUMN_CONFIG',
  //     }}
  //   />
  // );
};

const OnlineScorersTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const createCollectionObject = useCreateCollectionObject('ActionWithConfig');
  const [lastUpdatedTimestamp, setLastUpdatedTimestamp] = useState(0);

  const handleOpenModal = () => setIsModalOpen(true);
  const handleCloseModal = () => setIsModalOpen(false);
  const handleSaveModal = (newAction: ActionWithConfig) => {
    // Implement save logic here
    console.log('New action:', newAction);
    // TODO: Save the new action to the backend or update the state
    //
    let objectId = newAction.name;
    // Remove non alphanumeric characters
    objectId = objectId.replace(/[^a-zA-Z0-9]/g, '-');
    createCollectionObject({
      obj: {
        project_id: projectIdFromParts({entity, project}),
        object_id: objectId,
        val: newAction,
      },
    })
      .then(() => {
        setLastUpdatedTimestamp(Date.now());
      })
      .catch(err => {
        console.error(err);
      })
      .finally(() => {
        handleCloseModal();
      });
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flex: '1 1 auto',
        width: '100%',
      }}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'flex-end',
          p: 2,
          width: '100%',
        }}>
        <AddNewButton onClick={handleOpenModal} />
      </Box>
      <FilterableObjectVersionsTable
        key={lastUpdatedTimestamp}
        entity={entity}
        project={project}
        initialFilter={{
          baseObjectClass: 'ConfiguredAction',
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
