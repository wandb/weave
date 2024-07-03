import {FormControl} from '@material-ui/core';
import {Autocomplete} from '@mui/material';
import React, {useMemo} from 'react';

import {Button} from '../../../../../../../Button';
import {StyledTextField} from '../../../../StyledTextField';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {STANDARD_PADDING} from '../../ecpConstants';
import {getOrderedCallIds} from '../../ecpState';
import {EvaluationComparisonState} from '../../ecpTypes';
import {dimensionId, dimensionLabel} from '../../ecpUtil';
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

export const DimensionPicker: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const currDimension = props.state.comparisonDimension;
  const dimensions = useMemo(() => {
    return [
      ...Object.values(props.state.data.derivedMetricDimensions),
      ...Object.values(props.state.data.scorerMetricDimensions),
    ];
  }, [
    props.state.data.derivedMetricDimensions,
    props.state.data.scorerMetricDimensions,
  ]);
  const {setComparisonDimension} = useCompareEvaluationsState();
  // console.log(dimensions);
  const dimensionMap = useMemo(() => {
    return Object.fromEntries(dimensions.map(dim => [dimensionId(dim), dim]));
  }, [dimensions]);

  return (
    <FormControl>
      <Autocomplete
        size="small"
        disableClearable
        limitTags={1}
        value={currDimension ? dimensionId(currDimension) : undefined}
        onChange={(event, newValue) => {
          setComparisonDimension(dimensionMap[newValue]!);
        }}
        getOptionLabel={option => {
          return dimensionLabel(dimensionMap[option]!);
        }}
        options={Object.keys(dimensionMap)}
        renderInput={renderParams => (
          <StyledTextField
            {...renderParams}
            value={currDimension ? dimensionLabel(currDimension) : ''}
            label={'Dimension'}
            sx={{width: '300px'}}
          />
        )}
      />
    </FormControl>
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
