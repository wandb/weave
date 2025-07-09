import {Box, Collapse} from '@mui/material';
import {GridRowId, useGridApiRef} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useCallback, useContext, useMemo, useState} from 'react';
import {Button} from '../../../../../Button';
import {CodeEditor} from '../../../../../CodeEditor';
import {MetadataViewer} from './MetadataViewer';
import {Subheader} from './Styles';

type MetadataViewerSectionProps = {
  title: string;
  data: Data;
  open?: boolean;
  error?: string;
};
const EXPANDED_IDS_LENGTH = 200;

type Data = Record<string, any>;

const MetadataViewerSectionInner = ({
  title,
  data,
  open
}: MetadataViewerSectionProps) => {
  const apiRef = useGridApiRef();
  // Update this when we change the state to hidden
  // That way it restores the last state when uncollapsed
  const [isOpen, setIsOpen] = useState(open ?? false);
  const [mode, setMode] = useState('collapsed');
  const [expandedIds, setExpandedIds] = useState<GridRowId[]>([]);

  const body = useMemo(() => {
    if (mode === 'collapsed' || mode === 'expanded') {
      return (
        <MetadataViewer
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
  }, [isOpen, mode, apiRef, data, expandedIds]);

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
  const buttonSection = (
    <div>
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
    </div>
  );

  const headerSection = (
    <div>
      <div style={{ display: 'flex', minHeight: "32px" }}>
        <Button
          onClick={() => { setIsOpen(!isOpen) }}
          variant='ghost'
          size='small'
          icon={isOpen ? "chevron-down" : "chevron-next"}
          style={{fontSize: "14px"}}
        >
          <Subheader>{title}</Subheader>
        </Button>
      </div>
    </div>
  );

  return (
    <div style={{height: '100%', display: 'flex', flexDirection: 'column', margin: 0, padding: 0, gap: 8}}>
      <div style={{height: '100%', display: 'flex', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center'}}>
        {headerSection}
        {isOpen && buttonSection}
      </div>
      <Collapse in={isOpen}>
        {body}
      </Collapse>
    </div>
  );
}

// Use a deep comparison to avoid re-rendering when the data object hasn't really changed.
const MetadataViewerSectionMemoed = React.memo(
  (props: MetadataViewerSectionProps) => (
    <MetadataViewerSectionInner {...props} />
  ),
  (prevProps, nextProps) => _.isEqual(prevProps, nextProps)
);

export const MetadataViewerSection = (props: MetadataViewerSectionProps) => {
  return <MetadataViewerSectionMemoed {...props} />
}

