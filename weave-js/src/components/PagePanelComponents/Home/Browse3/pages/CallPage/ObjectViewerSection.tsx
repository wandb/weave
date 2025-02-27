import Box from '@mui/material/Box';
import {GridRowId, useGridApiRef} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useCallback, useContext, useMemo, useState} from 'react';
import styled from 'styled-components';

import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {Alert} from '../../../../../Alert';
import {Button} from '../../../../../Button';
import {CodeEditor} from '../../../../../CodeEditor';
import {isWeaveRef} from '../../filters/common';
import {isCustomWeaveTypePayload} from '../../typeViews/customWeaveType.types';
import {CustomWeaveTypeDispatcher} from '../../typeViews/CustomWeaveTypeDispatcher';
import {OBJECT_ATTR_EDGE_NAME} from '../wfReactInterface/constants';
import {WeaveCHTable, WeaveCHTableSourceRefContext} from './DataTableView';
import {ObjectViewer} from './ObjectViewer';
import {getValueType} from './traverse';
import {ValueView} from './ValueView';

const EXPANDED_IDS_LENGTH = 200;

type Data = Record<string, any>;

type ObjectViewerSectionProps = {
  title: string;
  data: Data;
  noHide?: boolean;
  isExpanded?: boolean;
};

const TitleRow = styled.div`
  display: flex;
  align-items: center;
  margin-bottom: 4px;
`;
TitleRow.displayName = 'S.TitleRow';

const Title = styled.div`
  flex: 1 1 auto;
  font-family: Source Sans Pro;
  font-size: 16px;
  font-weight: 600;
  line-height: 32px;
  letter-spacing: 0px;
  text-align: left;
`;
Title.displayName = 'S.Title';

// Use a deep comparison to avoid re-rendering when the data object hasn't really changed.
const ObjectViewerSectionNonEmptyMemoed = React.memo(
  (props: ObjectViewerSectionProps) => (
    <ObjectViewerSectionNonEmpty {...props} />
  ),
  (prevProps, nextProps) => _.isEqual(prevProps, nextProps)
);

const ObjectViewerSectionNonEmpty = ({
  title,
  data,
  noHide,
  isExpanded,
}: ObjectViewerSectionProps) => {
  const apiRef = useGridApiRef();
  const [mode, setMode] = useState('collapsed');
  const [expandedIds, setExpandedIds] = useState<GridRowId[]>([]);

  const body = useMemo(() => {
    if (mode === 'collapsed' || mode === 'expanded') {
      return (
        <ObjectViewer
          apiRef={apiRef}
          data={data}
          isExpanded={mode === 'expanded'}
          expandedIds={expandedIds}
          setExpandedIds={setExpandedIds}
        />
      );
    }
    if (mode === 'json') {
      return (
        <CodeEditor
          value={JSON.stringify(data, null, 2)}
          language="json"
          handleMouseWheel
          alwaysConsumeMouseWheel={false}
          readOnly
        />
      );
    }
    return null;
  }, [mode, apiRef, data, expandedIds]);

  const setTreeExpanded = useCallback(
    (setIsExpanded: boolean) => {
      const rowIds = apiRef.current.getAllRowIds();
      rowIds.forEach(rowId => {
        const rowNode = apiRef.current.getRowNode(rowId);
        if (rowNode && rowNode.type === 'group') {
          apiRef.current.setRowChildrenExpansion(rowId, setIsExpanded);
        }
      });
    },
    [apiRef]
  );
  const getGroupIds = useCallback(() => {
    const rowIds = apiRef.current.getAllRowIds();
    return rowIds.filter(rowId => {
      const rowNode = apiRef.current.getRowNode(rowId);
      return rowNode && rowNode.type === 'group';
    });
  }, [apiRef]);

  // Re-clicking the button will reapply collapse/expand
  const onClickCollapsed = useCallback(() => {
    if (mode === 'collapsed') {
      setTreeExpanded(false);
    }
    setMode('collapsed');
    setExpandedIds([]);
  }, [mode, setTreeExpanded]);

  const isExpandAllSmall = useMemo(() => {
    return (
      !!apiRef?.current?.getAllRowIds &&
      getGroupIds().length - expandedIds.length < EXPANDED_IDS_LENGTH
    );
  }, [apiRef, expandedIds.length, getGroupIds]);

  const onClickExpanded = useCallback(() => {
    if (mode === 'expanded') {
      setTreeExpanded(true);
    }
    setMode('expanded');
    if (isExpandAllSmall) {
      setExpandedIds(getGroupIds());
    } else {
      setExpandedIds(
        getGroupIds().slice(0, expandedIds.length + EXPANDED_IDS_LENGTH)
      );
    }
  }, [
    expandedIds.length,
    getGroupIds,
    isExpandAllSmall,
    mode,
    setTreeExpanded,
  ]);

  return (
    <Box sx={{height: '100%', display: 'flex', flexDirection: 'column'}}>
      <TitleRow>
        <Title>{title}</Title>
        <Button
          variant="ghost"
          icon="row-height-small"
          active={mode === 'collapsed'}
          onClick={onClickCollapsed}
          tooltip="View collapsed"
        />
        <Button
          variant="ghost"
          icon="expand-uncollapse"
          active={mode === 'expanded'}
          onClick={onClickExpanded}
          tooltip={
            isExpandAllSmall
              ? 'Expand all'
              : `Expand next ${EXPANDED_IDS_LENGTH} rows`
          }
        />
        <Button
          variant="ghost"
          icon="code-alt"
          active={mode === 'json'}
          onClick={() => setMode('json')}
          tooltip="View as JSON"
        />
        {!noHide && (
          <Button
            variant="ghost"
            icon="hide-hidden"
            active={mode === 'hidden'}
            onClick={() => setMode('hidden')}
            tooltip="Hide"
          />
        )}
      </TitleRow>
      {body}
    </Box>
  );
};

