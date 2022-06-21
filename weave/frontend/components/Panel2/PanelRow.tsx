import * as _ from 'lodash';
import React from 'react';
import {useState, useCallback, useMemo} from 'react';
import * as Types from '@wandb/cg/browser/model/types';
import PageControls from './ControlPage';
import * as Table from './PanelTable/tableState';
import * as CGReact from '@wandb/common/cgreact';
import * as Op from '@wandb/cg/browser/ops';
import * as Panel2 from './panel';
import {PanelComp2} from './PanelComp';
import * as ConfigPanel from './ConfigPanel';
import * as PanelLib from './panellib/libpanel';
import {useGatedValue} from '@wandb/common/state/hooks';
import {Checkbox} from 'semantic-ui-react';

export interface PanelRowConfig {
  pageSize: number;

  vertical?: boolean;
  childConfig: any;
}
type PanelRowProps = Panel2.PanelConverterProps;

function defaultConfig(
  inputType: Types.Type,
  child: Panel2.PanelSpecNode
): PanelRowConfig {
  inputType = Types.nullableTaggableValue(inputType);
  if (!Types.isList(inputType)) {
    throw new Error(`Invalid panel row input type: ${inputType}`);
  }
  let pageSize = 3;
  if (Types.listMaxLength(inputType) === 2) {
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

  return {pageSize, vertical: false, childConfig: undefined};
}

const useConfig = (
  inputType: Types.Type,
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

const PanelRowConfig: React.FC<PanelRowProps> = props => {
  const {updateConfig} = props;
  const config = useConfig(props.input.type, props.child, props.config);
  const {pageSize, vertical} = config;
  const childConfig = useMemo(
    () => config.childConfig ?? {},
    [config.childConfig]
  );
  const convertedType = Spec.convert(props.inputType);
  if (convertedType == null) {
    throw new Error('Invalid (null) pane row config input type');
  }
  const updateChildConfig = useCallback(
    (newConfig: any) =>
      updateConfig({...config, childConfig: {...childConfig, ...newConfig}}),
    [updateConfig, config, childConfig]
  );
  const newInput = useMemo(() => {
    return Op.opIndex({
      arr: props.input,
      index: Op.varNode('number', 'n'),
    });
  }, [props.input]);
  console.log(`config`, config);
  return (
    <>
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
    </>
  );
};

const PanelRow: React.FC<PanelRowProps> = props => {
  const {input, updateConfig, child} = props;
  const config = useConfig(props.input.type, child, props.config);
  const rowsNode = input;
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
  const rowNodesUse = CGReact.useEach(visibleRowsNode as any);
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
        <div style={{flex: '0 0 auto', height: '27px'}}>
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
  displayName: 'List of',
  ConfigComponent: PanelRowConfig,
  Component: PanelRow,
  convert: (inputType: Types.Type) => {
    // Since row can handle maybe<list<maybe<X>>
    // we need to do a little extra book keeping.
    let isNullable = false;
    if (Types.isNullable(inputType)) {
      inputType = Types.nonNullable(inputType);
      isNullable = true;
    }
    inputType = Types.taggableValue(inputType);
    if (Types.isNullable(inputType)) {
      inputType = Types.nonNullable(inputType);
      isNullable = true;
    }
    if (Types.isListLike(inputType)) {
      let res = Types.listObjectType(inputType);
      if (isNullable) {
        res = Types.maybe(res);
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
            ? childDims.height * (Types.listLength(type) ?? 3) + 20
            : undefined,
      };
    }

    // row
    return {
      width:
        childDims.width != null
          ? childDims.width * (Types.listLength(type) ?? 3) + 20
          : undefined,
      height: childDims.height != null ? childDims.height + 40 : undefined,
    };
  },
};
