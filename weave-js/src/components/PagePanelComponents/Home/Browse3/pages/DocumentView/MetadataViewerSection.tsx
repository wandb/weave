import {Collapse} from '@mui/material';
import {GridRowId, useGridApiRef} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {Fragment, useCallback, useMemo, useState} from 'react';

import {Button} from '../../../../../Button';
import {CodeEditor} from '../../../../../CodeEditor';
import {ObjectViewer} from '../CallPage/ObjectViewer';
import {Subheader} from './StyledText';

const EXPANDED_IDS_LENGTH = 200;

type Data = Record<string, any>;

type MetadataViewerSectionProps = {
  title: string;
  data: Data;
  open?: boolean;
  error?: string;
};

enum ViewerMode {
  Collapsed,
  Expanded,
  Json,
}

const MetadataViewerSectionInner = ({
  title,
  data,
  open,
}: MetadataViewerSectionProps) => {
  const apiRef = useGridApiRef();
  // Update this when we change the state to hidden
  // That way it restores the last state when uncollapsed
  const [isOpen, setIsOpen] = useState(open ?? false);
  const [mode, setMode] = useState(ViewerMode.Collapsed);
  const [expandedIds, setExpandedIds] = useState<GridRowId[]>([]);

  const body = useMemo(() => {
    if (mode === ViewerMode.Collapsed || mode === ViewerMode.Expanded) {
      return (
        <Fragment>
          <ObjectViewer
            apiRef={apiRef}
            data={data}
            isExpanded={mode === ViewerMode.Expanded}
            expandedIds={expandedIds}
            setExpandedIds={setExpandedIds}
            hideHeaders={true}
            truncateOverflow={true}
            groupingFixedWidth={125}
            cellGroupingInset={30}
          />
        </Fragment>
      );
    }
    if (mode === ViewerMode.Json) {
      return (
        <Fragment>
          <CodeEditor
            value={JSON.stringify(data, null, 2)}
            language="json"
            handleMouseWheel
            alwaysConsumeMouseWheel={false}
            readOnly
          />
        </Fragment>
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
    if (mode === ViewerMode.Collapsed) {
      setTreeExpanded(false);
    }
    setMode(ViewerMode.Collapsed);
    setExpandedIds([]);
  }, [mode, setTreeExpanded]);

  const isExpandAllSmall = useMemo(() => {
    return (
      !!apiRef?.current?.getAllRowIds &&
      getGroupIds().length - expandedIds.length < EXPANDED_IDS_LENGTH
    );
  }, [apiRef, expandedIds.length, getGroupIds]);

  const onClickExpanded = useCallback(() => {
    if (mode === ViewerMode.Expanded) {
      setTreeExpanded(true);
    }
    setMode(ViewerMode.Expanded);
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
        active={mode === ViewerMode.Collapsed}
        onClick={onClickCollapsed}
        tooltip="View collapsed"
      />
      <Button
        variant="ghost"
        icon="expand-uncollapse"
        active={mode === ViewerMode.Expanded}
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
        active={mode === ViewerMode.Json}
        onClick={() => setMode(ViewerMode.Json)}
        tooltip="View as JSON"
      />
    </div>
  );

  const headerSection = (
    <div>
      <div className="tw-style flex h-32">
        <Button
          onClick={() => {
            setIsOpen(!isOpen);
          }}
          variant="ghost"
          size="small"
          icon={isOpen ? 'chevron-down' : 'chevron-next'}
          className="tw-style text-14">
          <Subheader>{title}</Subheader>
        </Button>
      </div>
    </div>
  );

  return (
    <div className="tw-style m-0 flex h-full flex-col p-0">
      <div className="tw-style flex h-full flex-row items-center justify-between">
        {headerSection}
        {isOpen && buttonSection}
      </div>
      <Collapse
        in={isOpen}
        className="tw-style [&_.MuiCollapse-wrapperInner]:min-h-[50px] [&_.MuiCollapse-wrapperInner]:pt-8">
        {body}
      </Collapse>
    </div>
  );
};

// Use a deep comparison to avoid re-rendering when the data object hasn't really changed.
const MetadataViewerSectionMemoed = React.memo(
  (props: MetadataViewerSectionProps) => (
    <MetadataViewerSectionInner {...props} />
  ),
  (prevProps, nextProps) => _.isEqual(prevProps, nextProps)
);

export const MetadataViewerSection = (props: MetadataViewerSectionProps) => {
  return <MetadataViewerSectionMemoed {...props} />;
};
