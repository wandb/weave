import {useWeaveContext} from '@wandb/weave/context';
import {constString, Node, opGet} from '@wandb/weave/core';
import {useMakeMutation, useNodeValueExecutor} from '@wandb/weave/react';
import React, {useCallback, useMemo, useState} from 'react';
import {Button, Input, Modal} from 'semantic-ui-react';

import * as Panel2 from '../panel';
import {PanelTable, RowActionItems} from '../PanelTable/PanelTable';
import {
  getLocalArtifactDataNode,
  getLocalArtifactDataTableState,
  opObjectNameToURI,
  opObjectsToName,
} from './util';

const inputType = 'invalid';

type LocalDashboardsTableProps = Panel2.PanelProps<typeof inputType>;

const useOnDeleteCallback = () => {
  const executor = useNodeValueExecutor();
  const makeMutation = useMakeMutation();
  return (rowNode: Node, rowIndex: number) => {
    executor(opObjectNameToURI(rowNode)).then(res => {
      const dashExpr = opGet({
        uri: constString(res),
      });
      makeMutation(dashExpr, 'delete_artifact', {});
    });
  };
};
export const LocalDashboardsTable: React.FC<
  LocalDashboardsTableProps
> = props => {
  const weave = useWeaveContext();
  const dataNode = useMemo(
    () => opObjectsToName(getLocalArtifactDataNode(true)),
    []
  );

  const tableState = useMemo(() => {
    return getLocalArtifactDataTableState(dataNode, 'Dashboard Name', weave);
  }, [dataNode, weave]);

  const tableConfig = Panel2.useConfigChild(
    'tableConfig',
    props.config,
    props.updateConfig,
    useMemo(
      () => ({
        simpleTable: true,
        tableState,
      }),
      [tableState]
    )
  );

  const onDeleteCallback = useOnDeleteCallback();

  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [currentName, setCurrentName] = useState('');
  const executor = useNodeValueExecutor();
  const makeMutation = useMakeMutation();

  const onRenameCallback = useCallback(
    (rowNode: Node, rowIndex: number) => {
      executor(rowNode).then(res => {
        setCurrentName(res);
        setRenameModalOpen(true);
      });
    },
    [executor]
  );

  const onRenameModalCallback = useCallback(
    (newName: string) => {
      makeMutation(
        opGet({
          uri: constString(`local-artifact:///${currentName}/obj`),
        }),
        'rename_artifact',
        {name: constString(newName)}
      ).then(() => {
        setCurrentName('');
        setRenameModalOpen(false);
      });
    },
    [currentName, makeMutation]
  );

  const rowActions: RowActionItems = useMemo(() => {
    return [
      {
        key: 'delete',
        content: 'Delete',
        icon: 'trash',
        onClick: onDeleteCallback,
      },
      {
        key: 'rename',
        content: 'Rename',
        icon: 'pencil',
        onClick: onRenameCallback,
      },
    ];
  }, [onDeleteCallback, onRenameCallback]);

  return (
    <>
      <RenameDashboardModal
        key={currentName}
        open={renameModalOpen}
        onClose={() => setRenameModalOpen(false)}
        onRename={onRenameModalCallback}
        curName={currentName}
      />
      <PanelTable
        input={dataNode as any}
        config={tableConfig.config}
        updateConfig={tableConfig.updateConfig}
        context={props.context}
        updateContext={props.updateContext}
        updateInput={props.updateInput as any}
        rowActions={rowActions}
      />
    </>
  );
};

interface RenameDashboardModalProps {
  curName: string;
  open: boolean;
  onClose: () => void;
  onRename: (newName: string) => void;
}

const RenameDashboardModal: React.FC<RenameDashboardModalProps> = props => {
  const [newName, setNewName] = useState(props.curName);
  return (
    <Modal
      open={props.open}
      size="mini"
      content={
        <div
          style={{padding: 24, display: 'flex', flexDirection: 'column'}}
          onKeyUp={e => {
            if (e.key === 'Enter') {
              props.onRename(newName);
            }
          }}>
          <div style={{marginBottom: 24, fontWeight: 'bold'}}>Rename</div>
          <Input
            style={{marginBottom: 24}}
            value={newName}
            onChange={(e, {value}) => setNewName(value)}
          />
          <div style={{display: 'flex', justifyContent: 'space-between'}}>
            <Button onClick={() => props.onClose()}>Cancel</Button>
            <Button primary onClick={() => props.onRename(newName)}>
              Rename
            </Button>
          </div>
        </div>
      }
    />
  );
};
