import React, {useMemo} from 'react';

import {Button} from '../../../../../../../Button';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {STANDARD_PADDING} from '../../ecpConstants';
import {getOrderedCallIds} from '../../ecpState';
import {EvaluationComparisonState} from '../../ecpState';
import {HorizontalBox} from '../../Layout';
import {EvaluationDefinition} from './EvaluationDefinition';

export const ComparisonDefinitionSection: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const evalCallIds = useMemo(
    () => getOrderedCallIds(props.state),
    [props.state]
  );

  return (
    <HorizontalBox
      sx={{
        alignItems: 'center',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
        width: '100%',
        overflow: 'auto',
      }}>
      {evalCallIds.map((key, ndx) => {
        return (
          <React.Fragment key={key}>
            {ndx !== 0 && <SwapPositionsButton callId={key} />}
            <EvaluationDefinition state={props.state} callId={key} />
          </React.Fragment>
        );
      })}
    </HorizontalBox>
  );
};

const SwapPositionsButton: React.FC<{callId: string}> = props => {
  const {setBaselineEvaluationCallId} = useCompareEvaluationsState();
  return (
    <Button
      size="medium"
      variant="quiet"
      onClick={() => {
        setBaselineEvaluationCallId(props.callId);
      }}
      icon="retry"
    />
  );
};
