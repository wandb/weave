import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {parseRef, WeaveObjectRef} from '@wandb/weave/react';
import React, {useMemo} from 'react';

import {Button} from '../../../../../../../Button';
import {
  DEFAULT_FILTER_CALLS,
  DEFAULT_SORT_CALLS,
} from '../../../CallsPage/CallsTable';
import {useCallsForQuery} from '../../../CallsPage/callsTableQuery';
import {useEvaluationsFilter} from '../../../CallsPage/evaluationsFilter';
import {Id} from '../../../common/Id';
import {useWFHooks} from '../../../wfReactInterface/context';
import {ObjectVersionKey} from '../../../wfReactInterface/wfDataModelHooksInterface';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {STANDARD_PADDING} from '../../ecpConstants';
import {getOrderedCallIds} from '../../ecpState';
import {EvaluationComparisonState} from '../../ecpState';
import {HorizontalBox} from '../../Layout';
import {EvaluationDefinition, VerticalBar} from './EvaluationDefinition';

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
            <EvaluationDefinition state={props.state} callId={key} />
          </React.Fragment>
        );
      })}
      <AddEvaluationButton state={props.state} />
    </HorizontalBox>
  );
};

const EvalMenuOption: React.FC<{
  callId: string;
  callName: string;
  modelRef: string;
}> = props => {
  const {useObjectVersion} = useWFHooks();
  const objRef = useMemo(
    () => parseRef(props.modelRef) as WeaveObjectRef,
    [props.modelRef]
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
    <Tailwind>
      <div className="flexbox flex items-center">
        <span>{props.callName}</span>
        <Id id={props.callId} type="Call" />
        <VerticalBar />
        <span className="ml-2">
          {objectVersion.result?.objectId}:{objectVersion.result?.versionIndex}
        </span>
      </div>
    </Tailwind>
  );
};

const AddEvaluationButton: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {addEvaluationCall} = useCompareEvaluationsState();

  const evaluationsFilter = useEvaluationsFilter(
    props.state.data.entity,
    props.state.data.project
  );
  const page = useMemo(
    () => ({
      pageSize: 100,
      page: 0,
    }),
    []
  );
  const expandedRefCols = useMemo(() => new Set<string>(), []);
  const columns = useMemo(() => ['inputs'], []);
  const calls = useCallsForQuery(
    props.state.data.entity,
    props.state.data.project,
    evaluationsFilter,
    DEFAULT_FILTER_CALLS,
    DEFAULT_SORT_CALLS,
    page,
    expandedRefCols,
    columns
  );

  const menuOptions = useMemo(() => {
    return [
      calls.result.map(call => ({
        key: call.callId,
        content: (
          <EvalMenuOption
            callId={call.callId}
            callName={call.displayName ?? call.spanName}
            modelRef={call.traceCall?.inputs.model}
          />
        ),
        onClick: () => {
          addEvaluationCall(call.callId);
        },
      })),
    ];
  }, [calls, addEvaluationCall]);

  return (
    <div className="flex w-full">
      <PopupDropdown
        sections={menuOptions}
        flowing
        trigger={
          <Button
            className="row-actions-button"
            icon="add-new"
            size="large"
            variant="ghost"
            style={{marginLeft: '4px'}}>
            Add Evaluation
          </Button>
        }
      />
    </div>
  );
};
