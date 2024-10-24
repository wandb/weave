import {Box} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button/Button';
import React, {useState} from 'react';

import {ActionDispatchFilter} from '../../collections/actionCollection';
import {StyledDataGrid} from '../../StyledDataGrid';
import {NewBuiltInActionScorerModal} from '../ScorersPage/NewBuiltInActionScorerModal';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {convertISOToDate} from '../wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {OpVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';

type OnlineScorerType = TraceObjSchema<ActionDispatchFilter>;

const useOnlineScorersForOpVersion = (
  opVersion: OpVersionSchema
): OnlineScorerType[] => {
  // Placeholder
  return [];
};

export const OpOnlineScorersTab: React.FC<{
  opVersion: OpVersionSchema;
}> = ({opVersion}) => {
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
    {field: 'name', headerName: 'Name', flex: 1},
    {field: 'disabled', headerName: 'Disabled', flex: 1},
    {field: 'sampleRate', headerName: 'Sample Rate', flex: 1},
    {
      field: 'configuredActionRef',
      headerName: 'Configured Action Ref',
      flex: 1,
    },
    // Add more columns as needed
  ];

  const rows = onlineScorers
    .filter(scorer => scorer.val.op_name === opVersion.opId)
    .map((scorer, index) => {
      const scorerRef = objectVersionKeyToRefUri({
        scheme: 'weave',
        weaveKind: 'object',
        entity: opVersion.entity,
        project: opVersion.project,
        objectId: scorer.object_id,
        versionHash: scorer.digest,
        path: '',
      });
      return {
        id: scorerRef,
        name: scorer.object_id,
        createdAt: convertISOToDate(scorer.created_at),
        disabled: scorer.val.disabled,
        sampleRate: scorer.val.sample_rate,
        configuredActionRef: scorer.val.configured_action_ref,
        // Map other fields as needed
      };
    });

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
        <Button
          className="mx-4"
          size="medium"
          variant="primary"
          onClick={handleOpenModal}
          icon="add-new">
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
