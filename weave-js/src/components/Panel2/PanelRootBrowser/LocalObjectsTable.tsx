import {useWeaveContext} from '@wandb/weave/context';
import {
  callOpVeryUnsafe,
  constFunction,
  constString,
  Node,
  opDropNa,
  opFilter,
  opMap,
  opStringEqual,
  opTypeName,
  opUnique,
  voidNode,
} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import React, {useCallback, useMemo} from 'react';

import * as Panel2 from '../panel';
import {PanelCard} from '../PanelCard';
import {
  getLocalArtifactDataTableState,
  useNewPanelFromRootQueryCallback,
  getLocalArtifactDataNode,
  opObjectsToName,
} from './util';

export const useLocalObjectsExist = () => {
  const dataNode = useMemo(() => getLocalArtifactDataNode(false), []);
  const typenames = useUniqueTypeNames(dataNode);
  return typenames.length > 0;
};

const useUniqueTypeNames = (allObjectsNode: Node) => {
  const unique = opUnique({
    arr: opDropNa({
      arr: opMap({
        arr: allObjectsNode,
        mapFn: constFunction(
          {row: {type: 'FilesystemArtifact' as any}},
          ({row}) =>
            opTypeName({
              type: callOpVeryUnsafe(
                'FilesystemArtifact-weaveType',
                {
                  artifact: row,
                },
                'type'
              ) as any,
            })
        ),
      }),
    }),
  });
  return ((useNodeValue(unique).result ?? []) as string[]).filter(
    name => name !== 'OpDef'
  );
};

const applyTypeFilter = (allObjectsNode: Node, typename: string) => {
  return opFilter({
    arr: allObjectsNode,
    filterFn: constFunction(
      {row: {type: 'FilesystemArtifact' as any}},
      ({row}) =>
        opStringEqual({
          lhs: opTypeName({
            type: callOpVeryUnsafe(
              'FilesystemArtifact-weaveType',
              {
                artifact: row,
              },
              'type'
            ) as any,
          }),
          rhs: constString(typename),
        })
    ),
  });
};

const inputType = 'invalid';

type LocalObjectsTableProps = Panel2.PanelProps<typeof inputType>;

export const LocalObjectsTable: React.FC<
  LocalObjectsTableProps & {isRoot?: boolean}
> = props => {
  const weave = useWeaveContext();
  const dataNode = useMemo(() => getLocalArtifactDataNode(false), []);

  const tableState = useMemo(() => {
    return getLocalArtifactDataTableState(dataNode, 'Object Name', weave);
  }, [dataNode, weave]);

  const makeNewDashboard = useNewPanelFromRootQueryCallback();

  const updateInputProxy = useCallback(
    (newInput: Node) => {
      const updateInput = props.updateInput;
      if (updateInput != null) {
        if (props.isRoot) {
          const name = 'dashboard-temp-view';
          makeNewDashboard(name, newInput, false, newDashExpr => {
            updateInput(newDashExpr as any);
          });
        } else {
          updateInput(newInput as any);
        }
      }
    },
    [makeNewDashboard, props]
  );

  const typenames = useUniqueTypeNames(dataNode);
  const cardConfig = Panel2.useConfigChild(
    'cardConfig',
    props.config,
    props.updateConfig,
    useMemo(
      () => ({
        title: constString('Local Objects'),
        subtitle: '',
        content: typenames.map((typename: string) => {
          return {
            name: typename,
            content: {
              vars: {},
              input_node: opObjectsToName(applyTypeFilter(dataNode, typename)),
              id: 'table',
              config: {
                simpleTable: true,
                tableState,
              },
            },
          };
        }),
      }),
      [dataNode, tableState, typenames]
    )
  );

  if (typenames.length === 0) {
    return <></>;
  }

  return (
    <PanelCard
      input={voidNode() as any}
      config={cardConfig.config}
      updateConfig={cardConfig.updateConfig}
      context={props.context}
      updateContext={props.updateContext}
      updateInput={updateInputProxy as any}
    />
  );
};
