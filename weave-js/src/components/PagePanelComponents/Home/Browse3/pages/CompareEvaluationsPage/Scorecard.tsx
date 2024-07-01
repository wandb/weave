import {Box} from '@material-ui/core';
import React from 'react';

import {ValueViewNumber} from '../CallPage/ValueViewNumber';
import {EvaluationComparisonState} from './compareEvaluationsContext';
const STANDARD_PADDING = '16px';

export const ScoreCard: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const modelRefs: ['Baseline', 'Challenger'] = ['Baseline', 'Challenger'];
  const modelProps = {
    Model: {
      Baseline: 'Model A',
      Challenger: 'Model B',
    },
    Version: {
      Baseline: '1.0.0',
      Challenger: '1.0.0',
    },
    Author: {
      Baseline: 'Author A',
      Challenger: 'Author B',
    },
  };
  const scoreDefs = {
    score1: {
      metrics: [
        {key: 'score1.a.mean', unit: '', lowerIsBetter: true},
        {key: 'score1.b.mean', unit: '%', lowerIsBetter: false},
        {key: 'score1.c.mean', unit: ' ms', lowerIsBetter: true},
      ],
    },
    score2: {
      metrics: [
        {key: 'score2.a.true_fraction', unit: '', lowerIsBetter: false},
        {key: 'score2.b.true_fraction', unit: '%', lowerIsBetter: true},
        {key: 'score2.c.true_fraction', unit: ' ms', lowerIsBetter: false},
      ],
    },
    usage: {
      metrics: [
        // {key: 'tokens.requests', unit: '', lowerIsBetter: false},
        // {key: 'tokens.inputs', unit: '', lowerIsBetter: true},
        // {key: 'tokens.output', unit: '', lowerIsBetter: false},
        {key: 'tokens.total', unit: '', lowerIsBetter: false},
        {key: 'tokens.cost', unit: ' $', lowerIsBetter: false},
      ],
    },
    latency: {
      metrics: [{key: 'latency', unit: ' ms', lowerIsBetter: false}],
    },
  };
  const scores = {
    'score1.a.mean': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    'score1.b.mean': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    'score1.c.mean': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    'score2.a.true_fraction': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    'score2.b.true_fraction': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    'score2.c.true_fraction': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    'tokens.requests': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    'tokens.inputs': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    'tokens.output': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    'tokens.total': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    'tokens.cost': {
      Baseline: 0.5,
      Challenger: 0.6,
    },
    latency: {
      Baseline: 0.5,
      Challenger: 0.6,
    },
  };
  return (
    <Box
      sx={{
        width: '100%',
        flex: '0 0 auto',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
      }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr',
        }}>
        {/* Header Row */}
        <div></div>
        <div></div>
        <div
          style={{
            fontWeight: 'bold',
            // borderTopLeftRadius: '6px',
            // borderTop: '1px solid #ccc',
            // borderLeft: '1px solid #ccc',
          }}>
          Model A
        </div>
        <div
          style={{
            fontWeight: 'bold',
            // borderTopRightRadius: '6px',
            // borderTop: '1px solid #ccc',
            // borderRight: '1px solid #ccc',
          }}>
          Model B
        </div>
        <div></div>
        {/* Model Rows */}
        {Object.entries(modelProps).map(([prop, modelData]) => {
          return (
            <React.Fragment key={prop}>
              <div></div>
              <div
                style={{
                  fontWeight: 'bold',
                  textAlign: 'right',
                  paddingRight: '10px',
                }}>
                {prop}
              </div>
              {modelRefs.map((model, mNdx) => {
                return <div key={mNdx}>{modelData[model]}</div>;
              })}
              <div></div>
            </React.Fragment>
          );
        })}
        {/* Score Rows */}
        {Object.entries(scoreDefs).map(([key, def]) => {
          return (
            <React.Fragment key={key}>
              <div
                key={key}
                style={{
                  // vertical span length of metric
                  gridRowEnd: `span ${def.metrics.length}`,
                  borderTop: '1px solid #ccc',
                  fontWeight: 'bold',
                }}>
                {key}
              </div>
              {def.metrics.map((metric, metricNdx) => {
                return (
                  <React.Fragment key={metricNdx}>
                    <div
                      style={{
                        borderTop: metricNdx === 0 ? '1px solid #ccc' : '',
                      }}>
                      {metric.key}
                    </div>
                    {modelRefs.map((model, mNdx) => {
                      return (
                        <div
                          key={mNdx}
                          style={{
                            borderTop: metricNdx === 0 ? '1px solid #ccc' : '',
                          }}>
                          <ValueViewNumber
                            fractionDigits={4}
                            value={((scores as any)[metric.key] as any)[model]}
                          />
                          {metric.unit}
                        </div>
                      );
                    })}
                    <div
                      style={{
                        borderTop: metricNdx === 0 ? '1px solid #ccc' : '',
                      }}>
                      <ValueViewNumber
                        fractionDigits={4}
                        value={
                          ((scores as any)[metric.key] as any)[modelRefs[0]] -
                          ((scores as any)[metric.key] as any)[modelRefs[1]]
                        }
                      />
                      {metric.unit}
                    </div>
                  </React.Fragment>
                );
              })}
            </React.Fragment>
          );
        })}
      </div>
    </Box>
  );
};
