import {useWeaveContext} from '@wandb/weave/context';
import {isAssignableTo, varNode} from '@wandb/weave/core';
import _ from 'lodash';
import React from 'react';

import * as Panel2 from '../panel';
import {usePanelContext} from '../PanelContext';

const inputType = 'invalid';

type FrameVariablesTableProps = Panel2.PanelProps<typeof inputType>;

export const FrameVariablesTable: React.FC<
  FrameVariablesTableProps
> = props => {
  const weave = useWeaveContext();
  const panelContext = usePanelContext();

  return (
    <ul>
      {_.keys(panelContext.frame).map(varName => {
        const node = panelContext.frame[varName];
        if (
          node.nodeType === 'void' ||
          node.nodeType === 'var' ||
          isAssignableTo(node.type, {type: 'Group' as any}) ||
          isAssignableTo(node.type, {type: 'Panel' as any})
        ) {
          return null;
        }
        return (
          <li
            key={varName}
            onClick={() => {
              props.updateInput?.(varNode(node.type, varName) as any);
            }}>
            {varName}:{weave.typeToString(node.type)}
          </li>
        );
      })}
    </ul>
  );
};
