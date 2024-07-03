import {Box} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import React from 'react';

import {
  MOON_300,
  MOON_600,
  MOON_800,
} from '../../../../../../../../common/css/color.styles';
import {hexToRGB} from '../../../../../../../../common/css/utils';
import {Icon, IconNames} from '../../../../../../../Icon';
import {CallLink, ObjectVersionLink} from '../../../common/Links';
import {
  BOX_RADIUS,
  CIRCLE_SIZE,
  EVAL_DEF_HEIGHT,
  STANDARD_BORDER,
} from '../../ecpConstants';
import {EvaluationComparisonState} from '../../ecpTypes';
import {HorizontalBox} from '../../Layout';

export const EvaluationDefinition: React.FC<{
  state: EvaluationComparisonState;
  callId: string;
}> = props => {
  return (
    <HorizontalBox
      sx={{
        height: EVAL_DEF_HEIGHT,
        borderRadius: BOX_RADIUS,
        border: STANDARD_BORDER,
        padding: '12px',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
      <EvaluationCallLink {...props} />
      <VerticalBar />
      <EvaluationModelLink {...props} />
    </HorizontalBox>
  );
};
export const EvaluationCallLink: React.FC<{
  callId: string;
  state: EvaluationComparisonState;
}> = props => {
  // console.log(props.state, props.callId);
  const evaluationCall = props.state.data.evaluationCalls[props.callId];
  const [entity, project] =
    evaluationCall._rawEvaluationTraceData.project_id.split('/');
  return (
    <CallLink
      entityName={entity}
      projectName={project}
      opName={evaluationCall.name}
      callId={props.callId}
      icon={
        <Circle
          sx={{
            color: evaluationCall.color,
            height: CIRCLE_SIZE,
          }}
        />
      }
      color={MOON_800}
    />
  );
};

export const EvaluationModelLink: React.FC<{
  callId: string;
  state: EvaluationComparisonState;
}> = props => {
  const evaluationCall = props.state.data.evaluationCalls[props.callId];
  const modelObj = props.state.data.models[evaluationCall.modelRef];

  return (
    <ObjectVersionLink
      entityName={modelObj.entity}
      projectName={modelObj.project}
      objectName={modelObj._rawModelObject.object_id}
      version={modelObj._rawModelObject.digest}
      versionIndex={modelObj._rawModelObject.version_index}
      color={MOON_800}
      icon={<ModelIcon />}
    />
  );
};

const ModelIcon: React.FC = () => {
  return (
    <Box
      mr="4px"
      bgcolor={hexToRGB(MOON_300, 0.48)}
      sx={{
        height: '22px',
        width: '22px',
        borderRadius: '16px',
        display: 'flex',
        flex: '0 0 22px',
        justifyContent: 'center',
        alignItems: 'center',
        color: MOON_600,
      }}>
      <Icon name={IconNames.Model} width={14} height={14} />
    </Box>
  );
};
export const VerticalBar: React.FC = () => {
  return (
    <div
      style={{
        width: '2px',
        height: '100%',
        backgroundColor: MOON_300,
      }}
    />
  );
};
