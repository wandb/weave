import {Box} from '@mui/material';
import React, {useMemo} from 'react';

import {
  MOON_300,
  MOON_800,
} from '../../../../../../../../../common/css/color.styles';
import {parseRef, WeaveObjectRef} from '../../../../../../../../../react';
import {Icon} from '../../../../../../../../Icon';
import {SmallRef} from '../../../../../smallRef/SmallRef';
import {objectRefDisplayName} from '../../../../../smallRef/SmallWeaveRef';
import {CallLink, ObjectVersionLink} from '../../../../common/Links';
import {StatusChip} from '../../../../common/StatusChip';
import {useWFHooks} from '../../../../wfReactInterface/context';
import {ComputedCallStatusType} from '../../../../wfReactInterface/traceServerClientTypes';
import {isObjDeleteError} from '../../../../wfReactInterface/utilities';
import {ObjectVersionKey} from '../../../../wfReactInterface/wfDataModelHooksInterface';
import {EvaluationComparisonState} from '../../ecpState';

export const EvaluationCallLink: React.FC<{
  callId: string;
  state: EvaluationComparisonState;
  callStatus?: ComputedCallStatusType;
}> = props => {
  const evaluationCall = props.state.summary.evaluationCalls?.[props.callId];
  if (!evaluationCall) {
    return null;
  }
  const {entity, project} = props.state.summary;

  const showStatusChip = props.callStatus === 'running';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        flexWrap: 'wrap',
      }}>
      <CallLink
        entityName={entity}
        projectName={project}
        opName={evaluationCall.name}
        callId={props.callId}
        icon={<Icon name="filled-circle" color={evaluationCall.color} />}
        color={MOON_800}
        allowWrap={true}
      />
      {showStatusChip && (
        <StatusChip
          value="running"
          iconOnly
          tooltipOverride="Evaluation in progress"
        />
      )}
    </div>
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
  const objectVersion = useObjectVersion({key: objVersionKey});

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
          <Icon name="filled-circle" color={evaluationCall.color} />
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
      icon={<Icon name="filled-circle" color={evaluationCall.color} />}
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
