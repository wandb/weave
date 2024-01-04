import {LicenseInfo} from '@mui/x-license-pro';
import {useWeaveContext} from '@wandb/weave/context';
import {
  callOpVeryUnsafe,
  constFunction,
  constNodeUnsafe,
  constNumber,
  constString,
  isTypedDict,
  listObjectType,
  Node,
  NodeOrVoidNode,
  opDict,
  opLimit,
  opMap,
  opPick,
  voidNode,
} from '@wandb/weave/core';
import {parseRef, useNodeValue} from '@wandb/weave/react';
import _ from 'lodash';
import React, {FC, useEffect, useMemo, useState} from 'react';
import {BrowserRouter as Router} from 'react-router-dom';

import {usePanelContext} from '../../Panel2/PanelContext';
import {flattenObject} from './Browse2/browse2Util';
import {weaveConst, weaveGet} from './Browse2/easyWeave';
import {parseRefMaybe} from './Browse2/SmallRef';

LicenseInfo.setLicenseKey(
  '7684ecd9a2d817a3af28ae2a8682895aTz03NjEwMSxFPTE3MjgxNjc2MzEwMDAsUz1wcm8sTE09c3Vic2NyaXB0aW9uLEtWPTI='
);

export const EvalDemo: FC<{basename: string}> = props => {
  const tableNode = useMemo(
    // () => weaveGet('local-artifact:///ArrowWeaveList:1c10dd179e9be9de4f15/obj'),
    () => weaveGet('local-artifact:///ArrowWeaveList:911e669fca88f57dd3ac/obj'),
    []
  );
  const weave = useWeaveContext();
  const [refinedNode, setRefinedNode] = useState<NodeOrVoidNode>(voidNode());
  const {stack} = usePanelContext();
  useEffect(() => {
    const doRefine = async () => {
      const refined = await weave.refineNode(tableNode, stack);
      // console.log('GOT REFINED', refined);
      setRefinedNode(refined);
    };
    doRefine();
  }, [stack, tableNode, weave]);
  if (refinedNode.nodeType === 'void') {
    return <div>loading</div>;
  }
  console.log('REFINEDNODE', refinedNode);
  return (
    <Router basename={props.basename}>
      <TraceTable node={refinedNode} />
    </Router>
  );
};

export const TraceTable: FC<{
  node: Node;
}> = ({node}) => {
  const [focusRef, setFocusRef] = useState<string | null>(null);
  const objectType = listObjectType(node.type);
  console.log('OBJTYPE', objectType);
  if (!isTypedDict(objectType)) {
    throw new Error('invalid node for WeaveEditorList');
  }
  const fetchAllNode = useMemo(() => {
    return opLimit({
      arr: opMap({
        arr: node,
        mapFn: constFunction({row: objectType}, ({row}) =>
          opDict(
            _.fromPairs(
              Object.keys(objectType.propertyTypes).map(key => [
                key,
                opPick({obj: row, key: constString(key)}),
              ])
            ) as any
          )
        ),
      }),
      limit: constNumber(1000),
    });
  }, [node, objectType]);
  const fetchQuery = useNodeValue(fetchAllNode);
  const rows = useMemo(
    () => (fetchQuery.result ?? []).map(r => flattenObject(r)),
    [fetchQuery.result]
  );
  const colNames = Object.keys(rows[0] ?? {});
  if (fetchQuery.loading) {
    return <div>loading</div>;
  }
  console.log('rows', rows);
  return (
    <div style={{padding: 16}}>
      <div style={{display: 'flex'}}>
        <div>
          <div style={{fontSize: 20, marginBottom: 16}}>Eval Table</div>
          <div style={{display: 'flex'}}>
            {_.map(colNames, colName => (
              <div
                style={{
                  padding: 8,
                  width: 100,
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap',
                  border: '1px solid #eee',
                }}>
                {colName}
              </div>
            ))}
          </div>
          {rows.map(row => (
            <div style={{display: 'flex'}}>
              {_.map(row, (v, k) => (
                <div
                  style={{
                    padding: 8,
                    width: 100,
                    textOverflow: 'ellipsis',
                    overflow: 'hidden',
                    whiteSpace: 'nowrap',
                    border: '1px solid #eee',
                  }}>
                  {parseRefMaybe(v) ? (
                    <WeaveRef uri={v} onClick={() => setFocusRef(v)} />
                  ) : (
                    JSON.stringify(v)
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
        <div style={{paddingLeft: 16}}>
          <div style={{fontSize: 20, marginBottom: 16}}>Details</div>
          {focusRef != null && <RefDetails uri={focusRef} />}
        </div>
      </div>
    </div>
  );
};

const RefDetails: FC<{uri: string}> = ({uri}) => {
  const trace = useTrace(uri);
  return (
    <div>
      <div>{JSON.stringify(uri)}</div>
      {trace.ansestor && <Run run={trace.ansestor} />}
    </div>
  );
};

const Run: FC<{run: any}> = ({run}) => {
  const ref = parseRef(run.op_name);
  const inputs = useMemo(() => {
    return Object.values(_.filter(run.inputs, (v, k) => !k.startsWith('_')));
  }, [run.inputs]);
  return (
    <div>
      Op {ref.artifactName}:{ref.artifactVersion.slice(0, 6)}
      <div>Inputs</div>
      <div style={{paddingLeft: 16}}>
        {inputs.map(inputVal =>
          parseRefMaybe(inputVal) ? (
            <WeaveRef uri={inputVal} onClick={() => {}} />
          ) : (
            <div>{JSON.stringify(inputVal)}</div>
          )
        )}
      </div>
      <div>Output</div>
      <div style={{paddingLeft: 16}}>
        {parseRefMaybe(run.output) ? (
          <WeaveRef uri={run.output} onClick={() => {}} />
        ) : (
          <div>{JSON.stringify(run.output)}</div>
        )}
      </div>
    </div>
  );
};

const WeaveRef: FC<{
  uri: string;
  onClick: () => void;
}> = ({uri, onClick}) => {
  if (!(typeof uri === 'string' && uri.includes('artifact://'))) {
    throw new Error('invalid uri');
  }
  const objNode = weaveGet(uri);
  console.log('URI', uri);
  const objQuery = useNodeValue(objNode);
  console.log('OBJ QUERY', objQuery);
  return (
    <div style={{backgroundColor: '#ffe7cc'}} onClick={onClick}>
      {objQuery.loading ? 'loading' : JSON.stringify(objQuery.result)}
    </div>
  );
};

const useTrace = (ref: string) => {
  const runsNode = useMemo(
    () =>
      callOpVeryUnsafe('Ref-get', {
        self: callOpVeryUnsafe('op-objects', {
          ofType: constNodeUnsafe('type', {type: 'Run'}),
          alias: weaveConst('latest'),
          timestamp: weaveConst(0),
        }),
      }),
    []
  );
  const runsQuery = useNodeValue(runsNode);
  console.log('RUNS QUERY', runsQuery);
  const runs = useMemo(() => runsQuery.result ?? [], [runsQuery.result]);
  return useMemo(() => lineageDag(ref, runs), [ref, runs]);
};

const lineageDag = (ref: string, runs: Array<any>) => {
  const ancestor = (ref: string) => {
    return runs.filter(r => r.output === ref)[0];
  };
  return {ansestor: ancestor(ref)};
};
