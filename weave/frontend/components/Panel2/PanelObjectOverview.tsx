import React from 'react';
import * as Panel2 from './panel';
import * as Op from '@wandb/cg/browser/ops';
import * as CGReact from '@wandb/common/cgreact';
import * as TableState from './PanelTable/tableState';
import * as CG from '@wandb/cg/browser/graph';
import {defaultFacet, PanelFacet} from './PanelFacet';

const inputType = {type: 'typedDict' as const, propertyTypes: {}};

type PanelObjectOverviewProps = Panel2.PanelProps<typeof inputType>;

export const PanelObjectOverview: React.FC<PanelObjectOverviewProps> =
  props => {
    const keyTypes = Op.opObjectKeyTypes({obj: props.input});
    const keyTypesWithTypeQuery = CGReact.useNodeWithServerType(keyTypes);

    const exampleRow = TableState.getExampleRow(keyTypes);

    let facet = defaultFacet();
    facet = {
      ...facet,
      table: TableState.updateColumnSelect(
        facet.table,
        facet.dims.x,
        Op.opPick({
          obj: CG.varNode(exampleRow.type, 'row'),
          key: Op.constString('type'),
        })
      ),
    };
    facet = {
      ...facet,
      table: TableState.updateColumnSelect(
        facet.table,
        facet.dims.select,
        Op.opCount({arr: CG.varNode(props.input.type, 'row')})
      ),
    };
    facet = {
      ...facet,
      padding: 4,
    };

    if (keyTypesWithTypeQuery.loading) {
      return <div>-</div>;
    }

    return (
      <PanelFacet
        input={keyTypesWithTypeQuery.result as any}
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
