import {Box} from '@mui/material';
import React, {useMemo} from 'react';

import {
  MOON_300,
  MOON_600,
  MOON_800,
} from '../../../../../../../../common/css/color.styles';
import {hexToRGB} from '../../../../../../../../common/css/utils';
import {parseRef, WeaveObjectRef} from '../../../../../../../../react';
import {Icon, IconNames} from '../../../../../../../Icon';
import {objectRefDisplayName, SmallRef} from '../../../../smallRef/SmallRef';
import {CallLink, ObjectVersionLink} from '../../../common/Links';
import {useWFHooks} from '../../../wfReactInterface/context';
import {isObjDeleteError} from '../../../wfReactInterface/utilities';
import {ObjectVersionKey} from '../../../wfReactInterface/wfDataModelHooksInterface';
import {EvaluationComparisonState} from '../../ecpState';

export const EvaluationCallLink: React.FC<{
  callId: string;
  state: EvaluationComparisonState;
}> = props => {
  const evaluationCall = props.state.summary.evaluationCalls?.[props.callId];
  if (!evaluationCall) {
    return null;
  }
  const {entity, project} = props.state.summary;

  return (
    <CallLink
      entityName={entity}
      projectName={project}
      opName={evaluationCall.name}
      callId={props.callId}
      icon={<Icon name="filled-circle" color={evaluationCall.color} />}
      color={MOON_800}
    />
  );
};

export const EvaluationModelLink: React.FC<{
  callId: string;
  state: EvaluationComparisonState;
}> = props => {
  const {useObjectVersion} = useWFHooks();
  const evaluationCall = props.state.summary.evaluationCalls[props.callId];
  const objRef = useMemo(() => {
    return parseRef(evaluationCall.modelRef) as WeaveObjectRef;
  }, [evaluationCall.modelRef]);

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

  if (isObjDeleteError(objectVersion.error)) {
    return (
      <Box
        sx={{
          height: '22px',
          flex: 1,
          minWidth: 0,
          overflow: 'hidden',
          whiteSpace: 'nowrap',
          textOverflow: 'ellipsis',
          fontWeight: 500,
          textDecoration: 'line-through',
        }}>
        <Box display="flex" alignItems="center">
          <ModelIcon />
          {objectRefDisplayName(objRef).label}
        </Box>
      </Box>
    );
  }

  return (
    <ObjectVersionLink
      entityName={objRef.entityName}
      projectName={objRef.projectName}
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
  const evaluationCall = props.state.summary.evaluationCalls[props.callId];
  const evaluationObj =
    props.state.summary.evaluations[evaluationCall.evaluationRef];
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
