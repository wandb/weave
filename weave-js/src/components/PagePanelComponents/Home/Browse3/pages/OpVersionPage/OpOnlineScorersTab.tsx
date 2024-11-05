import {Box} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button/Button';
import {parseRef} from '@wandb/weave/react';
import React, {FC, useMemo, useState} from 'react';
import {z} from 'zod';

import {SmallRef} from '../../../Browse2/SmallRef';
import {
  ActionDispatchFilterSchema,
  ActionDispatchFilterType,
} from '../../collections/actionCollection';
import {collectionRegistry} from '../../collections/collectionRegistry';
import {
  useCollectionObjects,
  useCreateCollectionObject,
} from '../../collections/getCollectionObjects';
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

type OnlineScorerType = TraceObjSchema<ActionDispatchFilterType>;

const useOnlineScorersForOpVersion = (
  opVersion: OpVersionSchema
): {scorers: OnlineScorerType[]; refresh: () => void} => {
  const [poorMansRefreshCount, setPoorMansRefreshCount] = useState(0);
  const req = useMemo(() => {
    return {
      project_id: projectIdFromParts({
        entity: opVersion.entity,
        project: opVersion.project,
      }),
      filter: {
        latest_only: true,
      },
      poorMansRefreshCount,
    };
  }, [opVersion.entity, opVersion.project, poorMansRefreshCount]);
  const scorers = useCollectionObjects('ActionDispatchFilter', req).sort(
    (a, b) => {
      return (
        convertISOToDate(a.created_at).getTime() -
        convertISOToDate(b.created_at).getTime()
      );
    }
  );
  const refresh = () => {
    setPoorMansRefreshCount(poorMansRefreshCount + 1);
  };
  return {scorers, refresh};
};

export const OpOnlineScorersTab: React.FC<{
  opVersion: OpVersionSchema;
}> = ({opVersion}) => {
  const req = useMemo(() => {
    return {
      project_id: projectIdFromParts({
        entity: opVersion.entity,
        project: opVersion.project,
      }),
      filter: {
        latest_only: true,
      },
    };
  }, [opVersion.entity, opVersion.project]);
  const availableActions = useCollectionObjects('ConfiguredAction', req);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const {scorers: onlineScorers, refresh} =
    useOnlineScorersForOpVersion(opVersion);

  const handleOpenModal = () => {
    setIsModalOpen(true);
  };

  const handleCloseModal = (didSave: boolean) => {
    refresh();
    setIsModalOpen(false);
  };

  const columns = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      renderCell: (params: any) => {
        return <SmallRef nameOnly objRef={parseRef(params.value)} />;
      },
    },
    {field: 'sampleRate', headerName: 'Sample Rate', flex: 1},
    {
      field: 'configuredActionRef',
      headerName: 'Configured Action',
      flex: 1,
      renderCell: (params: any) => {
        return <SmallRef nameOnly objRef={parseRef(params.value)} />;
      },
    },
    {field: 'disabled', headerName: 'Disabled', flex: 1},
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
        name: scorerRef,
        createdAt: convertISOToDate(scorer.created_at),
        disabled: scorer.val.disabled,
        sampleRate: scorer.val.sample_rate,
        configuredActionRef: scorer.val.configured_action_ref,
        // Map other fields as needed
      };
    });

  const actionRefs = useMemo(() => {
    return availableActions.map(action => {
      return objectVersionKeyToRefUri({
        scheme: 'weave',
        weaveKind: 'object',
        entity: opVersion.entity,
        project: opVersion.project,
        objectId: action.object_id,
        versionHash: action.digest,
        path: '',
      });
    });
  }, [availableActions, opVersion.entity, opVersion.project]);

  const inputSchema = useMemo(() => {
    const base = ActionDispatchFilterSchema.merge(
      z.object({
        op_name: z.literal(opVersion.opId),
      })
    );
    if (actionRefs.length === 0) {
      return base;
    }

    return base.merge(
      z.object({
        configured_action_ref: z.enum(
          actionRefs as unknown as [string, ...string[]]
        ),
      })
    );
  }, [actionRefs, opVersion.opId]);

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
        rowHeight={34}
        sx={{
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'inherit',
          },
          '& .MuiDataGrid-cell': {
            lineHeight: '22px',
          },
        }}
      />
      <NewOnlineOpScorerModal
        entity={opVersion.entity}
        project={opVersion.project}
        collectionDef={{
          name: 'ActionDispatchFilter',
          schema: inputSchema,
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
  onClose: (didSave: boolean) => void;
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
    const opName = parsedAction.data.op_name;
    const actionRef = parsedAction.data.configured_action_ref;
    const actionName = parseRef(actionRef).artifactName;
    let objectId = `${opName}-${actionName}`;
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
        setConfig({});
        onClose(true);
      });
  };

  const [isValid, setIsValid] = useState(false);

  return (
    <ReusableDrawer
      open={isOpen}
      title="Configure online scorer"
      onClose={() => onClose(false)}
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
