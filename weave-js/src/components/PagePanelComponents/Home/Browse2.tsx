import * as _ from 'lodash';
import React, {FC, useCallback, useEffect, useMemo, useState} from 'react';
import {
  Switch,
  Route,
  Link,
  useParams,
  useHistory,
  useLocation,
} from 'react-router-dom';

import styled from 'styled-components';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {URL_BROWSE2} from '../../../urls';
import {useIsAuthenticated} from '@wandb/weave/context/WeaveViewerContext';
import * as query from './query';
import {
  callOpVeryUnsafe,
  constNumber,
  constString,
  opGet,
  Node,
  linearize,
  isConstNode,
} from '@wandb/weave/core';
import {ChildPanel, ChildPanelConfig, initPanel} from '../../Panel2/ChildPanel';
import {usePanelContext} from '../../Panel2/PanelContext';
import {useWeaveContext} from '@wandb/weave/context';
import {useMakeLocalBoardFromNode} from '../../Panel2/pyBoardGen';
import {SEED_BOARD_OP_NAME} from './HomePreviewSidebar';
import {Button} from 'semantic-ui-react';
import {isWandbArtifactRef, parseRef, useNodeValue} from '@wandb/weave/react';
import {monthRoundedTime} from '@wandb/weave/time';
import Sidebar from '../../Sidebar/Sidebar';
import {flatToTrees} from '../../Panel2/PanelTraceTree/util';
import {
  CallFilter,
  StreamId,
  callsTableFilter,
  callsTableNode,
  callsTableOpCounts,
  callsTableSelect,
} from './Browse2/calls';

function useQuery() {
  const {search} = useLocation();

  return React.useMemo(() => new URLSearchParams(search), [search]);
}

const Browse2Root: FC = props => {
  const isAuthenticated = useIsAuthenticated();
  const userEntities = query.useUserEntities(isAuthenticated);
  return (
    <div>
      Root
      <div>
        {userEntities.result.map(entityName => (
          <div key={entityName}>
            <Link to={`/${URL_BROWSE2}/${entityName}`}>{entityName}</Link>
          </div>
        ))}
      </div>
    </div>
  );
};

interface Browse2EntityParams {
  entity: string;
}

