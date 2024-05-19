import React, {useMemo} from 'react';
import {Loader} from 'semantic-ui-react';

import {useNodeValue} from '../../../react';
import {
  AgentSVG,
  ChainSVG,
  DownSVG,
  LLMSVG,
  NextSVG,
  PromptSVG,
  ToolSVG,
} from '../Icons';
import * as Panel2 from '../panel';
import {
  agentColor,
  agentTextColor,
  chainColor,
  chainTextColor,
  llmColor,
  llmTextColor,
  MinimalTooltip,
  promptColor,
  promptTextColor,
  toolColor,
  toolTextColor,
} from './common';
import * as S from './lct.style';

const inputType = {
  type: 'wb_trace_tree' as const,
};

type PanelTraceTreeModelConfigType = {};

type PanelTraceTreeModelProps = Panel2.PanelProps<
  typeof inputType,
  PanelTraceTreeModelConfigType
>;

export const PanelTraceTreeModel: React.FC<
  PanelTraceTreeModelProps
> = props => {
  const nodeValue = useNodeValue(props.input);
  const model = useMemo(() => {
    try {
      return JSON.parse(nodeValue.result?.model_dict_dumps ?? '{}');
    } catch (e) {
      console.log(e);
      return {};
    }
  }, [nodeValue.result]);

  if (nodeValue.loading) {
    return <Loader />;
  }

  if (model == null) {
    return <div></div>;
  }

  return (
    <S.ModelWrapper>
      <GeneralObjectRenderer data={model} />
    </S.ModelWrapper>
  );
};

type ModelComponent = {
  _type: string;
  [extraKey: string]: any;
};

const isModelComponent = (obj: any): obj is ModelComponent => {
  return obj && obj._kind;
};

const getSafeEntriesFromObject = (obj: any): Array<[string, any]> => {
  return Object.entries(obj)
    .filter(
      ([key, value]) =>
        value != null && key[0] !== '_' && !['verbose'].includes(key)
    )
    .sort(([keyA, valueA], [keyB, valueB]) => {
      return keyA < keyB ? -1 : 1;
    });
};

export const GeneralObjectRenderer: React.FC<{data: any}> = props => {
  if (props.data == null) {
    return <div>-</div>;
  } else if (typeof props.data === 'string') {
    return (
      <MinimalTooltip text={'' + props.data}>
        <S.ConstrainedTextField>{props.data}</S.ConstrainedTextField>
      </MinimalTooltip>
    );
  } else if (typeof props.data === 'number') {
    return <div>{props.data}</div>;
  } else if (typeof props.data === 'boolean') {
    return <div>{'' + props.data}</div>;
  } else if (Array.isArray(props.data)) {
    return (
      <KeyValTable
        isArray
        nonCollapsibleContent={props.data.map((item, i) => {
          return {
            key: '' + i,
            keyContent: <div style={{fontWeight: 'bold'}}>{i}</div>,
            valueContent: <GeneralObjectRenderer data={item} />,
          };
        })}
      />
    );
  } else if (typeof props.data === 'object') {
    let headerRow = null;
    if (isModelComponent(props.data)) {
      const typeName = props.data._kind;
      let typePrefix = null;
      let typeColor = '#eee';
      let typeTextColor = '#111';
      const lowerTypeName = typeName.toLowerCase();

      if (lowerTypeName.includes('chain')) {
        typePrefix = <ChainSVG />;
        typeColor = chainColor;
        typeTextColor = chainTextColor;
      } else if (
        lowerTypeName.includes('agent') ||
        lowerTypeName.includes('react')
      ) {
        typePrefix = <AgentSVG />;
        typeColor = agentColor;
        typeTextColor = agentTextColor;
      } else if (lowerTypeName.includes('prompt')) {
        typePrefix = <PromptSVG />;
        typeColor = promptColor;
        typeTextColor = promptTextColor;
      } else if (
        lowerTypeName.includes('llm') ||
        lowerTypeName.includes('openai')
      ) {
        typePrefix = <LLMSVG />;
        typeColor = llmColor;
        typeTextColor = llmTextColor;
      }

      headerRow = (
        <S.ModelComponentHeader
          backgroundColor={typeColor}
          color={typeTextColor}>
          {typePrefix}
          {typeName}
        </S.ModelComponentHeader>
      );
    }
    const entries = getSafeEntriesFromObject(props.data);
    const nonCollapsibleEntries = entries.filter(([key, value]) => {
      return (
        key === 'allowed_tools' || isModelComponent(value) || key === 'chains'
      );
    });
    const collapsibleEntries = entries.filter(([key, value]) => {
      return (
        key !== 'allowed_tools' && !isModelComponent(value) && key !== 'chains'
      );
    });

    return (
      <KeyValTable
        header={headerRow}
        collapsibleContent={collapsibleEntries.map(([key, value], i) => {
          return {
            key,
            valueContent: <GeneralObjectRenderer data={value} />,
          };
        })}
        nonCollapsibleContent={nonCollapsibleEntries.map(([key, value], i) => {
          if (key === 'allowed_tools') {
            return {
              key,
              valueContent: (
                <S.ModelComponentHeader
                  backgroundColor={toolColor}
                  color={toolTextColor}>
                  <ToolSVG /> {(value ?? []).join(', ')}
                </S.ModelComponentHeader>
              ),
            };
          }
          return {
            key,
            valueContent: <GeneralObjectRenderer data={value} />,
          };
        })}
      />
    );
  }
  return <div>{JSON.stringify(props.data)}</div>;
};

const KeyValTable: React.FC<{
  isArray?: boolean;
  header?: React.ReactNode;
  collapsibleContent?: Array<{
    key: string;
    valueContent: React.ReactNode;
  }>;
  nonCollapsibleContent?: Array<{
    key: string;
    valueContent: React.ReactNode;
  }>;
}> = props => {
  const canBeCollapsed =
    props.collapsibleContent != null &&
    props.collapsibleContent.length > 0 &&
    props.header != null;
  const [isCollapsed, setIsCollapsed] = React.useState(canBeCollapsed);
  return (
    <S.KVTWrapper>
      <S.KVTHeader
        canBeCollapsed={canBeCollapsed}
        onClick={() => {
          setIsCollapsed(!isCollapsed);
        }}>
        {props.header}
      </S.KVTHeader>
      {canBeCollapsed && (
        <S.KVTCollapseButton
          onClick={() => {
            setIsCollapsed(!isCollapsed);
          }}>
          {isCollapsed ? <NextSVG /> : <DownSVG />}
        </S.KVTCollapseButton>
      )}
      {!isCollapsed && <KVTContents contents={props.collapsibleContent} />}
      <KVTContents
        isArrayItem={props.isArray}
        contents={props.nonCollapsibleContent}
      />
    </S.KVTWrapper>
  );
};

const KVTContents: React.FC<{
  isArrayItem?: boolean;
  contents?: Array<{
    key: string;
    valueContent: React.ReactNode;
  }>;
}> = props => {
  return (
    <>
      {(props.contents ?? []).map(({key, valueContent}) => {
        return (
          <S.KVTRow key={key}>
            <MinimalTooltip text={key} lengthLimit={15}>
              <S.KVTKey isArrayItem={!!props.isArrayItem}>{key}</S.KVTKey>
            </MinimalTooltip>
            <S.KVTValue>{valueContent}</S.KVTValue>
          </S.KVTRow>
        );
      })}
    </>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'wb_trace_tree-modelViewer',
  canFullscreen: true,
  Component: PanelTraceTreeModel,
  inputType,
};
