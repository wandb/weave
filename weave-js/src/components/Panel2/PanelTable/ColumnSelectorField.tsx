import {
  dynamicMatchHighlight,
  MatchMode,
} from '@wandb/weave/common/util/columnMatching';
import React, {useCallback, useRef, useState} from 'react';
import {Icon, List} from 'semantic-ui-react';

import {ColumnEntry, TableState} from './tableState';

interface TableEditorColumnFieldProps {
  disabled: boolean;
  colName: string;
  colId?: string;
  icon?: string;
  config: TableState;
  dragging: boolean;
  searchQuery: string;
  searchMode: MatchMode;
  onDragStart: any;
  onDragEnd: any;
  onClick: any;
  onDrop(column: ColumnEntry): void;
}

const ColumnSelectorField: React.FC<TableEditorColumnFieldProps> = React.memo(
  ({
    disabled,
    colName,
    colId,
    icon,
    config,
    dragging,
    searchQuery,
    searchMode,
    onDragStart,
    onDragEnd,
    onClick,
    onDrop,
  }) => {
    // Count leave/enter events, because they fire in pairs when we drag over our
    // own children's boundaries.
    const [draggingOver, setDraggingOver] = useState(0);

    const selfRef = useRef<HTMLDivElement | null>(null);

    const onDragEnter = useCallback(() => {
      setDraggingOver(prev => prev + 1);
    }, []);
    const onDragLeave = useCallback((e: any) => {
      setDraggingOver(prev => prev - 1);
    }, []);

    const visible = !!config.columns[colName];
    return (
      <List.Item
        key={colName}
        ref={selfRef}
        className={
          'column-field-wrapper' +
          (dragging ? ' dragging' : '') +
          (visible && draggingOver !== 0 ? ' drop' : '') +
          (disabled ? ' disabled' : '')
        }
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragEnd={onDragEnd}
        onDragOver={(e: React.SyntheticEvent) => {
          e.preventDefault(); // this is necessary for onDrop to work
        }}
        onDrop={() => {
          setDraggingOver(0);
          onDrop({name: colName, id: colId});
        }}>
        <div
          className="column-field"
          draggable={!disabled}
          onDragStart={onDragStart}
          onClick={onClick}>
          <Icon className={`section-icon wbic-ic-${icon ?? 'metadata'}`} />
          <span className="column-name">
            {dynamicMatchHighlight(searchMode, colName, searchQuery)}
          </span>
        </div>
      </List.Item>
    );
  }
);

export default ColumnSelectorField;
