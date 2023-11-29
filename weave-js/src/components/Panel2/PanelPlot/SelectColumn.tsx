/**
 * Select a Column
 */
import {produce} from 'immer';
import * as _ from 'lodash';
import React, {MouseEventHandler, useMemo} from 'react';
import {
  components,
  MultiValueGenericProps,
  MultiValueProps,
  OnChangeValue,
  Props,
} from 'react-select';
import {
  SortableContainer,
  SortableContainerProps,
  SortableElement,
  SortableHandle,
  SortEndHandler,
} from 'react-sortable-hoc';
import styled from 'styled-components';

import {
  constString,
  isConstNode,
  isOutputNode,
  NodeOrVoidNode,
  opDict,
  opPick,
  varNode,
  voidNode,
} from '../../../core';
import {Select} from '../../Form/Select';
import {Icon, IconName} from '../../Icon';
import * as TableState from '../PanelTable/tableState';
import {Column, Columns} from './columnHelpers';
import {ColumnWithExpressionDimension} from './ColumnWithExpressionDimension';
import {PanelPlotProps} from './types';
import {PlotConfig, SeriesConfig} from './versions';

const SelectOptionLabel = styled.div`
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  gap: 8px;
`;
SelectOptionLabel.displayName = 'S.SelectOptionLabel';

const SelectOptionLabelText = styled.span`
  text-overflow: ellipsis;
  white-space: nowrap;
`;
SelectOptionLabelText.displayName = 'S.SelectOptionLabelText';

const OptionLabel = (props: ColumnOption) => {
  return (
    <SelectOptionLabel>
      <Icon name={props.icon} />
      <SelectOptionLabelText>{props.label}</SelectOptionLabelText>
    </SelectOptionLabel>
  );
};

type SelectColumnProps = {
  columns: Columns;
  dimension: ColumnWithExpressionDimension;
  input: PanelPlotProps['input'];
  config: PlotConfig;
  updateConfig: PanelPlotProps['updateConfig'];
  series: SeriesConfig[];
};
export type ColumnOption = {
  value: string;
  label: string;
  columnType: string;
  icon: IconName;
};

const TYPE_TO_ICON: Record<string, IconName> = {
  string: 'text-language-alt',
  number: 'number',
  timestamp: 'date',
  image: 'photo',
  audio: 'music-audio',
};

const getIconForType = (type: string): IconName => {
  return TYPE_TO_ICON[type] ?? 'cube-container'; // TODO: Is there a better default icon?
};
// const OptionLabel = (props: JobOption) => {
//   return (
//     <S.SelectOptionLabel>
//       <S.SelectOptionLabelText>{props.label}</S.SelectOptionLabelText>
//     </S.SelectOptionLabel>
//   );
// };

function arrayMove<T>(array: readonly T[], from: number, to: number) {
  const slicedArray = array.slice();
  slicedArray.splice(
    to < 0 ? array.length + to : to,
    0,
    slicedArray.splice(from, 1)[0]
  );
  return slicedArray;
}

const SortableMultiValue = SortableElement(
  (props: MultiValueProps<ColumnOption>) => {
    // this prevents the menu from being opened/closed when the user clicks
    // on a value to begin dragging it. ideally, detecting a click (instead of
    // a drag) would still focus the control and toggle the menu, but that
    // requires some magic with refs that are out of scope for this example
    const onMouseDown: MouseEventHandler<HTMLDivElement> = e => {
      e.preventDefault();
      e.stopPropagation();
    };
    const innerProps = {...props.innerProps, onMouseDown};
    return <components.MultiValue {...props} innerProps={innerProps} />;
  }
);

const SortableMultiValueLabel = SortableHandle(
  (props: MultiValueGenericProps) => <components.MultiValueLabel {...props} />
);

const SortableSelect = SortableContainer(Select) as React.ComponentClass<
  Props<ColumnOption, true> & SortableContainerProps
>;

