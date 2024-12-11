import {Box} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import React, {useMemo} from 'react';

import {
  MOON_300,
  MOON_600,
  MOON_800,
} from '../../../../../../../../common/css/color.styles';
import {hexToRGB} from '../../../../../../../../common/css/utils';
import {parseRef, WeaveObjectRef} from '../../../../../../../../react';
import {Icon, IconNames} from '../../../../../../../Icon';
import {SmallRef} from '../../../../../Browse2/SmallRef';
import {CallLink, ObjectVersionLink} from '../../../common/Links';
import {useWFHooks} from '../../../wfReactInterface/context';
import {ObjectVersionKey} from '../../../wfReactInterface/wfDataModelHooksInterface';
import {CIRCLE_SIZE} from '../../ecpConstants';
import {EvaluationComparisonState} from '../../ecpState';

export const EvaluationCallLink: React.FC<{
  callId: string;
  state: EvaluationComparisonState;
}> = props => {
  const evaluationCall = props.state.data.evaluationCalls?.[props.callId];
  if (!evaluationCall) {
    return null;
  }
  const {entity, project} = props.state.data;

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
  const {useObjectVersion} = useWFHooks();
  const evaluationCall = props.state.data.evaluationCalls[props.callId];
  const modelObj = props.state.data.models[evaluationCall.modelRef];
  const objRef = useMemo(
    () => parseRef(modelObj.ref) as WeaveObjectRef,
    [modelObj.ref]
  );
  const objVersionKey = useMemo(() => {
    return {
      scheme: 'weave',
      entity: objRef.entityName,
      project: objRef.projectName,
      weaveKind: objRef.weaveKind,
      objectId: objRef.artifactName,
      versionHash: objRef.artifactVersion,
      path: '',
      refExtra: objRef.artifactRefExtra,
    } as ObjectVersionKey;
  }, [
    objRef.artifactName,
    objRef.artifactRefExtra,
    objRef.artifactVersion,
    objRef.entityName,
    objRef.projectName,
    objRef.weaveKind,
  ]);
  const objectVersion = useObjectVersion(objVersionKey);

  return (
    <ObjectVersionLink
      entityName={modelObj.entity}
      projectName={modelObj.project}
      objectName={objRef.artifactName}
      version={objRef.artifactVersion}
      versionIndex={objectVersion.result?.versionIndex ?? 0}
      color={MOON_800}
      icon={<ModelIcon />}
    />
  );
};

export const EvaluationDatasetLink: React.FC<{
  callId: string;
  state: EvaluationComparisonState;
}> = props => {
  const evaluationCall = props.state.data.evaluationCalls[props.callId];
  const evaluationObj =
    props.state.data.evaluations[evaluationCall.evaluationRef];
  const parsed = parseRef(evaluationObj.datasetRef);
  if (!parsed) {
    return null;
  }
  return <SmallRef objRef={parsed} />;
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
        width: '1px',
        height: '100%',
        backgroundColor: MOON_300,
      }}
    />
  );
};
