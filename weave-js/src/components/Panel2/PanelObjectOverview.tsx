import {
  constString,
  opCount,
  opObjectKeyTypes,
  opPick,
  varNode,
} from '@wandb/weave/core';
import React from 'react';

import * as Panel2 from './panel';
import {defaultFacet} from './PanelFacet';
import PanelFacet from './PanelFacet/Component';
import * as TableState from './PanelTable/tableState';

const inputType = {type: 'typedDict' as const, propertyTypes: {}};

type PanelObjectOverviewProps = Panel2.PanelProps<typeof inputType>;

export const PanelObjectOverview: React.FC<
  PanelObjectOverviewProps
> = props => {
  const keyTypes = opObjectKeyTypes({obj: props.input});

  const exampleRow = TableState.getExampleRow(keyTypes);

  let facet = defaultFacet();
  facet = {
    ...facet,
    table: TableState.updateColumnSelect(
      facet.table,
      facet.dims.x,
      opPick({
        obj: varNode(exampleRow.type, 'row'),
        key: constString('type'),
      })
    ),
  };
  facet = {
    ...facet,
    table: TableState.updateColumnSelect(
      facet.table,
      facet.dims.select,
      opCount({arr: varNode(props.input.type, 'row')})
    ),
  };
  facet = {
    ...facet,
    padding: 4,
  };

  return (
    <PanelFacet
      input={keyTypes as any}
      context={props.context}
      updateContext={props.updateContext}
      config={facet}
      // Get rid of updateConfig
      updateConfig={() => console.log('HELLO')}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'object-overview',
  Component: PanelObjectOverview,
  inputType,
};
