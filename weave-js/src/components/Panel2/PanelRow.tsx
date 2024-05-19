import {
  isListLike,
  isNullable,
  listLength,
  listMaxLength,
  listObjectType,
  maybe,
  nonNullable,
  nullableTaggableValue,
  opDropNa,
  opIndex,
  taggableValue,
  Type,
  varNode,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import React, {useCallback, useMemo, useState} from 'react';
import {Checkbox} from 'semantic-ui-react';

import {useGatedValue} from '../../hookUtils';
import * as CGReact from '../../react';
import * as ConfigPanel from './ConfigPanel';
import PageControls from './ControlPage';
import * as Panel2 from './panel';
import {PanelComp2} from './PanelComp';
import {usePanelContext} from './PanelContext';
import * as PanelLib from './panellib/libpanel';
import * as Table from './PanelTable/tableState';

export interface PanelRowConfig {
  pageSize: number;

  vertical?: boolean;
  filterEmpty?: boolean;
  childConfig: any;
}
type PanelRowProps = Panel2.PanelConverterProps;

function defaultConfig(
  inputType: Type,
  child: Panel2.PanelSpecNode
): PanelRowConfig {
  inputType = nullableTaggableValue(inputType);
  if (!isListLike(inputType)) {
    throw new Error(`Invalid panel row input type: ${inputType}`);
  }
  let pageSize = 3;
  if (listMaxLength(inputType) === 2) {
    pageSize = 2;
  }
  const childSpecId = PanelLib.getStackIdAndName(child).id;
  if (
    child.id === 'id' ||
    childSpecId.endsWith('plot') ||
    childSpecId.endsWith('table') ||
    childSpecId.endsWith('histogram') ||
    childSpecId.endsWith('barchart')
  ) {
    pageSize = 1;
  }

  return {pageSize, vertical: false, filterEmpty: true, childConfig: undefined};
}

const useConfig = (
  inputType: Type,
  child: Panel2.PanelSpecNode,
  propsConfig: PanelRowConfig | undefined
): PanelRowConfig => {
  return useMemo(() => {
    const config = _.defaults(
      {...propsConfig},
      defaultConfig(inputType, child)
    );
    return config;
  }, [propsConfig, inputType, child]);
};

const PanelRowConfigComp: React.FC<PanelRowProps> = props => {
  const {updateConfig} = props;
  const {dashboardConfigOptions} = usePanelContext();
  const config = useConfig(props.input.type, props.child, props.config);
  const {pageSize, vertical, filterEmpty} = config;
  const childConfig = useMemo(
    () => config.childConfig ?? {},
    [config.childConfig]
  );
  const convertedType = Spec.convert(props.inputType ?? props.input.type);
  if (convertedType == null) {
    throw new Error('Invalid (null) pane row config input type');
  }
  const updateChildConfig = useCallback(
    (newConfig: any) =>
      updateConfig({...config, childConfig: {...childConfig, ...newConfig}}),
    [updateConfig, config, childConfig]
  );
  const newInput = useMemo(() => {
    return opIndex({
      arr: props.input,
      index: varNode('number', 'n'),
    });
  }, [props.input]);

  return (
    <ConfigPanel.ConfigSection label={`Properties`}>
      {dashboardConfigOptions}
      <ConfigPanel.ConfigOption label={'Page size'}>
        <ConfigPanel.ModifiedDropdownConfigField
          selection
          allowAdditions
          value={pageSize ?? 3}
          options={[1, 2, 3, 5, 10].map(o => ({
            key: o,
            value: o,
            text: o,
          }))}
          onChange={(e, {value}) => {
            let newValue = Math.max(1, Math.min(100, Number(value)));
            if (isNaN(newValue)) {
              newValue = 1;
            }
            updateConfig({pageSize: newValue});
          }}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label={'Vertical'}>
        <Checkbox
          checked={vertical ?? false}
          onChange={(e, {checked}) => updateConfig({vertical: !!checked})}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label={'Filter Nulls'}>
        <Checkbox
          checked={filterEmpty ?? true}
          onChange={(e, {checked}) => updateConfig({filterEmpty: !!checked})}
        />
      </ConfigPanel.ConfigOption>
      <PanelComp2
        input={newInput}
        inputType={convertedType}
        loading={props.loading}
        panelSpec={props.child}
        configMode={true}
        config={childConfig}
        context={props.context}
        updateConfig={updateChildConfig}
        updateContext={props.updateContext}
      />
    </ConfigPanel.ConfigSection>
  );
};

const PanelRow: React.FC<PanelRowProps> = props => {
  const {input, updateConfig, child} = props;
  const config = useConfig(props.input.type, child, props.config);
  let rowsNode = input;

  if (config.filterEmpty) {
    rowsNode = opDropNa({
      arr: rowsNode,
    });
  }

  const [pageNum, setPageNum] = useState(0);
  const {pageSize, vertical} = config;
  const childConfig = useMemo(
    () => config.childConfig ?? {},
    [config.childConfig]
  );
  const updateChildConfig = useCallback(
    (newConfig: any) =>
      updateConfig({...config, childConfig: {...childConfig, ...newConfig}}),
    [updateConfig, config, childConfig]
  );
  const visibleRowsNode = useMemo(
    () => Table.getPagedRowsNode(pageSize, pageNum, rowsNode),
    [pageSize, pageNum, rowsNode]
  );
  const rowNodesUse = CGReact.useEach(visibleRowsNode as any, pageSize);
  const rowNodes = rowNodesUse.result;

  return useGatedValue(
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        padding: '2px',
      }}>
      <div
        style={{
          height: '0px',
          width: '100%',
          display: 'flex',
          justifyContent: 'space-evenly',
          flexDirection: vertical ? 'column' : 'row',
          gap: '4px',
          flex: '1 1 auto',
        }}>
        {_.range(pageSize).map(offset => {
          const node = rowNodes[offset];
          if (node == null) {
            return <div key={offset} style={{flex: '1 1 auto'}} />;
          }
          return (
            <div
              key={offset}
              style={{
                overflowX: 'auto',
                flex: '1 1 50px',
                height: '100%',
              }}>
              <PanelComp2
                input={node}
                inputType={node.type}
                loading={props.loading}
                panelSpec={props.child}
                configMode={false}
                config={childConfig}
                context={props.context}
                updateConfig={updateChildConfig}
                updateContext={props.updateContext}
                updateInput={props.updateInput}
              />
            </div>
          );
        })}
      </div>
      {(rowsNode.type.length == null || rowsNode.type.length > pageSize) && (
        <div style={{flex: '0 0 auto', maxHeight: '27px'}}>
          <PageControls
            rowsNode={rowsNode}
            page={pageNum}
            pageSize={pageSize}
            setPage={setPageNum}
          />
        </div>
      )}
    </div>,
    o => !rowNodesUse.loading
  );
};

