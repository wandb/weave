// TODO:
//   filter stream to only show self matches
//   sort stream

import {useWeaveContext} from '@wandb/weave/context';
import {
  callOpVeryUnsafe,
  constString,
  Node,
  opArtifactName,
  opArtifactTypeArtifacts,
  opGet,
  opProjectArtifactType,
  opRootProject,
  Type,
  voidNode,
} from '@wandb/weave/core';
import {isWandbArtifactRef, parseRef, useNodeValue} from '@wandb/weave/react';
import React, {useEffect, useMemo} from 'react';

import {initPanel} from './ChildPanel';
import * as Panel2 from './panel';
import {usePanelContext} from './PanelContext';

// Don't show up in any suggestions for now.
const inputType = {type: 'OpDef'} as Type;

type PanelLabeledItemProps = Panel2.PanelProps<typeof inputType>;

export const PanelOpDef: React.FC<PanelLabeledItemProps> = props => {
  const weave = useWeaveContext();
  const {stack} = usePanelContext();
  const query = useNodeValue(props.input as any);
  const opDefRefStr = query.result;
  const entityProject = useMemo(() => {
    if (opDefRefStr == null) {
      return undefined;
    }
    const ref = parseRef(opDefRefStr);
    if (!isWandbArtifactRef(ref)) {
      return undefined;
    }
    return {
      entityName: ref.entityName,
      projectName: ref.projectName,
    };
  }, [opDefRefStr]);
  const streamTableNamesNode = useMemo(() => {
    if (entityProject == null) {
      return voidNode();
    }
    const projectNode = opRootProject({
      entityName: constString(entityProject.entityName),
      projectName: constString(entityProject.projectName),
    });
    const artifactTypeNode = opProjectArtifactType({
      project: projectNode,
      artifactType: constString('stream_table'),
    });
    return opArtifactName({
      artifact: opArtifactTypeArtifacts({
        artifactType: artifactTypeNode,
      }),
    });
  }, [entityProject]);
  const streamNamesQuery = useNodeValue(streamTableNamesNode);
  const streamNames: string[] = streamNamesQuery.result ?? [];
  // const [chosenStreamName, setChosenStreamName] = useState<string | undefined>(
  //   undefined
  // );
  const chosenStreamName = undefined;
  const streamName = chosenStreamName ?? streamNames[0];

  // const [panel, setPanel] = React.useState<ChildPanelConfig | undefined>();
  useEffect(() => {
    if (entityProject == null || streamName == null) {
      return;
    }
    const predsRefStr = `wandb-artifact:///${entityProject.entityName}/${entityProject.projectName}/${streamName}:latest/obj`;
    const streamTableRowsNode = callOpVeryUnsafe('stream_table-rows', {
      stream_table: opGet({
        uri: constString(predsRefStr),
      }),
    }) as Node;
    const refType = {
      type: 'FilesystemArtifactRef',
      _base_type: {
        type: 'Ref',
        objectType: 'any',
      },
      objectType: 'any',
    } as unknown as Type;
    streamTableRowsNode.type = {
      type: 'list',
      objectType: {
        type: 'typedDict',
        propertyTypes: {
          inputs: {
            type: 'typedDict',
            propertyTypes: {
              self: refType,
            },
          },
        },
      },
    };
    // const filtered = callOpVeryUnsafe('filter', {
    //   arr: streamTableRowsNode,
    //   filterFn: constFunction(
    //     {row: 'any'},
    //     ({row}) =>
    //       callOpVeryUnsafe('Ref-__eq__', {
    //         self: callOpVeryUnsafe('pick', {
    //           obj: row,
    //           key: constString('inputs.self'),
    //         }),
    //         other: constNodeUnsafe(refType, opDefRefStr),
    //       }) as any
    //   ),
    // }) as Node;
    // const counted = callOpVeryUnsafe('count', {
    //   arr: filtered,
    // }) as Node;
    const doInit = async () => {
      // const panel = await initPanel(
      await initPanel(weave, streamTableRowsNode, undefined, undefined, stack);
      // setPanel(panel);
    };
    doInit();
  }, [stack, weave, opDefRefStr, entityProject, streamName]);

  return (
    <div style={{width: '100%', height: '100%'}}>
      {opDefRefStr}
      {/* <div>
        Stream:{' '}
        <ModifiedDropdown
          value={streamName}
          onChange={(e, {value}) => {
            setChosenStreamName(value as string);
          }}
          options={streamNames.map(name => ({
            key: name,
            value: name,
            text: name,
          }))}
        />
      </div>
      <ChildPanel
        config={panel}
        updateConfig={() => console.log('UPDATE CONFIG')}
      /> */}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: false,
  id: 'PanelOpDef',
  Component: PanelOpDef,
  inputType,
};