const Browse2Entity: FC = props => {
  const params = useParams<Browse2EntityParams>();
  const entityProjects = query.useProjectsForEntity(params.entity);
  return (
    <div>
      <div>
        {entityProjects.result.map(projectName => (
          <div key={projectName}>
            <Link to={`/${URL_BROWSE2}/${params.entity}/${projectName}`}>
              {projectName}
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
};

interface Browse2ProjectParams {
  entity: string;
  project: string;
}

const Browse2Project: FC = props => {
  const params = useParams<Browse2ProjectParams>();
  const rootTypeCounts = query.useProjectAssetCountGeneral(
    params.entity,
    params.project
  );
  return (
    <div>
      <div style={{marginBottom: 12}}>
        Objects
        {rootTypeCounts.result
          .filter(
            typeInfo =>
              // typeInfo.name !== 'stream_table' &&
              typeInfo.name !== 'OpDef' && typeInfo.name !== 'wandb-history'
          )
          .map(typeInfo => (
            <div key={typeInfo.name}>
              <Link
                to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${typeInfo.name}`}>
                {typeInfo.name}
              </Link>
            </div>
          ))}
      </div>
      <div style={{marginBottom: 12}}>
        <div>Ops</div>
        <Browse2RootObjectType
          entity={params.entity}
          project={params.project}
          rootType="OpDef"
        />
      </div>
      <div style={{marginBottom: 12}}>
        <div>Runs</div>
        <Browse2RunsPage />
      </div>
    </div>
  );
};

interface Browse2RootObjectTypeParams {
  entity: string;
  project: string;
  rootType: string;
}

const Browse2RootObjectType: FC<Browse2RootObjectTypeParams> = ({
  entity,
  project,
  rootType,
}) => {
  const objectsInfo = query.useProjectObjectsOfType(entity, project, rootType);
  return (
    <div>
      <div>
        {objectsInfo.result.map(objInfo => (
          <div key={objInfo.name}>
            <Link
              to={`/${URL_BROWSE2}/${entity}/${project}/${rootType}/${objInfo.name}`}>
              {objInfo.name}
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
};

const Browse2RootObjectTypePage: FC = props => {
  const params = useParams<Browse2RootObjectTypeParams>();
  return <Browse2RootObjectType {...params} />;
};

interface Browse2RootObjectParams {
  entity: string;
  project: string;
  rootType: string;
  objName: string;
  objVersion: string;
}

const Browse2RootObject: FC = props => {
  const params = useParams<Browse2RootObjectParams>();
  const aliases = query.useObjectAliases(
    params.entity,
    params.project,
    params.objName
  );
  const versionNames = query.useObjectVersions(
    params.entity,
    params.project,
    params.objName
  );
  return (
    <div>
      <div>
        Aliases
        {aliases.result.map(alias => (
          <div key={alias}>
            <Link
              to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${alias}`}>
              {alias}
            </Link>
          </div>
        ))}
      </div>
      <div>
        Versions
        {versionNames.result.map(version => (
          <div key={version}>
            <Link
              to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${version}`}>
              {version}
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
};

interface ObjPath {
  entity: string;
  project: string;
  objName: string;
  objVersion: string;
}

const makeObjRefUri = (objPath: ObjPath) => {
  return `wandb-artifact:///${objPath.entity}/${objPath.project}/${objPath.objName}:${objPath.objVersion}/obj`;
};

interface Browse2RootObjectVersionItemParams {
  entity: string;
  project: string;
  rootType: string;
  objName: string;
  objVersion: string;
  refExtra?: string;
}

const nodeFromExtra = (node: Node, extra: string[]): Node => {
  if (extra.length === 0) {
    return node;
  }
  if (extra[0] === 'index') {
    return nodeFromExtra(
      callOpVeryUnsafe('index', {
        arr: node,
        index: constNumber(parseInt(extra[1])),
      }) as Node,
      extra.slice(2)
    );
  } else if (extra[0] === 'pick') {
    return nodeFromExtra(
      callOpVeryUnsafe('pick', {
        obj: node,
        key: constString(extra[1]),
      }) as Node,
      extra.slice(2)
    );
  }
  return nodeFromExtra(
    callOpVeryUnsafe('Object-__getattr__', {
      self: node,
      name: constString(extra[0]),
    }) as Node,
    extra.slice(1)
  );
};

interface Call {
  name: string;
  inputs: {[key: string]: any};
  output: any;
  attributes: {[key: string]: any};
  summary: {latency_s: number; [key: string]: any};
  span_id: string;
  trace_id: string;
  parent_id: string;
  timestamp: string;
  start_time_ms: number;
  end_time_ms: number;
}

type Span = Call;

const callOpName = (call: Call) => {
  if (!call.name.startsWith('wandb-artifact:')) {
    return call.name;
  }
  const ref = parseRef(call.name);
  if (!isWandbArtifactRef(ref)) {
    return call.name;
  }
  return ref.artifactName;
};

const RefEl = styled.div`
  margin-right: 4px;
  display: flex;
`;

const RefName = styled.div``;

const RefVer = styled.div``;

const RefViewSmall: FC<{refS: string}> = ({refS}) => {
  const parsed = parseRef(refS);
  return (
    <RefEl>
      <RefName>{parsed.artifactName}</RefName>:
      <RefVer>{parsed.artifactVersion.slice(0, 7)}</RefVer>
    </RefEl>
  );
};

const CallField = styled.div`
  margin-right: 4px;
`;

const CallOpEl = styled.div`
  margin-right: 4px;
`;

const CallInputs = styled.div`
  display: flex;
  margin-right: 4px;
  > *:not(:last-child) {
    margin-right: 4px;
  }
`;

const CallEl = styled.div<{selected: boolean}>`
  display: flex;
  cursor: pointer;
  :hover {
    background: ${globals.lightSky};
  }
  background: ${props => (props.selected ? globals.sky : 'inherit')};
`;

const CallViewSmall: FC<{
  call: Call;
  selected: boolean;
  onClick: () => void;
}> = ({call, selected, onClick}) => {
  const inputEntries = Object.entries(call.inputs).filter(
    ([k, c]) => c != null && !k.startsWith('_')
  );
  return (
    <CallEl
      selected={selected}
      onClick={() => {
        onClick();
      }}>
      {/* <CallField style={{marginRight: 4}}>{call.timestamp}</CallField> */}
      <CallField>{monthRoundedTime(call.summary.latency_s, true)}</CallField>
      <CallOpEl>{callOpName(call)}</CallOpEl>
      <CallInputs>
        (
        {inputEntries.map(([k, input]) =>
          typeof input === 'string' && input.startsWith('wandb-artifact:') ? (
            <RefViewSmall refS={input} />
          ) : (
            JSON.stringify(input).slice(0, 10)
          )
        )}
        )
      </CallInputs>
      <CallField>➡</CallField>
      <CallField>{JSON.stringify(call.output).slice(0, 10)}</CallField>
    </CallEl>
  );
};

export const SidebarWrapper = styled.div`
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.2);
  z-index: 100;
`;
SidebarWrapper.displayName = 'S.SidebarWrapper';

interface TraceSpan {
  traceId: string;
  spanId?: string;
}

type SpanWithChildren = Span & {child_spans: SpanWithChildren[]};

export const SpanTreeChildrenEl = styled.div`
  padding-left: 12px;
`;

export const SpanTreeDetailsEl = styled.div`
  padding-left: 18px;
`;

const SpanDetails: FC<{call: Call}> = ({call}) => {
  const actualInputs = Object.entries(call.inputs).filter(
    ([k, c]) => c != null && !k.startsWith('_')
  );
  const inputs = _.fromPairs(actualInputs);
  return (
    <div>
      <div style={{marginBottom: 12}}>
        <div>
          <b>Op</b>
        </div>
        {call.name}
      </div>
      <div style={{marginBottom: 12}}>
        <div>
          <b>inputs</b>
        </div>
        <pre style={{fontSize: 12}}>{JSON.stringify(inputs, undefined, 2)}</pre>
      </div>
      <div style={{marginBottom: 12}}>
        <div>
          <b>output</b>
        </div>
        <pre style={{fontSize: 12}}>
          {JSON.stringify(call.output, undefined, 2)}
        </pre>
      </div>
      <div style={{marginBottom: 12}}>
        <div>
          <b>attributes</b>
        </div>
        <pre style={{fontSize: 12}}>
          {JSON.stringify(call.attributes, undefined, 2)}
        </pre>
      </div>
      <div style={{marginBottom: 12}}>
        <div>
          <b>summary</b>
        </div>
        <pre style={{fontSize: 12}}>
          {JSON.stringify(call.summary, undefined, 2)}
        </pre>
      </div>
    </div>
  );
};

const SpanTreeNode: FC<{call: SpanWithChildren; selectedSpan: TraceSpan}> = ({
  call,
  selectedSpan,
}) => {
  const isSelected =
    selectedSpan.traceId === call.trace_id &&
    selectedSpan.spanId === call.span_id;
  const [expanded, setExpanded] = useState(isSelected);
  return (
    <>
      <CallViewSmall
        call={call}
        selected={isSelected}
        onClick={() => setExpanded(!expanded)}
      />
      {expanded && (
        <SpanTreeDetailsEl>
          <SpanDetails call={call} />{' '}
        </SpanTreeDetailsEl>
      )}
      <SpanTreeChildrenEl>
        {call.child_spans.map(child => (
          <SpanTreeNode call={child} selectedSpan={selectedSpan} />
        ))}
      </SpanTreeChildrenEl>
    </>
  );
};

const TraceDetails: FC<{streamId: StreamId; traceSpan: TraceSpan}> = ({
  streamId,
  traceSpan,
}) => {
  const traceSpansNode = useMemo(() => {
    const rowsNode = callsTableNode(streamId);
    const filtered = callsTableFilter(rowsNode, {traceId: traceSpan.traceId});
    return callsTableSelect(filtered);
  }, [streamId, traceSpan.traceId]);
  const traceSpansQuery = useNodeValue(traceSpansNode);

  const traceSpans: Span[] = useMemo(
    () => traceSpansQuery.result ?? [],
    [traceSpansQuery.result]
  );

  const tree = useMemo(
    () => flatToTrees(traceSpans),
    [traceSpans]
  ) as SpanWithChildren[];

  return (
    <div>
      <div>Trace id: {traceSpan.traceId}</div>
      <div>Span id: {traceSpan.spanId}</div>
      <div style={{marginBottom: 12}}>Span count: {traceSpans.length}</div>
      {tree[0] != null && (
        <SpanTreeNode call={tree[0]} selectedSpan={traceSpan} />
      )}
    </div>
  );
};

const Browse2Calls: FC<{
  streamId: StreamId;
  filters: CallFilter;
  selectedSpan?: TraceSpan;
}> = ({streamId, filters, selectedSpan}) => {
  const history = useHistory();
  const location = useLocation();
  const query = useQuery();

  const selected = useMemo(() => {
    const streamTableRowsNode = callsTableNode(streamId);
    const filtered = callsTableFilter(streamTableRowsNode, filters);
    return callsTableSelect(filtered);
  }, [filters, streamId]);

  const selectedQuery = useNodeValue(selected);

  const [selectedSpanId, setSelectedSpanId] = useState<TraceSpan | undefined>(
    selectedSpan
  );
  const selectedData = selectedQuery.result ?? [];

  return (
    <div style={{width: '100%', height: 500}}>
      Calls
      {filters.opUri != null && <div>Op: {filters.opUri}</div>}
      {filters.inputUris != null && (
        <div>
          Inputs:
          {filters.inputUris.map((inputUri, i) => (
            <div key={i}>{inputUri}</div>
          ))}
        </div>
      )}
      <div style={{paddingLeft: 24}}>
        {selectedData.map((call: Call) => (
          <CallViewSmall
            call={call}
            selected={
              call.trace_id === selectedSpanId?.traceId &&
              call.span_id === selectedSpanId?.spanId
            }
            onClick={() => {
              query.set('traceSpan', `${call.trace_id},${call.span_id}`);
              history.push({
                pathname: location.pathname,
                search: query.toString(),
              });
              setSelectedSpanId({traceId: call.trace_id, spanId: call.span_id});
            }}
          />
        ))}
      </div>
      {selectedSpanId != null && (
        <SidebarWrapper>
          <Sidebar
            width={600}
            collapsed={false}
            close={() => setSelectedSpanId(undefined)}>
            <div style={{width: '100%', height: '100%', overflowY: 'auto'}}>
              <div style={{padding: 12}}>
                <TraceDetails streamId={streamId} traceSpan={selectedSpanId} />
              </div>
            </div>
          </Sidebar>
        </SidebarWrapper>
      )}
    </div>
  );
};

const Browse2CallsPage: FC = () => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const filters: CallFilter = {};
  const query = useQuery();
  let selectedSpan: TraceSpan | undefined = undefined;
  query.forEach((val, key) => {
    if (key === 'op') {
      filters.opUri = val;
    } else if (key === 'inputUri') {
      if (filters.inputUris == null) {
        filters.inputUris = [];
      }
      filters.inputUris.push(val);
    } else if (key === 'traceSpan') {
      const [traceId, spanId] = val.split(',', 2);
      selectedSpan = {traceId, spanId};
    }
  });
  console.log('URL SEL SPAN', selectedSpan);
  return (
    <Browse2Calls
      streamId={{
        entityName: params.entity,
        projectName: params.project,
        streamName: 'stream',
      }}
      selectedSpan={selectedSpan}
      filters={filters}
    />
  );
};

const Browse2Runs: FC<{
  streamId: StreamId;
  selectedSpan?: TraceSpan;
}> = ({streamId, selectedSpan}) => {
  return <div>Runs</div>;
};

const Browse2RunsPage: FC = () => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const filters: CallFilter = {};
  const query = useQuery();
  let selectedSpan: TraceSpan | undefined = undefined;
  query.forEach((val, key) => {
    if (key === 'op') {
      filters.opUri = val;
    } else if (key === 'inputUri') {
      if (filters.inputUris == null) {
        filters.inputUris = [];
      }
      filters.inputUris.push(val);
    } else if (key === 'traceSpan') {
      const [traceId, spanId] = val.split(',', 2);
      selectedSpan = {traceId, spanId};
    }
  });
  return (
    <Browse2Runs
      streamId={{
        entityName: params.entity,
        projectName: params.project,
        streamName: 'stream',
      }}
      selectedSpan={selectedSpan}
    />
  );
};

const Browse2OpDefPage: FC = () => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const uri = makeObjRefUri(params);
  const query = useQuery();
  const {filt: filters, selSpan: selectedSpan} = useMemo(() => {
    let selSpan: TraceSpan | undefined = undefined;
    const filt: CallFilter = {opUri: uri};
    query.forEach((val, key) => {
      if (key === 'op') {
        filt.opUri = val;
      } else if (key === 'inputUri') {
        if (filt.inputUris == null) {
          filt.inputUris = [];
        }
        filt.inputUris.push(val);
      } else if (key === 'traceSpan') {
        const [traceId, spanId] = val.split(',', 2);
        selSpan = {traceId, spanId};
      }
    });
    return {filt, selSpan};
  }, [query, uri]);
  return (
    <div>
      <Browse2Calls
        streamId={{
          entityName: params.entity,
          projectName: params.project,
          streamName: 'stream',
        }}
        filters={filters}
        selectedSpan={selectedSpan}
      />
    </div>
  );
};

const opPageUrl = (opUri: string) => {
  const parsed = parseRef(opUri);
  if (!isWandbArtifactRef(parsed)) {
    throw new Error('non wandb artifact ref not yet handled');
  }
  return `/${URL_BROWSE2}/${parsed.entityName}/${parsed.projectName}/OpDef/${parsed.artifactName}/${parsed.artifactVersion}`;
};

const Browse2RootObjectVersionUsers: FC<{uri: string}> = ({uri}) => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const calledOpCountsNode = useMemo(() => {
    const streamTableRowsNode = callsTableNode({
      entityName: params.entity,
      projectName: params.project,
      streamName: 'stream',
    });
    const filtered = callsTableFilter(streamTableRowsNode, {
      inputUris: [uri],
    });
    return callsTableOpCounts(filtered);
  }, [params.entity, params.project, uri]);
  const calledOpCountsQuery = useNodeValue(calledOpCountsNode);
  const calledOpCounts = calledOpCountsQuery.result ?? [];
  return (
    <div style={{width: '100%'}}>
      {calledOpCounts.map(({name, count}: {name: string; count: number}) => (
        <div>
          <Link to={`${opPageUrl(name)}?inputUri=${encodeURIComponent(uri)}`}>
            {name}
          </Link>
          : {count}
        </div>
      ))}
    </div>
  );
};

const Browse2RootObjectVersionItem: FC = props => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const uri = makeObjRefUri(params);
  const history = useHistory();
  const itemNode = useMemo(() => {
    const objNode = opGet({uri: constString(uri)});
    if (params.refExtra == null) {
      return objNode;
    }
    const extraFields = params.refExtra.split('/');
    return nodeFromExtra(objNode, extraFields);
  }, [uri, params.refExtra]);
  const weave = useWeaveContext();
  const {stack} = usePanelContext();
  const [panel, setPanel] = React.useState<ChildPanelConfig | undefined>();

  const makeBoardFromNode = useMakeLocalBoardFromNode();

  const [isGenerating, setIsGenerating] = useState(false);

  const onNewBoard = useCallback(async () => {
    setIsGenerating(true);
    const refinedItemNode = await weave.refineNode(itemNode, stack);
    makeBoardFromNode(SEED_BOARD_OP_NAME, refinedItemNode, newDashExpr => {
      setIsGenerating(false);
      window.open('/?exp=' + weave.expToString(newDashExpr), '_blank');
    });
  }, [itemNode, makeBoardFromNode, stack, weave]);

  useEffect(() => {
    const doInit = async () => {
      const panel = await initPanel(
        weave,
        itemNode,
        undefined,
        undefined,
        stack
      );
      setPanel(panel);
    };
    doInit();
  }, [itemNode, stack, weave]);
  const handleUpdateInput = useCallback(
    (newExpr: Node) => {
      const linearNodes = linearize(newExpr);
      if (linearNodes == null) {
        console.log("Can't linearize nodes for updateInput", newExpr);
        return;
      }
      let newExtra: string[] = [];
      for (const subNode of linearNodes) {
        if (subNode.fromOp.name === 'Object-__getattr__') {
          if (!isConstNode(subNode.fromOp.inputs.name)) {
            console.log('updateInput can only handle const keys for now');
            return;
          }
          newExtra.push(subNode.fromOp.inputs.name.val);
        } else if (subNode.fromOp.name === 'index') {
          if (!isConstNode(subNode.fromOp.inputs.index)) {
            console.log('updateInput can only handle const index for now');
            return;
          }
          newExtra.push('index');
          newExtra.push(subNode.fromOp.inputs.index.val.toString());
        } else if (subNode.fromOp.name === 'pick') {
          if (!isConstNode(subNode.fromOp.inputs.key)) {
            console.log('updateInput can only handle const keys for now');
            return;
          }
          newExtra.push('pick');
          newExtra.push(subNode.fromOp.inputs.key.val);
        }
      }
      let newUri = `/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${params.objVersion}`;
      if (params.refExtra != null) {
        newUri += `/${params.refExtra}`;
      }
      newUri += `/${newExtra.join('/')}`;
      history.push(newUri);
    },
    [
      history,
      params.entity,
      params.objName,
      params.objVersion,
      params.project,
      params.rootType,
      params.refExtra,
    ]
  );
  return (
    <div>
      {/* <div>Name: {params.objName}</div>
      <div>Version: {params.objVersion}</div> */}
      {/* <div>Root Ref: {uri}</div> */}
      <div style={{marginBottom: 12}}>
        <div style={{display: 'flex', alignItems: 'center'}}>
          Expr: {weave.expToString(itemNode)}
          <Button
            style={{marginLeft: 12}}
            size="mini"
            onClick={onNewBoard}
            loading={isGenerating}>
            Open in board
          </Button>
        </div>
      </div>
      {params.rootType === 'stream_table' ? (
        <Browse2CallsPage />
      ) : params.rootType === 'OpDef' ? (
        <Browse2OpDefPage />
      ) : (
        <>
          <div style={{marginBottom: 12}}>
            Used in ops
            <Browse2RootObjectVersionUsers uri={uri} />
          </div>
          <div style={{height: 300, width: '100%'}}>
            Object view
            {panel != null && (
              <ChildPanel
                config={panel}
                updateConfig={newConfig => setPanel(newConfig)}
                updateInput={handleUpdateInput}
                passthroughUpdate
              />
            )}
          </div>
        </>
      )}
    </div>
  );
};

interface Browse2Params {
  entity?: string;
  project?: string;
  rootType?: string;
  objName?: string;
  objVersion?: string;
  refExtra?: string;
}

const Browse2Breadcrumbs: FC = props => {
  const params = useParams<Browse2Params>();
  return (
    <div>
      <Link to={`/${URL_BROWSE2}`}>🏠</Link>
      {params.entity && (
        <>
          {' / '}
          <Link to={`/${URL_BROWSE2}/${params.entity}`}>{params.entity}</Link>
          {params.project && (
            <>
              {' / '}
              <Link to={`/${URL_BROWSE2}/${params.entity}/${params.project}`}>
                {params.project}
              </Link>
              {params.rootType && (
                <>
                  {' / '}
                  <Link
                    to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}`}>
                    {params.rootType}
                  </Link>
                  {params.objName && (
                    <>
                      {' / '}
                      <Link
                        to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}`}>
                        {params.objName}
                      </Link>
                      {params.objVersion && (
                        <>
                          {' / '}
                          <Link
                            to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${params.objVersion}`}>
                            {params.objVersion}
                          </Link>
                          {params.refExtra && (
                            <RefExtraBreadCrumbs refExtra={params.refExtra} />
                          )}
                        </>
                      )}
                    </>
                  )}
                </>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
};

const RefExtraBreadCrumbs: FC<{refExtra: string}> = ({refExtra}) => {
  const params = useParams<Browse2Params>();
  const refFields = refExtra.split('/');
  return (
    <>
      {refFields.map((field, idx) => {
        return (
          <>
            {' / '}
            {field === 'index' ? (
              <span>row</span>
            ) : field === 'pick' ? (
              <span>col</span>
            ) : (
              <Link
                to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${
                  params.rootType
                }/${params.objName}/${params.objVersion}/${refFields
                  .slice(0, idx + 1)
                  .join('/')}`}>
                {field}
              </Link>
            )}
          </>
        );
      })}
    </>
  );
};

export const Browse2: FC = props => {
  return (
    <div style={{height: '100vh', overflow: 'auto'}}>
      <div style={{padding: 32}}>
        <Browse2Breadcrumbs />
        <Switch>
          <Route
            path={`/${URL_BROWSE2}/:entity/:project/:rootType/:objName/:objVersion/:refExtra*`}>
            <Browse2RootObjectVersionItem />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project/:rootType/:objName`}>
            <Browse2RootObject />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project/:rootType`}>
            <Browse2RootObjectTypePage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project`}>
            <Browse2Project />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity`}>
            <Browse2Entity />
          </Route>
          <Route path={`/${URL_BROWSE2}`}>
            <Browse2Root />
          </Route>
        </Switch>
      </div>
    </div>
  );
};
