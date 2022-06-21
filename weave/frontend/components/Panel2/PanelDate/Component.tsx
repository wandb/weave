import React from 'react';
import * as CGReact from '@wandb/common/cgreact';
import * as Types from '@wandb/cg/browser/model/types';
import moment from 'moment';
import * as Panel2 from '../panel';
import {inputType} from './common';
type PanelDateProps = Panel2.PanelProps<typeof inputType>;

const PanelDate: React.FC<PanelDateProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input as any);
  if (nodeValueQuery.loading) {
    return <div>-</div>;
  }
  const nodeType = Types.nullableTaggableValue(props.input.type);
  let date = nodeValueQuery.result as Date | number;

  if (!Types.isSimpleType(nodeType) && nodeType.type === 'timestamp') {
    // TODO: when other units are supported, need to do conversion.
    date = moment.utc(date as number).toDate();
  }
  const dateS = [
    moment(date).format('MMMM Do, YYYY'),
    'at',
    moment(date).format('h:mm:ss a'),
  ].join(' ');
  return <div>{dateS}</div>;
};

export default PanelDate;
