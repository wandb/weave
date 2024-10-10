import {Box} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {
  DragDropState,
  DragSource,
} from '@wandb/weave/common/containers/DragDropContainer';
import {DragHandle} from '@wandb/weave/common/containers/DragDropContainer/DragHandle';
import {Button} from '@wandb/weave/components/Button';
import {Pill} from '@wandb/weave/components/Tag';
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
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {
  BOX_RADIUS,
  CIRCLE_SIZE,
  EVAL_DEF_HEIGHT,
  STANDARD_BORDER,
} from '../../ecpConstants';
import {EvaluationComparisonState, getBaselineCallId} from '../../ecpState';
import {HorizontalBox} from '../../Layout';
import {DragHandleIcon} from './dragUtils';

export const EvaluationDefinition: React.FC<{
  state: EvaluationComparisonState;
  callId: string;
  ndx: number;
  onDragEnd?: (ctx: DragDropState, e: React.DragEvent) => void;
}> = props => {
  const {removeEvaluationCall, setSelectedCallIdsOrdered} =
    useCompareEvaluationsState();

  const menuOptions = useMemo(() => {
    return [
      {
        key: 'add-to-baseline',
        content: 'Set as baseline',
        onClick: () => {
          setSelectedCallIdsOrdered(prev => {
            if (prev == null) {
              return prev;
            }
            const index = prev.indexOf(props.callId);
            if (index === 0) {
              return prev;
            }
            const newOrder = [...prev];
            newOrder.splice(index, 1);
            newOrder.unshift(props.callId);
            return newOrder;
          });
        },
        disabled: props.callId === getBaselineCallId(props.state),
      },
      {
        key: 'remove',
        content: 'Remove',
        onClick: () => {
          removeEvaluationCall(props.callId);
        },
        disabled: Object.keys(props.state.data.evaluationCalls).length === 1,
      },
    ];
  }, [
    props.callId,
    props.state,
    removeEvaluationCall,
    setSelectedCallIdsOrdered,
  ]);

  const partRef = useMemo(() => ({id: `${props.ndx}`}), [props.ndx]);

  return (
    <DragSource
      partRef={partRef}
      onDragEnd={props.onDragEnd}
      draggingStyle={{opacity: 0.25}}>
      <HorizontalBox
        sx={{
          height: EVAL_DEF_HEIGHT,
          borderRadius: BOX_RADIUS,
          border: STANDARD_BORDER,
          paddingTop: '12px',
          paddingBottom: '12px',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
        <DragHandle
          partRef={partRef}
          style={{marginTop: '5px', marginRight: '-20px', marginLeft: '4px'}}>
          <DragHandleIcon />
        </DragHandle>
        <div style={{marginRight: '-8px'}}>
          <EvaluationCallLink {...props} />
        </div>
        {props.callId === getBaselineCallId(props.state) && (
          <div style={{marginRight: '-8px'}}>
            <Pill label="Baseline" color="teal" />
          </div>
        )}
        <div style={{marginLeft: '-6px', marginRight: '8px'}}>
          <PopupDropdown
            sections={[menuOptions]}
            trigger={
              <Button
                className="ml-4 rotate-90"
                icon="overflow-horizontal"
                size="small"
                variant="ghost"
              />
            }
          />
        </div>
      </HorizontalBox>
    </DragSource>
  );
};

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
