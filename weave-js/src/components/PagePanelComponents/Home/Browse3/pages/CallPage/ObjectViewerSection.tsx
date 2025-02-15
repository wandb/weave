import Box from '@mui/material/Box';
import {GridRowId, useGridApiRef} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import styled from 'styled-components';

import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {Alert} from '../../../../../Alert';
import {Button} from '../../../../../Button';
import {CodeEditor} from '../../../../../CodeEditor';
import {Icon} from '../../../../../Icon';
import {isWeaveRef} from '../../filters/common';
import {isCustomWeaveTypePayload} from '../../typeViews/customWeaveType.types';
import {CustomWeaveTypeDispatcher} from '../../typeViews/CustomWeaveTypeDispatcher';
import {OBJECT_ATTR_EDGE_NAME} from '../wfReactInterface/constants';
import {WeaveCHTable, WeaveCHTableSourceRefContext} from './DataTableView';
import {ObjectViewer} from './ObjectViewer';
import {getValueType, traverse} from './traverse';
import {ValueView} from './ValueView';

type Mode = 'collapsed' | 'expanded' | 'json';

function isModeCollapsed(mode: Mode): boolean {
  return mode === 'collapsed';
}

function isModeExpanded(mode: Mode): boolean {
  return mode === 'expanded';
}

function isModeJson(mode: Mode): boolean {
  return mode === 'json';
}

function isModeCollapsedOrExpanded(mode: Mode): boolean {
  return isModeCollapsed(mode) || isModeExpanded(mode);
}

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
  font-size: 14px;
  font-weight: 600;
  line-height: 32px;
  letter-spacing: 0px;
  text-align: left;
  display: flex;
  align-items: center;
  cursor: pointer;

  &:hover {
    opacity: 0.8;
  }
`;
Title.displayName = 'S.Title';

// We'll automatically expand objects if they are "simple" enough.
// This is a heuristic for what that means.
const isSimpleData = (data: Data): boolean => {
  let isSimple = true;
  traverse(data, context => {
    if (context.depth > 3) {
      isSimple = false;
      return false;
    }
    if (isWeaveRef(context.value)) {
      isSimple = false;
      return false;
    }
    if (context.valueType === 'array' && context.value.length > 10) {
      isSimple = false;
      return false;
    }
    if (
      context.valueType === 'object' &&
      Object.keys(context.value).length > 10
    ) {
      isSimple = false;
      return false;
    }
    return undefined;
  });
  return isSimple;
};

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
  const [mode, setMode] = useState<Mode>('collapsed');
  const [isViewerHidden, setIsViewerHidden] = useState(false);
  const [expandedIds, setExpandedIds] = useState<GridRowId[]>([]);

  const body = useMemo(() => {
    if (isViewerHidden) {
      return null;
    }
    if (isModeCollapsedOrExpanded(mode)) {
      return (
        <ObjectViewer
          apiRef={apiRef}
          data={data}
          isExpanded={isModeExpanded(mode)}
          expandedIds={expandedIds}
          setExpandedIds={setExpandedIds}
        />
      );
    }
    if (isModeJson(mode)) {
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
  }, [mode, apiRef, data, expandedIds, isViewerHidden]);

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
  const onClickCollapsed = () => {
    if (isModeCollapsed(mode)) {
      setTreeExpanded(false);
    }
    setMode('collapsed');
    setExpandedIds([]);
  };

  const isExpandAllSmall =
    !!apiRef?.current?.getAllRowIds &&
    getGroupIds().length - expandedIds.length < EXPANDED_IDS_LENGTH;

  const onClickExpanded = () => {
    if (isModeExpanded(mode)) {
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
  };

  // On first render and when data changes, recompute expansion state
  useEffect(() => {
    if (isViewerHidden || isModeJson(mode)) {
      return;
    }
    const isSimple = isSimpleData(data);
    const newMode = isSimple || isExpanded ? 'expanded' : 'collapsed';
    if (newMode === 'expanded') {
      onClickExpanded();
    } else {
      onClickCollapsed();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, isExpanded]);

  return (
    <Box sx={{height: '100%', display: 'flex', flexDirection: 'column'}}>
      <TitleRow>
        <Title onClick={() => setIsViewerHidden(!isViewerHidden)}>
          <Icon
            name={isViewerHidden ? 'chevron-next' : 'chevron-down'}
            width={16}
            height={16}
            style={{marginRight: '8px'}}
          />
          {title}
        </Title>
        {!isViewerHidden && (
          <>
            <Button
              variant="ghost"
              icon="collapse"
              onClick={onClickCollapsed}
              tooltip="Collapse all"
              active={isModeCollapsed(mode)}
            />
            <Button
              variant="ghost"
              icon="expand-uncollapse"
              onClick={onClickExpanded}
              tooltip={
                isExpandAllSmall
                  ? 'Expand all'
                  : `Expand next ${EXPANDED_IDS_LENGTH} rows`
              }
              active={isModeExpanded(mode)}
            />
            <Button
              variant="ghost"
              icon="code-alt"
              active={isModeJson(mode)}
              onClick={() => setMode('json')}
              tooltip="View as JSON"
            />
          </>
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
