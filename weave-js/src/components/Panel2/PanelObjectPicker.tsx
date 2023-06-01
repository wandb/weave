import {
  constNumber,
  constString,
  isTaggedValueLike,
  isVoidNode,
  listObjectType,
  Node,
  NodeOrVoidNode,
  opLimit,
  opOffset,
  opRunName,
  taggedValueValueType,
  Type,
  voidNode,
} from '@wandb/weave/core';
import React, {useCallback, useMemo, useState} from 'react';
import {Icon} from 'semantic-ui-react';
import styled from 'styled-components';

import {useEach} from '../../react';
import {ChildPanel} from './ChildPanel';
import * as Panel from './panel';

const inputType = {type: 'list' as const, objectType: 'any' as const};
interface PanelObjectPickerConfig {
  // This is a function of input, that produces a single item from
  // input.
  // Well, that's what Select() does. But it produces it as a const.
  //
  // Is this the same?
  label: string;
  choice: NodeOrVoidNode;
}
type PanelObjectPickerProps = Panel.PanelProps<
  typeof inputType,
  PanelObjectPickerConfig
>;

const Picker = styled.div``;

const Item = styled.div<{preferHorizontal?: boolean}>`
  display: flex;
  align-items: center;
  cursor: pointer;
`;

const Label = styled.div`
  margin-right: 8px;
`;

const Value = styled.div`
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
`;

const MenuItem = styled.div<{preferHorizontal?: boolean}>`
  cursor: pointer;
  padding-left: 16px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  &:hover {
    background-color: #eee;
  }
`;

const objValueType = (listType: Type): Type => {
  let objType = listObjectType(listType);
  if (isTaggedValueLike(objType)) {
    objType = taggedValueValueType(objType);
  }
  return objType;
};

export const PanelObjectPicker: React.FC<PanelObjectPickerProps> = props => {
  const {config, updateConfig} = props;
  const [expanded, setExpanded] = useState(false);
  // const updateVal = useCallback(
  //   (newVal: number) => updateConfig({...config, value: newVal}),
  //   [config, updateConfig]
  // );
  const inputPageNode = useMemo(
    () =>
      opLimit({
        arr: opOffset({arr: props.input, offset: constNumber(0)}),
        limit: constNumber(10),
      }),
    [props.input]
  );
  const itemNodes = useEach(inputPageNode as any);
  const choose = useCallback(
    (choice: any) => {
      updateConfig({choice});
      // setExpanded(false);
    },
    [updateConfig]
  );
  let displayFunction = (node: NodeOrVoidNode) => node;
  if (objValueType(props.input.type) === 'run') {
    displayFunction = (node: NodeOrVoidNode) =>
      isVoidNode(node)
        ? constString('-') // TODO(np): What to show when node is void?
        : opRunName({run: node as Node});
  }

  return (
    <Picker>
      <Item onClick={() => setExpanded(!expanded)}>
        <Icon
          onClick={(e: React.SyntheticEvent<HTMLInputElement>) =>
            console.log('bla')
          }
          size="mini"
          name={`chevron ${expanded ? 'down' : 'right'}`}
        />
        <Label>{props.config?.label}: </Label>
        <Value>
          <ChildPanel
            config={{
              vars: {},
              input_node: displayFunction(config?.choice ?? voidNode()),
              id: '',
              config: {},
            }}
            updateConfig={(newConfig: any) =>
              console.warn('DROPPING CONFIG IN PANEL OBJECT PICKER')
            }
          />
        </Value>
      </Item>
      {/* <div>Filter expression editor.</div> */}
      {expanded && (
        <div>
          {itemNodes.result.map((itemNode: any) => {
            return (
              <MenuItem onClick={() => choose(itemNode)}>
                <ChildPanel
                  config={{
                    vars: {},
                    input_node: displayFunction(itemNode),
                    id: '',
                    config: undefined,
                  }}
                  updateConfig={(newConfig: any) =>
                    console.warn('DROPPING CONFIG IN PANEL OBJECT PICKER')
                  }
                />
              </MenuItem>
            );
          })}
        </div>
      )}
    </Picker>
  );
};

export const Spec: Panel.PanelSpec = {
  hidden: true,
  id: 'ObjectPicker',
  Component: PanelObjectPicker,
  inputType,
};
