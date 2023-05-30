import React from 'react';
import Measure from 'react-measure';

import {ComputeGraphViz} from './ComputeGraphViz';
import * as Panel2 from './panel';

const inputType = 'any' as const;
type PanelExpressionGraphProps = Panel2.PanelProps<typeof inputType>;

export const PanelExpressionGraph: React.FC<
  PanelExpressionGraphProps
> = props => {
  const [bounds, setBounds] = React.useState({width: 400, height: 400});
  return (
    <Measure
      bounds
      onResize={contentRect => {
        if (contentRect.bounds != null) {
          setBounds(contentRect.bounds);
        }
      }}>
      {({measureRef}) => (
        <div
          ref={measureRef}
          style={{
            height: '100%',
            width: '100%',
            overflow: 'hidden',
          }}>
          <ComputeGraphViz
            node={props.input}
            width={bounds.width}
            height={bounds.height}
          />
        </div>
      )}
    </Measure>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'debug-expression-graph',
  Component: PanelExpressionGraph,
  inputType,
};
