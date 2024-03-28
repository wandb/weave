import {useGridApiRef} from '@mui/x-data-grid-pro';
import React, {useCallback, useContext, useMemo, useState} from 'react';
import styled from 'styled-components';

import {Button} from '../../../../../Button';
import {CodeEditor} from '../../../../../CodeEditor';
import {isRef} from '../common/util';
import {ObjectViewer} from './ObjectViewer';
import {getValueType, traverse} from './traverse';
import {ValueView} from './ValueView';

type Data = Record<string, any>;

type ObjectViewerSectionProps = {
  title: string;
  data: Data;
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

// We'll automatically expand objects if they are "simple" enough.
// This is a heuristic for what that means.
const isSimpleData = (data: Data): boolean => {
  let isSimple = true;
  traverse(data, context => {
    if (context.depth > 3) {
      isSimple = false;
      return false;
    }
    if (isRef(context.value)) {
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

export const ObjectViewerSection = ({
  title,
  data,
}: ObjectViewerSectionProps) => {
  const apiRef = useGridApiRef();
  const [mode, setMode] = useState(
    isSimpleData(data) ? 'expanded' : 'collapsed'
  );

  const isOneValue = '_result' in data;
  const baseRef = useContext(ObjectViewerSectionContext);

  const body = useMemo(() => {
    if (mode === 'collapsed' || mode === 'expanded') {
      if (isOneValue) {
        const oneResultData = {
          value: data._result,
          valueType: getValueType(data._result),
          isLeaf: true,
        };
        return (
          <ValueView data={oneResultData} isExpanded={true} baseRef={baseRef} />
        );
      }
      return (
        <ObjectViewer
          apiRef={apiRef}
          data={data}
          isExpanded={mode === 'expanded'}
        />
      );
    }
    if (mode === 'json') {
      return (
        <CodeEditor
          value={JSON.stringify(data, null, 2)}
          language="json"
          readOnly
        />
      );
    }
    return null;
  }, [mode, isOneValue, apiRef, data, baseRef]);

  const setTreeExpanded = useCallback(
    (isExpanded: boolean) => {
      const rowIds = apiRef.current.getAllRowIds();
      rowIds.forEach(rowId => {
        const rowNode = apiRef.current.getRowNode(rowId);
        if (rowNode && rowNode.type === 'group') {
          apiRef.current.setRowChildrenExpansion(rowId, isExpanded);
        }
      });
    },
    [apiRef]
  );

  // Re-clicking the button will reapply collapse/expand
  const onClickCollapsed = () => {
    if (mode === 'collapsed') {
      setTreeExpanded(false);
    }
    setMode('collapsed');
  };
  const onClickExpanded = () => {
    if (mode === 'expanded') {
      setTreeExpanded(true);
    }
    setMode('expanded');
  };

  return (
    <>
      <TitleRow>
        <Title>{title}</Title>
        <Button
          variant="quiet"
          icon="row-height-small"
          active={mode === 'collapsed'}
          onClick={onClickCollapsed}
          tooltip="View collapsed"
        />
        <Button
          variant="quiet"
          icon="expand-uncollapse"
          active={mode === 'expanded'}
          onClick={onClickExpanded}
          tooltip="View expanded"
        />
        <Button
          variant="quiet"
          icon="code-alt"
          active={mode === 'json'}
          onClick={() => setMode('json')}
          tooltip="View as JSON"
        />
        <Button
          variant="quiet"
          icon="hide-hidden"
          active={mode === 'hidden'}
          onClick={() => setMode('hidden')}
          tooltip="Hide"
        />
      </TitleRow>
      {body}
    </>
  );
};

// Create a context that can be consumed by ObjectViewerSection
export const ObjectViewerSectionContext = React.createContext<
  string | undefined
>(undefined);
