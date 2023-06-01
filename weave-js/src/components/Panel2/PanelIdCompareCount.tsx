import * as _ from 'lodash';
import React from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'dict' as const,
    objectType: {
      type: 'union' as const,
      members: ['none' as const, 'id' as const],
    },
  },
};

type PanelIdCompareProps = Panel2.PanelProps<typeof inputType>;

const PanelIdCompareCount: React.FC<PanelIdCompareProps> = props => {
  const nodeValue = CGReact.useNodeValue(props.input);
  if (nodeValue.loading) {
    return <div>-</div>;
  }
  const counts: {[key: string]: number} = {};
  const arr = nodeValue.result;
  if (arr.length > 0) {
    for (const key of Object.keys(arr[0])) {
      counts[key] = 0;
    }
    for (const row of arr) {
      for (const key of Object.keys(row)) {
        counts[key] += row[key] != null ? 1 : 0;
      }
    }
  }
  return (
    <div>
      {_.map(counts, (count, key) => (
        <div key={key}>
          {key}: {count} ids
        </div>
      ))}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'id-compare-count',
  Component: PanelIdCompareCount,
  inputType,
};
