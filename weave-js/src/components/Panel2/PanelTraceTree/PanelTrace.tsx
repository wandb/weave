import * as Panel2 from '../panel';
import React, {useCallback, useMemo} from 'react';
import {TraceTreeSpanViewer} from './PanelTraceTreeTrace';
import {useNodeValue} from '@wandb/weave/react';
import {
  constFunction,
  constNumber,
  listObjectType,
  opLimit,
  opMap,
} from '@wandb/weave/core';
import {Loader} from 'semantic-ui-react';
import {SpanWeaveType, flatToTrees, unifyRoots} from './util';
import {opSpanAsDictToLegacySpanShape} from './common';
import * as S from './lct.style';
import {GeneralObjectRenderer} from './PanelTraceTreeModel';

const inputType = {
  type: 'list' as const,
  objectType: SpanWeaveType,
};

type PanelTraceTreeTraceProps = Panel2.PanelProps<
  typeof inputType,
  {
    selectedSpanIndex?: number;
  }
>;

const PanelTraceRender: React.FC<PanelTraceTreeTraceProps> = props => {
  const query = useMemo(() => {
    const limited = opLimit({arr: props.input, limit: constNumber(10000)});
    return opMap({
      arr: limited as any,
      mapFn: constFunction(
        {row: listObjectType(props.input.type), index: 'number'},
        ({row, index}) => opSpanAsDictToLegacySpanShape({spanDict: row})
      ),
    } as any);
  }, [props.input]);
  const nodeValue = useNodeValue(query);
  const tree = useMemo(
    () =>
      nodeValue.loading ? null : unifyRoots(flatToTrees(nodeValue.result)),
    [nodeValue.loading, nodeValue.result]
  );
  const setSelectedSpanIndex = useCallback(
    (selectedSpanIndex: number) => {
      props.updateConfig({selectedSpanIndex});
    },
    [props]
  );
  const [selectedTab, setSelectedTab] = React.useState(0);

  const modelId = tree?.attributes?.model?.id;
  const modelObj = React.useMemo(() => {
    let modelObjInner = tree?.attributes?.model?.obj;
    if (typeof modelObjInner === 'string') {
      try {
        modelObjInner = JSON.parse(modelObjInner);
      } catch (e) {
        console.log(e);
        modelObjInner = null;
      }
    }
    return modelObjInner;
  }, [tree?.attributes?.model?.obj]);
  let modelTitle = 'Model Architecture';
  if (modelId != null) {
    modelTitle += ` (ID: ${modelId})`;
  }

  if (tree == null) {
    return <Loader />;
  }

  if (modelObj == null) {
    return (
      <TraceTreeSpanViewer
        span={tree}
        selectedSpanIndex={props.config?.selectedSpanIndex}
        onSelectSpanIndex={setSelectedSpanIndex}
      />
    );
  }

  return (
    <S.SimpleTabs
      activeIndex={selectedTab}
      onTabChange={(e: any, p: any) => {
        setSelectedTab(p?.activeIndex ?? 0);
      }}
      panes={[
        {
          menuItem: {
            key: 'trace',
            content: `Trace Timeline`,
          },
          render: () => (
            <S.TabWrapper>
              <TraceTreeSpanViewer
                span={tree}
                selectedSpanIndex={props.config?.selectedSpanIndex}
                onSelectSpanIndex={setSelectedSpanIndex}
              />
            </S.TabWrapper>
          ),
        },
        {
          menuItem: {
            key: 'model',
            content: modelTitle,
          },
          render: () => (
            <S.TabWrapper>
              <S.ModelWrapper>
                <GeneralObjectRenderer data={modelObj} />
              </S.ModelWrapper>
            </S.TabWrapper>
          ),
        },
      ]}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'tracePanel',
  canFullscreen: true,
  Component: PanelTraceRender,
  inputType,
};
