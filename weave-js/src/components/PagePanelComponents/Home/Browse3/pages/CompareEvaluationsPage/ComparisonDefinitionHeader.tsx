import {Box, FormControl} from '@material-ui/core';
import {Autocomplete} from '@mui/material';
import React, {useMemo} from 'react';

import {Button} from '../../../../../Button';
import {StyledTextField} from '../../StyledTextField';
import {useCompareEvaluationsState} from './compareEvaluationsContext';
import {STANDARD_PADDING} from './constants';
import {EvaluationDefinition} from './EvaluationDefinition';
import {getOrderedCallIds} from './evaluationResults';
import {ScoreDimension} from './evaluations';
import {useEvaluationCallDimensions} from './initialize';
import {HorizontalBox} from './Layout';
import {EvaluationComparisonState} from './types';

export const ComparisonDefinition: React.FC<{
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
export const DefinitionText: React.FC<{text: string}> = props => {
  return <Box>{props.text}</Box>;
};
const dimensionToText = (dim: ScoreDimension): string => {
  return dim.scorerRef + '/' + dim.scoreKeyPath;
};
export const DimensionPicker: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const currDimension = props.state.comparisonDimension;
  const dimensions = useEvaluationCallDimensions(props.state);
  const {setComparisonDimension} = useCompareEvaluationsState();
  // console.log(dimensions);
  const dimensionMap = useMemo(() => {
    return Object.fromEntries(
      dimensions.map(dim => [dimensionToText(dim), dim])
    );
  }, [dimensions]);

  return (
    <FormControl>
      <Autocomplete
        size="small"
        disableClearable
        limitTags={1}
        value={dimensionToText(currDimension)}
        onChange={(event, newValue) => {
          // console.log('onChange', newValue);
          // TODO: THis is incorrect!
          // throw new Error('Not implemented');
          setComparisonDimension(dimensionMap[newValue]!);
        }}
        getOptionLabel={option => {
          // Not quite correct since there could be multiple scorers with the same name
          return dimensionMap[option]?.scoreKeyPath ?? option;
        }}
        options={Object.keys(dimensionMap)}
        renderInput={renderParams => (
          <StyledTextField
            {...renderParams}
            value={dimensionToText(currDimension)}
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
        // console.log('setting', props.callId);
        setBaselineEvaluationCallId(props.callId);
      }}
      icon="retry"
    />
  );
};
