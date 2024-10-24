import {Box} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button/Button';
import React, {FC, useState} from 'react';
import {z} from 'zod';

import {
  ActionDispatchFilter,
  ActionDispatchFilterSchema,
} from '../../collections/actionCollection';
import {collectionRegistry} from '../../collections/collectionRegistry';
import {useCreateCollectionObject} from '../../collections/getCollectionObjects';
import {DynamicConfigForm} from '../../DynamicConfigForm';
import {ReusableDrawer} from '../../ReusableDrawer';
import {StyledDataGrid} from '../../StyledDataGrid';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {
  convertISOToDate,
  projectIdFromParts,
} from '../wfReactInterface/tsDataModelHooks';
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

  const columns = [
    {field: 'name', headerName: 'Name', flex: 1},
    {field: 'disabled', headerName: 'Disabled', flex: 1},
    {field: 'sampleRate', headerName: 'Sample Rate', flex: 1},
    {
      field: 'configuredActionRef',
      headerName: 'Configured Action Ref',
      flex: 1,
    },
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
        columnHeaderHeight={40}
        disableRowSelectionOnClick
        sx={{
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'inherit',
          },
        }}
      />
      <NewOnlineOpScorerModal
        entity={opVersion.entity}
        project={opVersion.project}
        collectionDef={{
          name: 'ActionDispatchFilter',
          schema: ActionDispatchFilterSchema,
        }}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </Box>
  );
};

interface NewOnlineOpScorerModalProps {
  entity: string;
  project: string;
  collectionDef: {
    name: keyof typeof collectionRegistry;
    schema: z.Schema;
  };
  isOpen: boolean;
  onClose: () => void;
}

export const NewOnlineOpScorerModal: FC<NewOnlineOpScorerModalProps> = ({
  entity,
  project,
  collectionDef,
  isOpen,
  onClose,
}) => {
  const [config, setConfig] = useState<Record<string, any>>({});

  const createCollectionObject = useCreateCollectionObject(collectionDef.name);

  const handleSaveModal = (newAction: Record<string, any>) => {
    const parsedAction = collectionDef.schema.safeParse(newAction);
    if (!parsedAction.success) {
      console.error(
        `Invalid action: ${JSON.stringify(parsedAction.error.errors)}`
      );
      return;
    }
    let objectId = newAction.name;
    // Remove non alphanumeric characters
    objectId = objectId.replace(/[^a-zA-Z0-9]/g, '-');
    createCollectionObject({
      obj: {
        project_id: projectIdFromParts({entity, project}),
        object_id: objectId,
        val: parsedAction.data,
      },
    })
      .catch(err => {
        console.error(err);
      })
      .finally(() => {
        onClose();
      });
  };

  const [isValid, setIsValid] = useState(false);

  return (
    <ReusableDrawer
      open={isOpen}
      title="Configure new built-in action scorer"
      onClose={onClose}
      onSave={() => handleSaveModal(config)}
      saveDisabled={!isValid}>
      <DynamicConfigForm
        configSchema={collectionDef.schema}
        config={config}
        setConfig={setConfig}
        onValidChange={setIsValid}
      />
    </ReusableDrawer>
  );
};
