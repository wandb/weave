


import { Box } from '@material-ui/core';
import { Button } from '@wandb/weave/components/Button/Button';
import React, { useState } from 'react';

import { ActionDispatchFilter } from '../../collections/actionCollection';
import { StyledDataGrid } from '../../StyledDataGrid';
import { NewBuiltInActionScorerModal }  from '../ScorersPage/NewBuiltInActionScorerModal';
import { TraceObjSchema } from '../wfReactInterface/traceServerClientTypes';
import { OpVersionSchema } from '../wfReactInterface/wfDataModelHooksInterface';



type OnlineScorerType = TraceObjSchema<ActionDispatchFilter>

const useOnlineScorersForOpVersion = (opVersion: OpVersionSchema): OnlineScorerType[] => {
  // Placeholder
  return []
};

export const OpOnlineScorersTab: React.FC<{
  opVersion: OpVersionSchema;
}> = ({ opVersion }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const onlineScorers = useOnlineScorersForOpVersion(opVersion);

  const handleOpenModal = () => {
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  const handleSaveModal = (newAction: any) => {
    // Implement save logic here
    console.log('New action:', newAction);
    handleCloseModal();
  };

  const columns = [
    { field: 'name', headerName: 'Name', flex: 1 },
    { field: 'actionType', headerName: 'Action Type', flex: 1 },
    // Add more columns as needed
  ];

  const rows = onlineScorers.map((scorer, index) => ({
    id: index,
    name: scorer.val.name,
    actionType: scorer.val.action.action_type,
    // Map other fields as needed
  }));

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flex: '1 1 auto',
        width: '100%',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'flex-end',
          p: 2,
          width: '100%',
        }}
      >
        <Button
          className="mx-4"
          size="medium"
          variant="primary"
          onClick={handleOpenModal}
          icon="add-new"
        >
          Create New
        </Button>
      </Box>
      <StyledDataGrid
        rows={rows}
        columns={columns}
        autoHeight
        disableRowSelectionOnClick
        sx={{
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'inherit',
          },
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

