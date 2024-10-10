import {Popover} from '@mui/material';
import Input from '@wandb/weave/common/components/Input';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {parseRef, WeaveObjectRef} from '@wandb/weave/react';
import React, {useEffect, useMemo, useRef, useState} from 'react';

import {Button} from '../../../../../../../Button';
import {
  DEFAULT_FILTER_CALLS,
  DEFAULT_SORT_CALLS,
} from '../../../CallsPage/CallsTable';
import {useCallsForQuery} from '../../../CallsPage/callsTableQuery';
import {useEvaluationsFilter} from '../../../CallsPage/evaluationsFilter';
import {Id} from '../../../common/Id';
import {useWFHooks} from '../../../wfReactInterface/context';
import {
  CallSchema,
  ObjectVersionKey,
} from '../../../wfReactInterface/wfDataModelHooksInterface';
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

const ModelRefLabel: React.FC<{modelRef: string}> = props => {
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
    <span className="ml-2">
      {objectVersion.result?.objectId}:{objectVersion.result?.versionIndex}
    </span>
  );
};

const AddEvaluationButton: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {addEvaluationCall} = useCompareEvaluationsState();

  // Calls query for just evaluations
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
  // Don't query for output here, re-queried in tsDataModelHooksEvaluationComparison.ts
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

  const evalsNotComparing = useMemo(() => {
    return calls.result.filter(
      call =>
        !Object.keys(props.state.data.evaluationCalls).includes(call.callId)
    );
  }, [calls.result, props.state.data.evaluationCalls]);

  const [menuOptions, setMenuOptions] =
    useState<CallSchema[]>(evalsNotComparing);
  useEffect(() => {
    setMenuOptions(evalsNotComparing);
  }, [evalsNotComparing]);

  const onSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const search = e.target.value;
    if (search === '') {
      setMenuOptions(evalsNotComparing);
      return;
    }

    const filteredOptions = calls.result.filter(call => {
      if (
        (call.displayName ?? call.spanName)
          .toLowerCase()
          .includes(search.toLowerCase())
      ) {
        return true;
      }
      if (call.callId.slice(-4).includes(search)) {
        return true;
      }
      const modelRef = parseRef(call.traceCall?.inputs.model) as WeaveObjectRef;
      if (modelRef.artifactName.toLowerCase().includes(search.toLowerCase())) {
        return true;
      }
      return false;
    });

    setMenuOptions(filteredOptions);
  };

  // Popover management
  const refBar = useRef<HTMLDivElement>(null);
  const refLabel = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : refBar.current);
  };
  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  return (
    <>
      <div
        ref={refBar}
        className="flex cursor-pointer items-center gap-4 rounded px-8 py-4 outline outline-moon-250 hover:outline-2 hover:outline-teal-500/40"
        onClick={onClick}>
        <div ref={refLabel}>
          <Button variant="ghost" size="large" icon="add-new">
            Add evaluation
          </Button>
        </div>
      </div>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        slotProps={{
          paper: {
            sx: {
              marginTop: '8px',
              overflow: 'visible',
              minWidth: '200px',
            },
          },
        }}
        onClose={() => setAnchorEl(null)}>
        <Tailwind>
          <div className="w-full p-12">
            <Input
              type="text"
              placeholder="Search"
              icon="search"
              iconPosition="left"
              onChange={onSearchChange}
              className="w-full"
            />
            <div className="mt-12 flex max-h-[400px] flex-col gap-2 overflow-y-auto">
              {menuOptions.length === 0 && (
                <div className="text-center text-moon-600">No evaluations</div>
              )}
              {menuOptions.map(call => (
                <div key={call.callId} className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="small"
                    className="pb-8 pt-8 font-['Source_Sans_Pro'] text-base font-normal text-moon-800"
                    onClick={() => {
                      addEvaluationCall(call.callId);
                    }}>
                    <>
                      <span>{call.displayName ?? call.spanName}</span>
                      <Id id={call.callId} type="Call" className="ml-0 mr-4" />
                      <VerticalBar />
                      <ModelRefLabel modelRef={call.traceCall?.inputs.model} />
                    </>
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};
