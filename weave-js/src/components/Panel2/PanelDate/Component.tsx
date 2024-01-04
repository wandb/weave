import * as TypeHelpers from '@wandb/weave/core';
import moment from 'moment';
import React from 'react';

import * as CGReact from '../../../react';
import * as Panel2 from '../panel';
import {Panel2Loader} from '../PanelComp';
import * as S from '../PanelString.styles';
import {inputType} from './common';

type PanelDateProps = Panel2.PanelProps<typeof inputType, {format?: string}>;

const PanelDate: React.FC<PanelDateProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input as any);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }

  if (nodeValueQuery.result == null) {
    return <div>-</div>;
  }

  const nodeType = TypeHelpers.nullableTaggableValue(props.input.type);
  let date = nodeValueQuery.result as Date | number;

  if (
    !TypeHelpers.isSimpleTypeShape(nodeType) &&
    nodeType.type === 'timestamp'
  ) {
    // TODO: when other units are supported, need to do conversion.
    date = moment(date as number).toDate();
  }
  let dateS = [moment(date).format('yyyy-MM-DD HH:mm:ss')].join(' ');

  if (props.config?.format != null) {
    dateS = moment(date).format(props.config.format);
  }

  return (
    <S.StringContainer>
      <S.StringItem>{dateS}</S.StringItem>
    </S.StringContainer>
  );
};

export default PanelDate;