export const Spec: Panel2.PanelConvertSpec = {
  id: 'row',
  displayName: 'List',
  ConfigComponent: PanelRowConfigComp,
  Component: PanelRow,
  canFullscreen: true,
  convert: (inputType: Type) => {
    // Since row can handle maybe<list<maybe<X>>
    // we need to do a little extra book keeping.
    let nullable = false;
    if (isNullable(inputType)) {
      inputType = nonNullable(inputType);
      nullable = true;
    }
    inputType = taggableValue(inputType);
    if (isNullable(inputType)) {
      inputType = nonNullable(inputType);
      nullable = true;
    }
    if (isListLike(inputType)) {
      let res = listObjectType(inputType);
      if (nullable) {
        res = maybe(res);
      }
      return res;
    }
    return null;
  },
  defaultFixedSize: (childDims, type, config) => {
    if (config.vertical) {
      // column
      return {
        width: childDims.width != null ? childDims.width + 40 : undefined,
        height:
          childDims.height != null
            ? childDims.height * (listLength(type) ?? 3) + 20
            : undefined,
      };
    }

    // row
    return {
      width:
        childDims.width != null
          ? childDims.width * (listLength(type) ?? 3) + 20
          : undefined,
      height: childDims.height != null ? childDims.height + 40 : undefined,
    };
  },
};
