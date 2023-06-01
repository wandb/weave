import _ from 'lodash';
import React, {useMemo} from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';
import * as S from './PanelString.styles';
import {TooltipTrigger} from './Tooltip';

const inputType = {
  type: 'union' as const,
  members: [
    {
      type: 'dict' as const,
      objectType: {
        type: 'union' as const,
        members: ['none' as const, 'string' as const],
      },
    },
    {
      type: 'list' as const,
      maxLength: 25,
      objectType: {
        type: 'union' as const,
        members: ['none' as const, 'string' as const],
      },
    },
  ],
};

type PanelStringCompareProps = Panel2.PanelProps<typeof inputType>;

const PanelStringCompare: React.FC<PanelStringCompareProps> = props => {
  const path = props.input;
  const nodeValueQuery = CGReact.useNodeValue<
    | {
        type: 'dict';
        objectType: {
          type: 'union';
          members: Array<'string' | 'none'>;
        };
        maxLength?: undefined;
      }
    | {
        type: 'list';
        maxLength: number;
        objectType: {
          type: 'union';
          members: Array<'string' | 'none'>;
        };
      }
  >(path);

  const data = useMemo(() => {
    if (nodeValueQuery.loading) {
      return [];
    }

    if (_.isArray(nodeValueQuery.result)) {
      return nodeValueQuery.result.map((item, ndx) => {
        return {key: '' + ndx, value: '' + (item ?? '')};
      });
    } else {
      return Object.entries(nodeValueQuery.result ?? {}).map(
        ([key, value]) => ({
          key,
          value: '' + value,
        })
      );
    }
  }, [nodeValueQuery]);

  const dataAsString = useMemo(() => {
    return data
      .map(({key, value}) => {
        return `${key}: ${value == null ? '-' : value}`;
      })
      .join('\n');
  }, [data]);

  if (!data.length) {
    return <div>-</div>;
  }

  return (
    <TooltipTrigger
      copyableContent={dataAsString}
      content={
        <S.PreformattedProportionalString>
          {dataAsString}
        </S.PreformattedProportionalString>
      }>
      <S.StringContainer style={{whiteSpace: 'pre-line', lineHeight: '1.25em'}}>
        <S.StringItem>{dataAsString}</S.StringItem>
      </S.StringContainer>
    </TooltipTrigger>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'string-compare',
  Component: PanelStringCompare,
  inputType,
};