const SelectColumnSingle = ({
  dimension,
  columns,
  input,
  config,
  updateConfig,
  series,
}: SelectColumnProps) => {
  const options: ColumnOption[] = columns
    .map((column: Column) => {
      const dotted = column.path.join('.');
      const columnType = column.type;
      // TODO: keep value as array of strings?
      return {
        value: dotted,
        label: dotted,
        columnType,
        icon: getIconForType(columnType),
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label));

  const ser = series[0];
  // const dimName = dimension.name === 'label' ? 'color' : dimension.name; // TODO
  const dimName = dimension.name;
  const tableCol = ser.dims[dimName];
  const func = ser.table.columnSelectFunctions[tableCol];
  let selectedOpt = null;
  if (
    isOutputNode(func) &&
    func.fromOp.name === 'pick' &&
    isConstNode(func.fromOp.inputs.key)
  ) {
    // Handle case where expression is something like row["label"]
    const selectedVal = func.fromOp.inputs.key.val;
    selectedOpt = _.find(options, {value: selectedVal}) ?? null;
  }

  const [selected, setSelected] = React.useState<ColumnOption | null>(
    selectedOpt
  );

  const seriesIndices = useMemo(
    () => series.map(s => config.series.indexOf(s)),
    [series, config.series]
  );

  const onChange = (selectedOption: OnChangeValue<ColumnOption, false>) => {
    setSelected(selectedOption);
    const exampleRow = TableState.getExampleRow(input);
    const newConfig = produce(config, draft => {
      seriesIndices.forEach(i => {
        const s = draft.series[i];

        // draft.forEach(s => {
        //     // if (sion.series)) {
        //     //   // @ts-ignore
        //     //   s.constants[dimName] = value;
        //     // }
        //     // const tooltip: any = {};
        //     // selectedOptions.forEach((option: ColumnOption) => {
        //     //   const colId = option.value; // e.g. gdp
        //     //   const value = opPick({
        //     //     obj: varNode(exampleRow.type, 'row'),
        //     //     key: constString(colId),
        //     //   });
        //       // const value = constString('value');
        //       // const colType = s.table.columnSelectFunctions[colId].type;
        //       // console.log({colId, colType});
        //       // console.log({colId});
        //       // tooltip[option.value] = constString(option.value);
        //       // tooltip[option.value] = value;
        //     });
        //     // const node = _.isEmpty(tooltip) ? voidNode() : opDict(tooltip);
        //     // s.table = TableState.updateColumnSelect(
        //     //   s.table,
        //     //   s.dims['tooltip'], // fixme
        //     //   node
        //     // );
        const node = selectedOption
          ? opPick({
              obj: varNode(exampleRow.type, 'row'),
              key: constString(selectedOption.value),
            })
          : voidNode();
        s.table = TableState.updateColumnSelect(s.table, s.dims[dimName], node);
      });
    });
    updateConfig(newConfig);
    // updateConfig({
    //   series: newSeries,
    // });
  };

  //   const onChange = (newValue: MultiValue<ColumnOption>) => {
  //     console.log('onChange');
  //     console.log(newValue);
  //     // if (option) {
  //     //   onSelectJob(option);
  //     // }
  //   };
  return (
    <Select
      options={options}
      placeholder="Select a column..."
      onChange={onChange}
      //   value={selectedJobId as any}
      formatOptionLabel={OptionLabel}
      value={selected}
      //   onChange={onChange}
    />
  );
};

const SelectColumnMultiple = ({
  dimension,
  columns,
  input,
  config,
  updateConfig,
  series,
}: SelectColumnProps) => {
  const options: ColumnOption[] = columns
    .map((column: Column) => {
      const dotted = column.path.join('.');
      const columnType = column.type;
      // TODO: keep value as array of strings?
      return {
        value: dotted,
        label: dotted,
        columnType,
        icon: getIconForType(columnType),
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label));

  const ser = series[0];
  // const dimName = dimension.name === 'label' ? 'color' : dimension.name; // TODO
  const dimName = dimension.name;
  const tableCol = ser.dims[dimName];
  const func = ser.table.columnSelectFunctions[tableCol];
  let selectedOptions: ColumnOption[] = [];
  if (isOutputNode(func)) {
    if (func.fromOp.name === 'pick' && isConstNode(func.fromOp.inputs.key)) {
      // Handle case where expression is something like row["Image"]
      const selectedKey = func.fromOp.inputs.key.val;
      selectedOptions = options.filter(o => {
        return selectedKey === o.value;
      });
    } else if (func.fromOp.name === 'dict') {
      // Handle case where expression is a dict like {name: row["name"]}
      // TODO: Could have more checks here about the expected type of the values.
      const selectedKeys = Object.keys(func.fromOp.inputs);
      selectedOptions = options.filter(o => {
        return selectedKeys.includes(o.value);
      });
    }
  }

  // console.log({columns, input, config, dimension});
  // console.log({selectedVal, series, tableCol, func});

  const [selected, setSelected] =
    React.useState<readonly ColumnOption[]>(selectedOptions);

  const seriesIndices = useMemo(
    () => series.map(s => config.series.indexOf(s)),
    [series, config.series]
  );

  const onChange = (selectedOpts: OnChangeValue<ColumnOption, true>) => {
    setSelected(selectedOpts);
    const exampleRow = TableState.getExampleRow(input);
    const newConfig = produce(config, draft => {
      seriesIndices.forEach(i => {
        const s = draft.series[i];
        // if (isShared || _.isEqual(s, dimension.series)) {
        //   // @ts-ignore
        //   s.constants[dimName] = value;
        // }

        let node: NodeOrVoidNode = voidNode();
        if (selectedOpts.length > 0) {
          // TODO: Images don't render as values in dict tooltips.
          //       We should fix that.
          //       https://wandb.atlassian.net/browse/WB-16692
          //       For now, special case having a single image column selection
          if (
            selectedOpts.length === 1 &&
            selectedOpts[0].columnType === 'image'
          ) {
            node = opPick({
              obj: varNode(exampleRow.type, 'row'),
              key: constString(selectedOpts[0].value),
            });
          } else {
            // Keep the dict format since seems nice to have a label for value?
            const tooltip: any = {};
            selectedOpts.forEach((option: ColumnOption) => {
              const colId = option.value; // e.g. gdp
              const value = opPick({
                obj: varNode(exampleRow.type, 'row'),
                key: constString(colId),
              });
              tooltip[option.value] = value;
            });
            node = opDict(tooltip);
          }
        }

        s.table = TableState.updateColumnSelect(
          s.table,
          s.dims[dimension.name],
          node
        );
      });
    });
    updateConfig(newConfig);
  };

  const onSortEnd: SortEndHandler = ({oldIndex, newIndex}) => {
    const newValue = arrayMove(selected, oldIndex, newIndex);
    setSelected(newValue);
    // console.log(
    //   'Values sorted:',
    //   newValue.map(i => i.value)
    // );
    onChange(newValue);
  };

  //   const onChange = (newValue: MultiValue<ColumnOption>) => {
  //     console.log('onChange');
  //     console.log(newValue);
  //     // if (option) {
  //     //   onSelectJob(option);
  //     // }
  //   };
  return (
    <SortableSelect
      useDragHandle
      // react-sortable-hoc props:
      axis="xy"
      onSortEnd={onSortEnd}
      distance={4}
      // small fix for https://github.com/clauderic/react-sortable-hoc/pull/352:
      getHelperDimensions={({node}) => node.getBoundingClientRect()}
      size="variable"
      options={options}
      isMulti
      placeholder="Select columns..."
      onChange={onChange}
      //   value={selectedJobId as any}
      formatOptionLabel={OptionLabel}
      value={selected}
      //   onChange={onChange}
      components={{
        // @ts-ignore We're failing to provide a required index prop to SortableElement
        MultiValue: SortableMultiValue,
        MultiValueLabel: SortableMultiValueLabel,
      }}
      closeMenuOnSelect={false}
    />
  );
};

export const SelectColumn = (props: SelectColumnProps) => {
  return props.dimension.isMulti ? (
    <SelectColumnMultiple {...props} />
  ) : (
    <SelectColumnSingle {...props} />
  );
};