export const ObjectViewerSection = ({
  title,
  data,
  noHide,
  isExpanded,
}: ObjectViewerSectionProps) => {
  const currentRef = useContext(WeaveCHTableSourceRefContext);

  if (isCustomWeaveTypePayload(data)) {
    return (
      <>
        <TitleRow>
          <Title>{title}</Title>
        </TitleRow>
        <CustomWeaveTypeDispatcher data={data} />
      </>
    );
  }

  const numKeys = Object.keys(data).length;
  if (numKeys === 0) {
    return (
      <>
        <TitleRow>
          <Title>{title}</Title>
        </TitleRow>
        <Alert>None</Alert>
      </>
    );
  }
  if (numKeys === 1 && '_result' in data) {
    let value = data._result;
    if (isWeaveRef(value)) {
      // Little hack to make sure that we render refs
      // inside the expansion table view
      value = {' ': value};
    }
    const valueType = getValueType(value);
    if (valueType === 'object' || (valueType === 'array' && value.length > 0)) {
      return (
        <ObjectViewerSectionNonEmptyMemoed
          title={title}
          data={value}
          noHide={noHide}
          isExpanded={isExpanded}
        />
      );
    }
    const oneResultData = {
      value,
      valueType,
      isLeaf: true,
    };
    return (
      <>
        <TitleRow>
          <Title>{title}</Title>
        </TitleRow>
        <ValueView data={oneResultData} isExpanded={true} />
      </>
    );
  }

  // Here we have a very special case for when the section is viewing a dataset.
  // Instead of rending the generic renderer, we directly render a full-screen
  // data table.
  if (
    data._type === 'Dataset' &&
    data._class_name === 'Dataset' &&
    _.isEqual(data._bases, ['Object', 'BaseModel'])
  ) {
    const parsed = parseRef(data.rows);
    if (isWeaveObjectRef(parsed) && parsed.weaveKind === 'table') {
      const inner = (
        <Box
          sx={{
            height: '100%',
            overflow: 'hidden',
          }}>
          <WeaveCHTable tableRefUri={data.rows} fullHeight />
        </Box>
      );
      if (currentRef != null) {
        return (
          <WeaveCHTableSourceRefContext.Provider
            value={currentRef + '/' + OBJECT_ATTR_EDGE_NAME + '/rows'}>
            {inner}
          </WeaveCHTableSourceRefContext.Provider>
        );
      }
      return inner;
    }
  }
  return (
    <ObjectViewerSectionNonEmpty
      title={title}
      data={data}
      noHide={noHide}
      isExpanded={isExpanded}
    />
  );
};
