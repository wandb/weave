import {Box, Popover, SxProps} from '@mui/material';
import {
  GridColDef,
  GridColumnGroupingModel,
  GridColumnHeaderParams,
  GridColumnNode,
  GridEventListener,
  GridFooter,
  GridFooterContainer,
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import {Icon} from '@wandb/weave/components/Icon';
import {IconButton} from '@wandb/weave/components/IconButton';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {CellValue} from '@wandb/weave/components/PagePanelComponents/Home/Browse2/CellValue';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {parseRefMaybe} from '@wandb/weave/react';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {
  HIDE_TRACETREE_PARAM,
  SHOW_FEEDBACK_PARAM,
  usePeekLocation,
  useWeaveflowRouteContext,
} from '../../../../../context';
import {NotApplicable} from '../../../../../NotApplicable';
import {SmallRef} from '../../../../../smallRef/SmallRef';
import {StyledDataGrid} from '../../../../../StyledDataGrid';
import {IdPanel} from '../../../../common/Id';
import {CallLink} from '../../../../common/Links';
import {
  CompareEvaluationContext,
  useCompareEvaluationsState,
} from '../../compareEvaluationsContext';
import {
  buildCompositeMetricsMap,
  DERIVED_SCORER_REF_PLACEHOLDER,
} from '../../compositeMetricsUtil';
import {EvaluationComparisonState} from '../../ecpState';
import {filterLatestCallIdsPerModelDataset} from '../../latestEvaluationUtil';
import {HorizontalBox} from '../../Layout';
import {EvaluationModelLink} from '../ComparisonDefinitionSection/EvaluationDefinition';
import {
  ColumnsManagementPanel,
  CUSTOM_GROUP_KEY_TO_CONTROL_CHILDREN_VISIBILITY,
} from './ColumnsManagementPanel';
import {
  evalAggScorerMetricCompGeneric,
  lookupMetricValueDirect,
} from './ExampleCompareSectionDetail';
import {
  FilteredAggregateRows,
  PivotedRow,
  removePrefix,
  useExampleCompareData,
  useFilteredAggregateRows,
} from './exampleCompareSectionUtil';

const styledDataGridStyleOverrides: SxProps = {
  borderTop: 0,
  '& .MuiDataGrid-row:hover': {
    backgroundColor: 'white',
  },
  '& .MuiDataGrid-row.Mui-selected:hover': {
    // match the non-hover background color
    backgroundColor: 'rgba(169, 237, 242, 0.32)',
  },
  '& .MuiDataGrid-cell--pinnedLeft': {
    backgroundColor: 'white',
    zIndex: '7 !important',
  },
  '& .MuiDataGrid-footerContainer': {
    minHeight: '40px !important',
  },
  '& .MuiTablePagination-root': {
    minHeight: '40px !important',
    fontFamily: 'Source Sans Pro',
    color: '#79808A', // moon-500
  },
  '& .MuiTablePagination-displayedRows': {
    fontFamily: 'Source Sans Pro',
    color: '#79808A', // moon-500
  },
  '& .MuiTablePagination-selectLabel': {
    fontFamily: 'Source Sans Pro',
    color: '#79808A', // moon-500
  },
  '& .MuiTablePagination-select': {
    fontFamily: 'Source Sans Pro',
    color: '#79808A', // moon-500
  },
  '& .MuiTablePagination-actions': {
    color: '#79808A', // moon-500
  },
  '& .input-digest-cell': {
    padding: '0px !important',
  },
  '& .input-digest-cell:hover': {
    backgroundColor: '#E9F8FB !important',
  },
  '& .call-id-cell': {
    padding: '0px !important',
  },
  '& .call-id-cell:hover': {
    backgroundColor: '#E9F8FB !important',
  },
  width: '100%',
};

/**
 * Hook to handle navigation to a call
 */
const useCallNavigation = () => {
  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();
  const peekLoc = usePeekLocation();

  return useCallback(
    (entityName: string, projectName: string, callId: string) => {
      const peekParams = new URLSearchParams(peekLoc?.search ?? '');
      const traceTreeParam = peekParams.get(HIDE_TRACETREE_PARAM);
      const hideTraceTree =
        traceTreeParam === '1'
          ? true
          : traceTreeParam === '0'
          ? false
          : undefined;
      const showFeedbackParam = peekParams.get(SHOW_FEEDBACK_PARAM);
      const showFeedbackExpand =
        showFeedbackParam === '1'
          ? true
          : showFeedbackParam === '0'
          ? false
          : undefined;

      const url = peekingRouter.callUIUrl(
        entityName,
        projectName,
        '',
        callId,
        undefined,
        hideTraceTree,
        showFeedbackExpand
      );

      history.push(url);
    },
    [history, peekingRouter, peekLoc]
  );
};

/**
 * Custom footer component that includes controls and pagination
 */
interface CustomFooterProps {
  setRowHeightToSingle: () => void;
  setRowHeightToThree: () => void;
  setRowHeightToSix: () => void;
  currentRowHeight: number;
  onlyOneModel: boolean;
  setModelsAsRows: (value: React.SetStateAction<boolean>) => void;
  shouldHighlightSelectedRow?: boolean;
  onShowSplitView: () => void;
  mergeDatasetResultsPerModel?: boolean;
}

const CustomFooter: React.FC<CustomFooterProps> = props => {
  const [columnMenuAnchorEl, setColumnMenuAnchorEl] =
    useState<HTMLElement | null>(null);

  const handleColumnMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setColumnMenuAnchorEl(event.currentTarget);
  };

  const handleColumnMenuClose = () => {
    setColumnMenuAnchorEl(null);
  };

  return (
    <GridFooterContainer>
      <HorizontalBox
        sx={{
          justifyContent: 'flex-start',
          alignItems: 'center',
          padding: '0 16px',
          minHeight: '40px',
          height: '40px',
        }}>
        <Tooltip
          content="Single row"
          trigger={
            <IconButton onClick={props.setRowHeightToSingle}>
              <Icon name="row-height-xlarge" />
            </IconButton>
          }
        />
        <Tooltip
          content="3 rows"
          trigger={
            <IconButton onClick={props.setRowHeightToThree}>
              <Icon name="row-height-medium" />
            </IconButton>
          }
        />
        <Tooltip
          content="6 rows"
          trigger={
            <IconButton onClick={props.setRowHeightToSix}>
              <Icon name="row-height-small" />
            </IconButton>
          }
        />
        <Tooltip
          content="Show/hide columns"
          trigger={
            <IconButton onClick={handleColumnMenuOpen}>
              <Icon name="column" />
            </IconButton>
          }
        />
        {!props.onlyOneModel && !props.mergeDatasetResultsPerModel && (
          <Tooltip
            content="Pivot on eval"
            trigger={
              <IconButton onClick={() => props.setModelsAsRows(v => !v)}>
                <Icon name="retry" />
              </IconButton>
            }
          />
        )}
        {/* {!props.shouldHighlightSelectedRow && (
          <Tooltip
            content="Show Detail Panel"
            trigger={
              <IconButton onClick={props.onShowSplitView}>
                <Icon name="panel" />
              </IconButton>
            }
          />
        )} */}
      </HorizontalBox>
      <GridFooter sx={{border: 'none'}} />
      <Popover
        open={Boolean(columnMenuAnchorEl)}
        anchorEl={columnMenuAnchorEl}
        onClose={handleColumnMenuClose}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        slotProps={{
          paper: {
            sx: {
              maxHeight: '400px',
              overflow: 'auto',
            },
          },
        }}>
        <ColumnsManagementPanel />
      </Popover>
    </GridFooterContainer>
  );
};

/**
 * Types for the comparison table data structure
 */

// Base type for all row data
type BaseRowData = Pick<PivotedRow, 'output' | 'scores' | 'inputDigest'> & {
  id: string;
  _expansionId: string;
};

// Row data when models are displayed as columns
type ModelAsColumnsRowData = BaseRowData & {
  _pivot: 'modelsAsColumns';
};

// Row data when models are displayed as rows
type ModelAsRowsRowData = BaseRowData &
  Pick<PivotedRow, 'evaluationCallId' | 'predictAndScore'> & {
    _pivot: 'modelsAsRows';
  };

type RowDataBase = ModelAsColumnsRowData | ModelAsRowsRowData;

// Row data for individual trials
type TrialRowData = RowDataBase & {
  _type: 'trial';
  _trialNdx: number;
};

// Row data for summary rows
type SummaryRowData = RowDataBase & {
  _type: 'summary';
  _numTrials: number;
};

type RowData = TrialRowData | SummaryRowData;

/**
 * Component Props
 */
interface DatasetRowItemRendererProps {
  digest: string;
  inputKey: string;
  lineClamp?: number;
}

interface ExampleCompareSectionTableProps {
  state: EvaluationComparisonState;
  shouldHighlightSelectedRow?: boolean;
  onShowSplitView: () => void;
  // Set of scorer prefixes (e.g., "scores.tool_usage_scorer") to show.
  // All other scorer columns will be hidden by default.
  defaultHiddenScorerMetrics?: Set<string>;
  // When true, merges results from the same model across different datasets into one column
  mergeDatasetResultsPerModel?: boolean;
  // When true, hides the Inputs and Outputs columns by default
  hideInputOutputColumns?: boolean;
  // When true, disables baseline comparison stats in scorer columns
  disableBaselineStats?: boolean;
}

/**
 * Constants
 */
const DISABLED_ROW_SPANNING = {
  rowSpanValueGetter: (value: any, row: RowData) => row.id,
};

/**
 * Helper function to group evaluation calls by model name
 */
const groupEvaluationsByModel = (
  evaluationCallIds: string[],
  evaluationCalls: any
): Map<string, string[]> => {
  const modelGroups = new Map<string, string[]>();

  evaluationCallIds.forEach(callId => {
    const evalCall = evaluationCalls[callId];
    if (!evalCall || !evalCall.modelRef) return;

    // Parse the model ref to extract the model name
    const modelRef = parseRefMaybe(evalCall.modelRef);
    const modelName = modelRef?.artifactName || 'Unknown Model';

    if (!modelGroups.has(modelName)) {
      modelGroups.set(modelName, []);
    }
    modelGroups.get(modelName)!.push(callId);
  });

  return modelGroups;
};

const SCORE_COLUMN_SETTINGS = {
  flex: 1,
  minWidth: 162,
};

// Constants for column width calculations
const MIN_COLUMN_WIDTH = 100;
const MAX_COLUMN_WIDTH = 400;
const DYNAMIC_COLUMN_MAX_WIDTH = 500;
const BASE_CHAR_WIDTH = 8; // Approximate width of a character in pixels
const PADDING = 32; // Padding for cell content

// Helper to estimate content width
const estimateContentWidth = (content: any): number => {
  if (content == null) return MIN_COLUMN_WIDTH;

  if (typeof content === 'object' && '_type' in content) {
    return MIN_COLUMN_WIDTH;
  }

  // Convert content to string for length estimation
  const contentStr =
    typeof content === 'string' ? content : JSON.stringify(content);

  // Calculate width based on content length
  const estimatedWidth = Math.min(
    Math.max(contentStr.length * BASE_CHAR_WIDTH + PADDING, MIN_COLUMN_WIDTH),
    MAX_COLUMN_WIDTH
  );

  return estimatedWidth;
};

// Hook to calculate column widths based on first row
const useColumnWidths = (
  ctx: CompareEvaluationContext,
  inputSubFields: string[],
  outputColumnKeys: string[],
  rows: RowData[]
) => {
  const firstRow = useFirstExampleRow(ctx);

  return useMemo(() => {
    // Calculate input widths from fetched data
    const inputWidths =
      firstRow.loading || !firstRow.targetRowValue
        ? Object.fromEntries(inputSubFields.map(key => [key, MIN_COLUMN_WIDTH]))
        : Object.fromEntries(
            inputSubFields.map(key => [
              key,
              estimateContentWidth(firstRow.targetRowValue?.[key]),
            ])
          );

    // Calculate output widths from actual row data
    const outputWidths = Object.fromEntries(
      outputColumnKeys.map(key => {
        // Find the first non-summary row with output data
        const firstOutputRow = rows.find(
          row =>
            row._type !== 'summary' &&
            row.output[key] &&
            Object.values(row.output[key]).some(v => v != null)
        );

        // Get the first non-null output value
        const firstOutputValue = firstOutputRow?.output[key]
          ? Object.values(firstOutputRow.output[key]).find(v => v != null)
          : null;

        return [key, estimateContentWidth(firstOutputValue)];
      })
    );

    return {inputWidths, outputWidths};
  }, [firstRow, inputSubFields, outputColumnKeys, rows]);
};

/**
 * Renders a cell value from the dataset
 */
const DatasetRowItemRenderer: React.FC<DatasetRowItemRendererProps> = props => {
  const ctx = useCompareEvaluationsState();
  const row = useExampleCompareData(ctx, props.digest);
  if (row.loading) {
    return <LoadingDots />;
  }
  return (
    <DenseCellValue
      value={row.targetRowValue?.[props.inputKey]}
      lineClamp={props.lineClamp}
    />
  );
};

// Component for showing preview of cell content in a popover
const CellPreviewPopover: React.FC<{
  anchorEl: HTMLElement | null;
  onClose: () => void;
  content: any;
  isJsonContent?: boolean;
}> = ({anchorEl, onClose, content, isJsonContent}) => {
  if (!anchorEl) return null;

  const displayContent = isJsonContent
    ? JSON.stringify(content, null, 2)
    : content;

  return (
    <Popover
      open={Boolean(anchorEl)}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{
        vertical: 'center',
        horizontal: 'center',
      }}
      transformOrigin={{
        vertical: 'center',
        horizontal: 'center',
      }}
      slotProps={{
        paper: {
          sx: {
            maxWidth: '600px',
            maxHeight: '400px',
            overflow: 'auto',
            p: 2,
            boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.15)',
            border: '1px solid rgba(0, 0, 0, 0.1)',
          },
        },
      }}>
      <Box
        sx={{
          fontFamily: isJsonContent ? 'monospace' : 'inherit',
          fontSize: '14px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}>
        {displayContent}
      </Box>
    </Popover>
  );
};

const DenseCellValue: React.FC<
  React.ComponentProps<typeof CellValue> & {lineClamp?: number}
> = props => {
  const {lineClamp = 1, ...cellValueProps} = props;
  const [previewAnchorEl, setPreviewAnchorEl] = useState<HTMLElement | null>(
    null
  );
  const textRef = useRef<HTMLDivElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);

  // Check if text is overflowing
  useEffect(() => {
    if (textRef.current) {
      const isTextOverflowing =
        textRef.current.scrollHeight > textRef.current.clientHeight ||
        textRef.current.scrollWidth > textRef.current.clientWidth;
      setIsOverflowing(isTextOverflowing);
    }
  }, [props.value, lineClamp]);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    if (isOverflowing) {
      event.stopPropagation();
      setPreviewAnchorEl(event.currentTarget);
    }
  };

  const handleClosePreview = () => {
    setPreviewAnchorEl(null);
  };

  if (props.value == null) {
    return <NotApplicable />;
  }

  // For string values, render directly with line-clamp
  if (
    typeof props.value === 'string' &&
    !props.value.startsWith('data:image/')
  ) {
    return (
      <>
        <Box
          sx={{
            height: '100%',
            width: '100%',
            padding: '6px 4px',
            display: 'flex',
            alignItems: 'flex-start',
          }}
          onClick={handleClick}>
          <Box
            ref={textRef}
            sx={{
              width: '100%',
              overflow: 'hidden',
              textAlign: 'left',
              lineHeight: '17px',
              display: '-webkit-box',
              WebkitLineClamp: lineClamp,
              WebkitBoxOrient: 'vertical',
              textOverflow: 'ellipsis',
              wordBreak: 'break-word',
              whiteSpace: 'normal',
              cursor: isOverflowing ? 'pointer' : 'default',
              '&:hover': isOverflowing
                ? {
                    textDecoration: 'underline',
                    textDecorationStyle: 'dotted',
                  }
                : {},
            }}
            title={isOverflowing ? 'Click to preview' : undefined}>
            {props.value.trim()}
          </Box>
        </Box>
        <CellPreviewPopover
          anchorEl={previewAnchorEl}
          onClose={handleClosePreview}
          content={props.value}
        />
      </>
    );
  }

  // For objects/arrays that will be JSON stringified, also apply line-clamp
  if (typeof props.value === 'object') {
    const stringified = JSON.stringify(props.value);
    return (
      <>
        <Box
          sx={{
            height: '100%',
            width: '100%',
            padding: '6px 4px',
            display: 'flex',
            alignItems: 'flex-start',
          }}
          onClick={handleClick}>
          <Box
            ref={textRef}
            sx={{
              width: '100%',
              overflow: 'hidden',
              textAlign: 'left',
              lineHeight: '17px',
              display: '-webkit-box',
              WebkitLineClamp: lineClamp,
              WebkitBoxOrient: 'vertical',
              textOverflow: 'ellipsis',
              wordBreak: 'break-word',
              whiteSpace: 'normal',
              cursor: isOverflowing ? 'pointer' : 'default',
              fontFamily: 'monospace',
              fontSize: '0.875em',
              '&:hover': isOverflowing
                ? {
                    textDecoration: 'underline',
                    textDecorationStyle: 'dotted',
                  }
                : {},
            }}
            title={isOverflowing ? 'Click to preview' : undefined}>
            {stringified}
          </Box>
        </Box>
        <CellPreviewPopover
          anchorEl={previewAnchorEl}
          onClose={handleClosePreview}
          content={props.value}
          isJsonContent={true}
        />
      </>
    );
  }

  // For non-string values, use the default CellValue component
  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'flex-start',
        padding: '4px',
      }}>
      <CellValue {...cellValueProps} />
    </Box>
  );
};
/**
 * Main component for displaying comparison data in a table format
 * Can display models as either rows or columns
 */
export const ExampleCompareSectionTable: React.FC<
  ExampleCompareSectionTableProps
> = props => {
  const {hiddenEvaluationIds, filterToLatestEvaluationsPerModel} =
    useCompareEvaluationsState();
  const [modelsAsRows, setModelsAsRows] = useState(false);
  const [rowHeight, setRowHeight] = useState(32);
  const [lineClamp, setLineClamp] = useState(1);

  const setRowHeightToSingle = useCallback(() => {
    setRowHeight(32); // 1 line
    setLineClamp(1);
  }, []);

  const setRowHeightToThree = useCallback(() => {
    setRowHeight(32 + 17 * 2); // 3 lines
    setLineClamp(3);
  }, []);

  const setRowHeightToSix = useCallback(() => {
    setRowHeight(32 + 17 * 5); // 6 lines
    setLineClamp(6);
  }, []);

  // Filter out hidden evaluations and keep only latest for each model (if in leaderboard mode)
  const visibleEvaluationCallIds = useMemo(() => {
    const nonHiddenIds = props.state.evaluationCallIdsOrdered.filter(
      id => !hiddenEvaluationIds.has(id)
    );

    // Only apply latest evaluation filtering if we're in leaderboard mode
    if (filterToLatestEvaluationsPerModel) {
      // Filter to keep only the latest evaluation for each model-dataset combination
      return filterLatestCallIdsPerModelDataset(
        nonHiddenIds,
        props.state.summary.evaluationCalls,
        props.state.summary.evaluations,
        {},
        true
      );
    }

    return nonHiddenIds;
  }, [
    props.state.evaluationCallIdsOrdered,
    props.state.summary.evaluationCalls,
    props.state.summary.evaluations,
    hiddenEvaluationIds,
    filterToLatestEvaluationsPerModel,
  ]);

  const onlyOneModel = visibleEvaluationCallIds.length === 1;

  // Create a modified state with filtered evaluation call IDs
  const filteredState = useMemo(() => {
    return {
      ...props.state,
      evaluationCallIdsOrdered: visibleEvaluationCallIds,
    };
  }, [props.state, visibleEvaluationCallIds]);

  const inner =
    modelsAsRows || onlyOneModel ? (
      <ExampleCompareSectionTableModelsAsRows
        {...props}
        state={filteredState}
        rowHeight={rowHeight}
        lineClamp={lineClamp}
        setRowHeightToSingle={setRowHeightToSingle}
        setRowHeightToThree={setRowHeightToThree}
        setRowHeightToSix={setRowHeightToSix}
        setModelsAsRows={setModelsAsRows}
        onlyOneModel={onlyOneModel}
        defaultHiddenScorerMetrics={props.defaultHiddenScorerMetrics}
        mergeDatasetResultsPerModel={props.mergeDatasetResultsPerModel}
        disableBaselineStats={props.disableBaselineStats}
      />
    ) : (
      <ExampleCompareSectionTableModelsAsColumns
        {...props}
        state={filteredState}
        rowHeight={rowHeight}
        lineClamp={lineClamp}
        setRowHeightToSingle={setRowHeightToSingle}
        setRowHeightToThree={setRowHeightToThree}
        setRowHeightToSix={setRowHeightToSix}
        setModelsAsRows={setModelsAsRows}
        onlyOneModel={onlyOneModel}
        defaultHiddenScorerMetrics={props.defaultHiddenScorerMetrics}
        mergeDatasetResultsPerModel={props.mergeDatasetResultsPerModel}
        disableBaselineStats={props.disableBaselineStats}
      />
    );
  return inner;
};

/**
 * Hooks for data management
 */

// Gets the first example row from the comparison results
const useFirstExampleRow = (ctx: CompareEvaluationContext) => {
  const {state} = ctx;
  return useExampleCompareData(
    ctx,
    Object.keys(
      state.loadableComparisonResults.result?.resultRows ?? {'': ''}
    )[0]
  );
};

// Gets the input sub-fields from the first example row
const useInputSubFields = (ctx: CompareEvaluationContext) => {
  const firstExampleRow = useFirstExampleRow(ctx);
  const res = useMemo(() => {
    const exampleRow = firstExampleRow.targetRowValue ?? {};

    if (_.isObject(exampleRow)) {
      return Object.keys(exampleRow);
    } else {
      return [''];
    }
  }, [firstExampleRow.targetRowValue]);

  return {loading: firstExampleRow.loading, inputSubFields: res};
};

// Manages selected row state
const useSelectedRowState = (
  state: EvaluationComparisonState,
  rows: RowData[],
  shouldHighlightSelectedRow: boolean
) => {
  const {setSelectedInputDigest} = useCompareEvaluationsState();
  const selectedRowInputDigest = useMemo(() => {
    if (!shouldHighlightSelectedRow) {
      return [];
    }
    if (_.isEmpty(rows)) {
      return [];
    }
    const assumedSelectedInputDigest =
      state.selectedInputDigest ?? rows[0].inputDigest;
    return rows
      .filter(row => row.inputDigest === assumedSelectedInputDigest)
      .map(row => row.id);
  }, [shouldHighlightSelectedRow, state.selectedInputDigest, rows]);

  return {
    setSelectedInputDigest,
    selectedRowInputDigest,
  };
};

/**
 * Table data management hooks
 */

// Prepares table data when models are displayed as rows
const useTableDataForModelsAsRows = (
  state: EvaluationComparisonState,
  filteredRows: FilteredAggregateRows
): {rows: RowData[]; hasTrials: boolean} => {
  const {rows, hasTrials} = useMemo(() => {
    let hasTrials = false;
    const returnRows: RowData[] = filteredRows.flatMap(filteredRow => {
      const evaluationCallIds = state.evaluationCallIdsOrdered;
      const finalRows: RowData[] = [];
      for (const evaluationCallId of evaluationCallIds) {
        const matchingRows = filteredRow.originalRows.filter(
          row => row.evaluationCallId === evaluationCallId
        );
        const numTrials = matchingRows.length;
        const expansionId = filteredRow.inputDigest + ':' + evaluationCallId;
        const originalRows: TrialRowData[] = matchingRows.map(
          (row, trialNdx) => {
            return {
              _type: 'trial' as const,
              _expansionId: expansionId,
              _trialNdx: trialNdx,
              _pivot: 'modelsAsRows' as const,
              ...row,
            };
          }
        );
        const digestEvalId = filteredRow.inputDigest + ':' + evaluationCallId;
        hasTrials = hasTrials || numTrials > 1;

        const summaryRow: SummaryRowData = {
          ...matchingRows[0],
          _type: 'summary' as const,
          _numTrials: numTrials,
          _expansionId: expansionId,
          _pivot: 'modelsAsRows' as const,
          id: digestEvalId,
          output: filteredRow.output,
          scores: filteredRow.scores,
        };
        finalRows.push(summaryRow);

        finalRows.push(...originalRows);
      }
      return finalRows;
    });
    return {rows: returnRows, hasTrials};
  }, [filteredRows, state.evaluationCallIdsOrdered]);

  return {rows, hasTrials};
};

// Prepares table data when models are displayed as columns
const useTableDataForModelsAsColumns = (
  filteredRows: FilteredAggregateRows
): {rows: RowData[]; hasTrials: boolean} => {
  return useMemo(() => {
    let hasTrials = false;
    const returnRows: RowData[] = filteredRows.flatMap(
      (filteredRow): RowData[] => {
        const groupedOriginalRows = _.groupBy(
          filteredRow.originalRows,
          row => row.evaluationCallId
        );
        const maxTrials = Math.max(
          ...Object.values(groupedOriginalRows).map(rows => rows.length)
        );

        const summaryRow: SummaryRowData = {
          ...filteredRow,
          _type: 'summary' as const,
          _numTrials: maxTrials,
          _expansionId: filteredRow.inputDigest,
          _pivot: 'modelsAsColumns' as const,
          id: filteredRow.inputDigest + ':summary',
          output: filteredRow.output,
          scores: filteredRow.scores,
        };

        hasTrials = hasTrials || maxTrials > 1;

        return [
          summaryRow,
          ..._.range(maxTrials).map(trialNdx => {
            const res: TrialRowData = {
              ...filteredRow,
              _type: 'trial' as const,
              _trialNdx: trialNdx,
              _expansionId: filteredRow.inputDigest,
              _pivot: 'modelsAsColumns' as const,
              id: filteredRow.inputDigest + ':trial:' + trialNdx,
              output: Object.fromEntries(
                Object.entries(filteredRow.output).map(([key, value]) => {
                  return [
                    key,
                    Object.fromEntries(
                      Object.values(groupedOriginalRows).map(evalVal => {
                        return [
                          evalVal[trialNdx]?.evaluationCallId,
                          evalVal[trialNdx]?.output?.[key]?.[
                            evalVal[trialNdx]?.evaluationCallId
                          ],
                        ];
                      })
                    ),
                  ];
                })
              ),
              scores: Object.fromEntries(
                Object.entries(filteredRow.scores).map(([key, value]) => {
                  return [
                    key,
                    Object.fromEntries(
                      Object.values(groupedOriginalRows).map(evalVal => {
                        return [
                          evalVal[trialNdx]?.evaluationCallId,
                          evalVal[trialNdx]?.scores?.[key]?.[
                            evalVal[trialNdx]?.evaluationCallId
                          ],
                        ];
                      })
                    ),
                  ];
                })
              ),
            };
            return res;
          }),
        ];
      }
    );

    return {rows: returnRows, hasTrials};
  }, [filteredRows]);
};

const useExpandedIds = () => {
  const [toggledIds, setToggledIds] = useState<string[]>([]);
  const [defaultExpandState, setDefaultExpandState] = useState<
    'expanded' | 'collapsed'
  >('collapsed');
  const toggleDefaultExpansionState = useCallback(() => {
    setToggledIds([]);
    setDefaultExpandState(v => (v === 'expanded' ? 'collapsed' : 'expanded'));
  }, []);
  const toggleExpansion = useCallback((id: string) => {
    setToggledIds(prev =>
      prev.includes(id) ? prev.filter(v => v !== id) : [...prev, id]
    );
  }, []);
  const isExpanded = useCallback(
    (id: string) => {
      if (defaultExpandState === 'expanded') {
        return !toggledIds.includes(id);
      } else {
        return toggledIds.includes(id);
      }
    },
    [toggledIds, defaultExpandState]
  );
  return {
    isExpanded,
    toggleDefaultExpansionState,
    defaultExpandState,
    toggleExpansion,
  };
};
/**
 * Table Components
 */

const datasetField = (
  state?: EvaluationComparisonState,
  filteredRows?: FilteredAggregateRows
): GridColDef<RowData> | null => {
  if (!state) return null;

  return {
    field: 'dataset',
    headerName: 'Dataset',
    width: 150,
    maxWidth: 300,
    resizable: true,
    disableColumnMenu: false,
    disableReorder: true,
    filterable: false,
    sortable: true,
    ...DISABLED_ROW_SPANNING,
    valueGetter: (value: any, row: RowData) => {
      if (!filteredRows || !state) {
        return '';
      }

      // For modelsAsRows, we can get the dataset from the specific evaluation
      if (row._pivot === 'modelsAsRows' && 'evaluationCallId' in row) {
        const evaluationCall =
          state.summary.evaluationCalls[row.evaluationCallId];
        if (evaluationCall) {
          const evaluationObj =
            state.summary.evaluations[evaluationCall.evaluationRef];
          if (evaluationObj && evaluationObj.datasetRef) {
            const parsed = parseRefMaybe(evaluationObj.datasetRef);
            return parsed?.artifactName || '';
          }
        }
      }

      // For modelsAsColumns, find the first available dataset from the original rows
      const matchingFilteredRow = filteredRows.find(
        fr => fr.inputDigest === row.inputDigest
      );

      if (
        matchingFilteredRow &&
        matchingFilteredRow.originalRows &&
        matchingFilteredRow.originalRows.length > 0
      ) {
        const firstOriginalRow = matchingFilteredRow.originalRows[0];
        const evaluationCall =
          state.summary.evaluationCalls[firstOriginalRow.evaluationCallId];
        if (evaluationCall) {
          const evaluationObj =
            state.summary.evaluations[evaluationCall.evaluationRef];
          if (evaluationObj && evaluationObj.datasetRef) {
            const parsed = parseRefMaybe(evaluationObj.datasetRef);
            return parsed?.artifactName || '';
          }
        }
      }

      return '';
    },
    renderCell: (params: GridRenderCellParams<RowData>) => {
      if (!filteredRows || !state) {
        return <NotApplicable />;
      }

      let datasetRef = null;

      // For modelsAsRows, we can get the dataset from the specific evaluation
      if (
        params.row._pivot === 'modelsAsRows' &&
        'evaluationCallId' in params.row
      ) {
        const evaluationCall =
          state.summary.evaluationCalls[params.row.evaluationCallId];
        if (evaluationCall) {
          const evaluationObj =
            state.summary.evaluations[evaluationCall.evaluationRef];
          if (evaluationObj && evaluationObj.datasetRef) {
            const parsed = parseRefMaybe(evaluationObj.datasetRef);
            if (parsed) {
              datasetRef = parsed;
            }
          }
        }
      } else {
        // For modelsAsColumns, find the first available dataset from the original rows
        const matchingFilteredRow = filteredRows.find(
          fr => fr.inputDigest === params.row.inputDigest
        );

        if (
          matchingFilteredRow &&
          matchingFilteredRow.originalRows &&
          matchingFilteredRow.originalRows.length > 0
        ) {
          const firstOriginalRow = matchingFilteredRow.originalRows[0];
          const evaluationCall =
            state.summary.evaluationCalls[firstOriginalRow.evaluationCallId];
          if (evaluationCall) {
            const evaluationObj =
              state.summary.evaluations[evaluationCall.evaluationRef];
            if (evaluationObj && evaluationObj.datasetRef) {
              const parsed = parseRefMaybe(evaluationObj.datasetRef);
              if (parsed) {
                datasetRef = parsed;
              }
            }
          }
        }
      }

      if (!datasetRef) {
        return <NotApplicable />;
      }

      return (
        <Box
          style={{
            height: '100%',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
          }}>
          <SmallRef objRef={datasetRef} />
        </Box>
      );
    },
  } as GridColDef<RowData>;
};

const inputFields = (
  inputSubFields: string[],
  setSelectedInputDigest: (inputDigest: string) => void,
  onShowSplitView: () => void,
  columnWidths: {[key: string]: number},
  lineClamp: number
): GridColDef<RowData>[] => [
  {
    field: 'inputDigest',
    headerName: 'Row',
    width: 60,
    maxWidth: 60,
    headerAlign: 'center',
    resizable: false,
    disableColumnMenu: true,
    disableReorder: true,
    filterable: false,
    sortable: false,
    hideable: false,
    cellClassName: 'input-digest-cell',
    renderCell: params => {
      return (
        <Box
          style={{
            height: '100%',
            width: '100%',
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            cursor: 'pointer',
          }}
          onClick={() => {
            setSelectedInputDigest(params.row.inputDigest);
            onShowSplitView();
          }}>
          <span
            style={{flexShrink: 1, marginLeft: 'auto', marginRight: 'auto'}}>
            <IdPanel clickable>{params.row.inputDigest.slice(-4)}</IdPanel>
          </span>
        </Box>
      );
    },
  },
  ...inputSubFields.map(
    key =>
      ({
        field: `inputs.${key}`,
        headerName: key,
        sortable: false,
        filterable: false,
        width: columnWidths[key],
        maxWidth: DYNAMIC_COLUMN_MAX_WIDTH,
        valueGetter: (value: any, row: RowData) => {
          return row.inputDigest;
        },
        renderCell: (params: GridRenderCellParams<RowData>) => {
          return (
            <DatasetRowItemRenderer
              digest={params.row.inputDigest}
              inputKey={key}
              lineClamp={lineClamp}
            />
          );
        },
      } as GridColDef<RowData>)
  ),
];

const expansionField = (
  toggleDefaultExpansionState: () => void,
  defaultExpandState: 'expanded' | 'collapsed',
  isExpanded: (id: string) => boolean,
  toggleExpansion: (id: string) => void
): GridColDef<RowData> => ({
  field: 'expandTrials',
  headerName: '',
  width: 50,
  maxWidth: 50,
  resizable: false,
  disableColumnMenu: true,
  disableReorder: true,
  sortable: false,
  filterable: false,
  hideable: false,
  headerAlign: 'center',
  renderHeader: (params: GridColumnHeaderParams<RowData>) => {
    return (
      <Tooltip
        content={
          defaultExpandState === 'expanded' ? 'Hide trials' : 'Show trials'
        }
        trigger={
          <IconButton onClick={toggleDefaultExpansionState}>
            <Icon
              name={
                defaultExpandState === 'expanded'
                  ? 'collapse'
                  : 'expand-uncollapse'
              }
            />
          </IconButton>
        }
      />
    );
  },
  valueGetter: (value: any, row: RowData) => {
    return row._expansionId;
  },
  renderCell: (params: GridRenderCellParams<RowData>) => {
    const itemIsExpanded = isExpanded(params.row._expansionId);
    return (
      <Box
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          width: '100%',
        }}>
        <Tooltip
          content={itemIsExpanded ? 'Hide trials' : 'Show trials'}
          trigger={
            <IconButton
              onClick={() => {
                toggleExpansion(params.row._expansionId);
              }}>
              <Icon name={itemIsExpanded ? 'collapse' : 'expand-uncollapse'} />
            </IconButton>
          }
        />
      </Box>
    );
  },
});

// Component for displaying models as rows
export const ExampleCompareSectionTableModelsAsRows: React.FC<
  ExampleCompareSectionTableProps & {
    rowHeight: number;
    lineClamp: number;
    setRowHeightToSingle: () => void;
    setRowHeightToThree: () => void;
    setRowHeightToSix: () => void;
    setModelsAsRows: (value: React.SetStateAction<boolean>) => void;
    onlyOneModel: boolean;
    defaultHiddenScorerMetrics?: Set<string>;
    mergeDatasetResultsPerModel?: boolean;
  }
> = props => {
  const ctx = useCompareEvaluationsState();
  const onlyOneModel = ctx.state.evaluationCallIdsOrdered.length === 1;
  const {filteredRows, outputColumnKeys} = useFilteredAggregateRows(ctx.state);
  const {
    isExpanded,
    toggleDefaultExpansionState,
    defaultExpandState,
    toggleExpansion,
  } = useExpandedIds();
  const {rows, hasTrials} = useTableDataForModelsAsRows(
    props.state,
    filteredRows
  );

  const inputSubFields = useInputSubFields(ctx);
  const compositeMetrics = useMemo(() => {
    return buildCompositeMetricsMap(props.state.summary, 'score');
  }, [props.state.summary]);
  const {selectedRowInputDigest, setSelectedInputDigest} = useSelectedRowState(
    props.state,
    rows,
    props.shouldHighlightSelectedRow ?? false
  );

  const {inputWidths, outputWidths} = useColumnWidths(
    ctx,
    inputSubFields.inputSubFields,
    outputColumnKeys,
    rows
  );

  const navigateToCall = useCallNavigation();

  const columns: GridColDef<RowData>[] = useMemo(() => {
    const datasetCol = datasetField(props.state, filteredRows);
    const res: GridColDef<RowData>[] = [
      ...inputFields(
        inputSubFields.inputSubFields,
        setSelectedInputDigest,
        props.onShowSplitView,
        inputWidths,
        props.lineClamp
      ),
      ...(datasetCol ? [datasetCol] : []),
      ...(onlyOneModel
        ? []
        : [
            {
              field: 'evaluationCallId',
              headerName: 'Eval/Model',
              disableColumnMenu: true,
              sortable: false,
              filterable: false,
              hideable: false,
              renderCell: (params: GridRenderCellParams<RowData>) => {
                if (params.row._pivot === 'modelsAsColumns') {
                  // This does not make sense for models as columns
                  return null;
                }

                return (
                  <EvaluationModelLink
                    callId={params.row.evaluationCallId}
                    state={props.state}
                  />
                );
              },
            } as GridColDef<RowData>,
          ]),
      ...(hasTrials
        ? [
            expansionField(
              toggleDefaultExpansionState,
              defaultExpandState,
              isExpanded,
              toggleExpansion
            ),
          ]
        : []),
      {
        field: 'trialNdx',
        headerName: 'Trials',
        width: 60,
        maxWidth: 60,
        resizable: false,
        disableColumnMenu: true,
        disableReorder: true,
        sortable: false,
        filterable: false,
        hideable: false,

        ...DISABLED_ROW_SPANNING,
        renderCell: params => {
          if (params.row._type === 'summary') {
            return (
              <div
                style={{
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                {params.row._numTrials}
              </div>
            );
          }
          if (params.row._pivot === 'modelsAsColumns') {
            // This does not make sense for models as columns as you would need
            // one column per model and it is not really worth the space
            return null;
          }
          const trialPredict = params.row.predictAndScore._rawPredictTraceData;
          const [trialEntity, trialProject] =
            trialPredict?.project_id.split('/') ?? [];
          const trialOpName = parseRefMaybe(
            trialPredict?.op_name ?? ''
          )?.artifactName;
          const trialCallId = params.row.predictAndScore.callId;
          if (trialEntity && trialProject && trialOpName && trialCallId) {
            return (
              <Box
                style={{
                  overflow: 'hidden',
                  height: '100%',
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                }}
                onClick={() =>
                  navigateToCall(trialEntity, trialProject, trialCallId)
                }>
                <CallLink
                  entityName={trialEntity}
                  projectName={trialProject}
                  opName={trialOpName}
                  callId={trialCallId}
                  noName
                />
              </Box>
            );
          }
          return null;
        },
      },
      {
        field: 'predictCall',
        headerName: 'Call',
        width: 100,
        maxWidth: 150,
        resizable: true,
        disableColumnMenu: true,
        sortable: false,
        filterable: false,
        hideable: false,
        headerAlign: 'center',
        cellClassName: 'call-id-cell',
        ...DISABLED_ROW_SPANNING,
        renderCell: (params: GridRenderCellParams<RowData>) => {
          if (params.row._pivot === 'modelsAsColumns') {
            return null;
          }

          // For trial rows, we have direct access to predictAndScore
          if (
            params.row._type === 'trial' &&
            params.row._pivot === 'modelsAsRows'
          ) {
            const trialPredict =
              params.row.predictAndScore._rawPredictTraceData;
            const [trialEntity, trialProject] =
              trialPredict?.project_id.split('/') ?? [];
            const trialOpName = parseRefMaybe(
              trialPredict?.op_name ?? ''
            )?.artifactName;
            const trialCallId = params.row.predictAndScore.callId;

            if (trialEntity && trialProject && trialOpName && trialCallId) {
              return (
                <Box
                  style={{
                    overflow: 'hidden',
                    height: '100%',
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                  }}
                  onClick={() =>
                    navigateToCall(trialEntity, trialProject, trialCallId)
                  }>
                  <CallLink
                    entityName={trialEntity}
                    projectName={trialProject}
                    opName={trialOpName}
                    callId={trialCallId}
                    noName
                  />
                </Box>
              );
            }
          }

          // For summary rows, we need to get the first trial from filteredRows
          if (params.row._type === 'summary') {
            // Find the corresponding filtered row
            const correspondingFilteredRow = filteredRows.find(
              fr => fr.inputDigest === params.row.inputDigest
            );
            if (correspondingFilteredRow) {
              // For modelsAsRows, we can use evaluationCallId directly
              const evalCallId =
                (params.row as RowData)._pivot === 'modelsAsRows'
                  ? (params.row as ModelAsRowsRowData).evaluationCallId
                  : (params.row as RowData)._pivot === 'modelsAsColumns'
                  ? props.state.evaluationCallIdsOrdered[0] // Use first evaluation for modelsAsColumns
                  : null;

              if (!evalCallId) return null;

              const firstTrial = correspondingFilteredRow.originalRows.find(
                row => row.evaluationCallId === evalCallId
              );
              if (firstTrial) {
                const trialPredict =
                  firstTrial.predictAndScore._rawPredictTraceData;
                const [trialEntity, trialProject] =
                  trialPredict?.project_id.split('/') ?? [];
                const trialOpName = parseRefMaybe(
                  trialPredict?.op_name ?? ''
                )?.artifactName;
                const trialCallId = firstTrial.predictAndScore.callId;

                if (trialEntity && trialProject && trialOpName && trialCallId) {
                  return (
                    <Box
                      style={{
                        overflow: 'hidden',
                        height: '100%',
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                      }}
                      onClick={() =>
                        navigateToCall(trialEntity, trialProject, trialCallId)
                      }>
                      <CallLink
                        entityName={trialEntity}
                        projectName={trialProject}
                        opName={trialOpName}
                        callId={trialCallId}
                        noName
                      />
                    </Box>
                  );
                }
              }
            }
          }

          return null;
        },
      },
      ...outputColumnKeys.map(
        key =>
          ({
            field: `output.${key}`,
            headerName: key,
            renderHeader: () => removePrefix(key, 'output.'),
            width: outputWidths[key],
            maxWidth: DYNAMIC_COLUMN_MAX_WIDTH,
            ...DISABLED_ROW_SPANNING,
            disableReorder: true,
            valueGetter: (value: any, row: RowData) => {
              if (row._pivot === 'modelsAsColumns') {
                return null;
              }
              return row.output[key]?.[row.evaluationCallId];
            },
            renderCell: (params: GridRenderCellParams<RowData>) => {
              if (params.row._pivot === 'modelsAsColumns') {
                return null;
              }
              if (params.row._type === 'summary') {
                // TODO: Should we indicate that this is just the first trial?
                return (
                  <DenseCellValue
                    value={
                      params.row.output[key]?.[params.row.evaluationCallId]
                    }
                    lineClamp={props.lineClamp}
                  />
                );
              }
              return (
                <DenseCellValue
                  value={params.row.output[key]?.[params.row.evaluationCallId]}
                  lineClamp={props.lineClamp}
                />
              );
            },
          } as GridColDef<RowData>)
      ),
      ...Object.entries(compositeMetrics).flatMap(
        ([metricGroupKey, metricGroupDef]) => {
          return Object.entries(metricGroupDef.metrics).map(
            ([keyPath, metricDef]) => {
              const metricSubpath = Object.values(metricDef.scorerRefs)[0]
                .metric.metricSubPath;
              return {
                field: `scores.${keyPath}`,
                headerName:
                  metricSubpath.length > 0 ? metricSubpath.join('.') : keyPath,
                ...SCORE_COLUMN_SETTINGS,
                ...DISABLED_ROW_SPANNING,
                disableColumnMenu: false,
                disableReorder: true,
                valueGetter: (value: any, row: RowData) => {
                  if (row._pivot === 'modelsAsColumns') {
                    // This does not make sense for models as columns
                    return null;
                  }
                  const dimension = Object.values(metricDef.scorerRefs)[0]
                    .metric;
                  return lookupMetricValueDirect(
                    row.scores,
                    row.evaluationCallId,
                    dimension,
                    compositeMetrics
                  );
                },
                renderCell: (params: GridRenderCellParams<RowData>) => {
                  if (params.row._pivot === 'modelsAsColumns') {
                    // This does not make sense for models as columns
                    return null;
                  }
                  const dimension = Object.values(metricDef.scorerRefs)[0]
                    .metric;
                  const summaryValue = lookupMetricValueDirect(
                    params.row.scores,
                    params.row.evaluationCallId,
                    dimension,
                    compositeMetrics
                  );
                  const baselineValue = props.disableBaselineStats
                    ? undefined
                    : lookupMetricValueDirect(
                        params.row.scores,
                        props.state.evaluationCallIdsOrdered[0],
                        dimension,
                        compositeMetrics
                      );

                  return evalAggScorerMetricCompGeneric(
                    dimension,
                    summaryValue,
                    baselineValue
                  );
                },
              } as GridColDef<RowData>;
            }
          );
        }
      ),
    ];
    return res;
  }, [
    inputSubFields.inputSubFields,
    setSelectedInputDigest,
    props.onShowSplitView,
    props.state,
    inputWidths,
    onlyOneModel,
    hasTrials,
    toggleDefaultExpansionState,
    defaultExpandState,
    isExpanded,
    toggleExpansion,
    outputColumnKeys,
    compositeMetrics,
    outputWidths,
    filteredRows,
    props.lineClamp,
    navigateToCall,
    props.disableBaselineStats,
  ]);

  const columnGroupingModel: GridColumnGroupingModel = useMemo(() => {
    return [
      {
        groupId: 'inputs',
        headerName: 'Inputs',
        children: [
          ...inputSubFields.inputSubFields.map(key => ({
            field: `inputs.${key}`,
          })),
        ],
      },
      {
        groupId: 'predictCall',
        headerName: 'Calls',
        [CUSTOM_GROUP_KEY_TO_CONTROL_CHILDREN_VISIBILITY]: true,
        children: [{field: 'predictCall'}],
      },
      {
        groupId: 'scores',
        headerName: 'Scores',
        children: Object.entries(compositeMetrics).flatMap(
          ([metricGroupKey, metricGroupDef]) => {
            const firstChildKeyPath = Object.entries(
              metricGroupDef.metrics
            )[0][0];
            const childrenLength = Object.entries(
              metricGroupDef.metrics
            ).length;
            const children: GridColumnNode[] = Object.entries(
              metricGroupDef.metrics
            ).map(([keyPath, metricDef]) => ({
              field: `scores.${keyPath}`,
            }));
            if (
              metricGroupKey === DERIVED_SCORER_REF_PLACEHOLDER ||
              (childrenLength === 1 && firstChildKeyPath === metricGroupKey)
            ) {
              return children;
            }
            return [
              {
                groupId: `scores.${metricGroupKey}`,
                headerName: metricGroupKey,
                children,
              },
            ];
          }
        ),
      },
      {
        groupId: 'output',
        headerName: 'Output',
        children: outputColumnKeys.map(key => ({
          field: `output.${key}`,
        })),
      },
    ];
  }, [inputSubFields.inputSubFields, compositeMetrics, outputColumnKeys]);

  const onlyExpandedRows = useOnlyExpandedRows(rows, isExpanded);

  const {columnsWithControlledWidths, onColumnWidthChange} =
    useColumnsWithControlledWidths(columns);

  // Create initial column visibility model that conditionally hides scorer metrics and input/output columns
  const initialColumnVisibilityModel = useMemo(() => {
    const hiddenColumns: Record<string, boolean> = {};

    // If defaultHiddenScorerMetrics is provided (leaderboard context),
    // hide scorer columns that don't belong to any scorer in the leaderboard
    if (props.defaultHiddenScorerMetrics) {
      columns.forEach(col => {
        if (col.field.startsWith('scores.')) {
          // Check if this column belongs to any scorer that's in the leaderboard
          // We check if the column field starts with any of the visible scorer prefixes
          const shouldShow = Array.from(props.defaultHiddenScorerMetrics!).some(
            scorerPrefix => col.field.startsWith(scorerPrefix)
          );
          const shouldHide = !shouldShow;
          if (shouldHide) {
            hiddenColumns[col.field] = false; // false means hidden in MUI DataGrid
          }
        }
      });
    }
    // If no defaultHiddenScorerMetrics provided (regular compare context),
    // show all scorer metrics by default (don't add them to hiddenColumns)

    // Hide input and output columns if requested (for leaderboard context)
    if (props.hideInputOutputColumns) {
      columns.forEach(col => {
        if (
          col.field.startsWith('inputs.') ||
          col.field.startsWith('output.')
        ) {
          hiddenColumns[col.field] = false; // false means hidden in MUI DataGrid
        }
      });
    }

    return hiddenColumns;
  }, [columns, props.defaultHiddenScorerMetrics, props.hideInputOutputColumns]);

  if (inputSubFields.loading || props.state.loadableComparisonResults.loading) {
    return <LoadingDots />;
  }
  return (
    <StyledDataGrid
      onColumnWidthChange={onColumnWidthChange}
      pinnedColumns={{
        left: ['inputDigest'],
      }}
      columnHeaderHeight={36}
      rowHeight={props.rowHeight}
      rowSelectionModel={selectedRowInputDigest}
      unstable_rowSpanning={true}
      columns={columnsWithControlledWidths}
      rows={onlyExpandedRows}
      columnGroupingModel={columnGroupingModel}
      disableRowSelectionOnClick
      pagination
      pageSizeOptions={[50]}
      initialState={{
        columns: {
          columnVisibilityModel: initialColumnVisibilityModel,
        },
        sorting: {
          sortModel: [{field: 'dataset', sort: 'asc'}],
        },
      }}
      sx={{
        ...styledDataGridStyleOverrides,
        backgroundColor: 'white',
      }}
      slots={{
        columnsPanel: ColumnsManagementPanel,
        footer: () => (
          <CustomFooter
            setRowHeightToSingle={props.setRowHeightToSingle}
            setRowHeightToThree={props.setRowHeightToThree}
            setRowHeightToSix={props.setRowHeightToSix}
            currentRowHeight={props.rowHeight}
            onlyOneModel={props.onlyOneModel}
            setModelsAsRows={props.setModelsAsRows}
            shouldHighlightSelectedRow={props.shouldHighlightSelectedRow}
            onShowSplitView={props.onShowSplitView}
            mergeDatasetResultsPerModel={props.mergeDatasetResultsPerModel}
          />
        ),
      }}
    />
  );
};

const useOnlyExpandedRows = (
  rows: RowData[],
  isExpanded: (id: string) => boolean
) => {
  return useMemo(() => {
    return rows.filter(row =>
      isExpanded(row._expansionId)
        ? row._type === 'trial'
        : row._type === 'summary'
    );
  }, [rows, isExpanded]);
};

// Component for displaying models as columns
export const ExampleCompareSectionTableModelsAsColumns: React.FC<
  ExampleCompareSectionTableProps & {
    rowHeight: number;
    lineClamp: number;
    setRowHeightToSingle: () => void;
    setRowHeightToThree: () => void;
    setRowHeightToSix: () => void;
    setModelsAsRows: (value: React.SetStateAction<boolean>) => void;
    onlyOneModel: boolean;
    defaultHiddenScorerMetrics?: Set<string>;
    mergeDatasetResultsPerModel?: boolean;
  }
> = props => {
  const ctx = useCompareEvaluationsState();
  const {filteredRows, outputColumnKeys} = useFilteredAggregateRows(ctx.state);
  const {
    isExpanded,
    toggleDefaultExpansionState,
    defaultExpandState,
    toggleExpansion,
  } = useExpandedIds();

  const {rows, hasTrials} = useTableDataForModelsAsColumns(filteredRows);
  const inputSubFields = useInputSubFields(ctx);
  const compositeMetrics = useMemo(() => {
    return buildCompositeMetricsMap(props.state.summary, 'score');
  }, [props.state.summary]);

  const {selectedRowInputDigest, setSelectedInputDigest} = useSelectedRowState(
    props.state,
    rows,
    props.shouldHighlightSelectedRow ?? false
  );

  const {inputWidths, outputWidths} = useColumnWidths(
    ctx,
    inputSubFields.inputSubFields,
    outputColumnKeys,
    rows
  );

  const navigateToCall = useCallNavigation();

  const columns: GridColDef<RowData>[] = useMemo(() => {
    // Group evaluations by model if mergeDatasetResultsPerModel is true
    const modelGroups = props.mergeDatasetResultsPerModel
      ? groupEvaluationsByModel(
          props.state.evaluationCallIdsOrdered,
          props.state.summary.evaluationCalls
        )
      : null;

    const datasetCol = datasetField(props.state, filteredRows);
    const res: GridColDef<RowData>[] = [
      ...inputFields(
        inputSubFields.inputSubFields,
        setSelectedInputDigest,
        props.onShowSplitView,
        inputWidths,
        props.lineClamp
      ),
      ...(datasetCol ? [datasetCol] : []),
      ...(hasTrials
        ? [
            expansionField(
              toggleDefaultExpansionState,
              defaultExpandState,
              isExpanded,
              toggleExpansion
            ),
          ]
        : []),
      // Add predict call columns for each evaluation or model group
      ...(modelGroups
        ? Array.from(modelGroups.entries()).map(
            ([modelName, evalCallIds]) =>
              ({
                field: `predictCall.${modelName}`,
                headerName: modelName,
                width: 100,
                maxWidth: 150,
                resizable: true,
                disableColumnMenu: false,
                disableReorder: true,
                sortable: false,
                filterable: false,
                headerAlign: 'center',
                cellClassName: 'call-id-cell',
                ...DISABLED_ROW_SPANNING,
                renderHeader: () => {
                  // Use first eval call ID to show model link
                  return (
                    <EvaluationModelLink
                      callId={evalCallIds[0]}
                      state={props.state}
                    />
                  );
                },
                renderCell: (params: GridRenderCellParams<RowData>) => {
                  // Find the corresponding filtered row
                  const correspondingFilteredRow = filteredRows.find(
                    fr => fr.inputDigest === params.row.inputDigest
                  );
                  if (correspondingFilteredRow) {
                    // Find first available trial from any of the evalCallIds in this model group
                    for (const evalCallId of evalCallIds) {
                      const trial =
                        params.row._type === 'trial'
                          ? correspondingFilteredRow.originalRows.filter(
                              row => row.evaluationCallId === evalCallId
                            )[params.row._trialNdx]
                          : correspondingFilteredRow.originalRows.find(
                              row => row.evaluationCallId === evalCallId
                            );

                      if (trial) {
                        const trialPredict =
                          trial.predictAndScore._rawPredictTraceData;
                        const [trialEntity, trialProject] =
                          trialPredict?.project_id.split('/') ?? [];
                        const trialOpName = parseRefMaybe(
                          trialPredict?.op_name ?? ''
                        )?.artifactName;
                        const trialCallId = trial.predictAndScore.callId;

                        if (
                          trialEntity &&
                          trialProject &&
                          trialOpName &&
                          trialCallId
                        ) {
                          return (
                            <Box
                              style={{
                                overflow: 'hidden',
                                height: '100%',
                                width: '100%',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                cursor: 'pointer',
                              }}
                              onClick={() =>
                                navigateToCall(
                                  trialEntity,
                                  trialProject,
                                  trialCallId
                                )
                              }>
                              <CallLink
                                entityName={trialEntity}
                                projectName={trialProject}
                                opName={trialOpName}
                                callId={trialCallId}
                                noName
                              />
                            </Box>
                          );
                        }
                      }
                    }
                  }
                  return null;
                },
              } as GridColDef<RowData>)
          )
        : props.state.evaluationCallIdsOrdered.map(
            evaluationCallId =>
              ({
                field: `predictCall.${evaluationCallId}`,
                headerName: 'Call',
                width: 100,
                maxWidth: 150,
                resizable: true,
                disableColumnMenu: false,
                disableReorder: true,
                sortable: false,
                filterable: false,
                headerAlign: 'center',
                cellClassName: 'call-id-cell',
                ...DISABLED_ROW_SPANNING,
                renderHeader: (params: GridColumnHeaderParams<RowData>) => {
                  return (
                    <EvaluationModelLink
                      callId={evaluationCallId}
                      state={props.state}
                    />
                  );
                },
                renderCell: (params: GridRenderCellParams<RowData>) => {
                  // Find the corresponding filtered row
                  const correspondingFilteredRow = filteredRows.find(
                    fr => fr.inputDigest === params.row.inputDigest
                  );
                  if (correspondingFilteredRow) {
                    const trial =
                      params.row._type === 'trial'
                        ? correspondingFilteredRow.originalRows.filter(
                            row => row.evaluationCallId === evaluationCallId
                          )[params.row._trialNdx]
                        : correspondingFilteredRow.originalRows.find(
                            row => row.evaluationCallId === evaluationCallId
                          );

                    if (trial) {
                      const trialPredict =
                        trial.predictAndScore._rawPredictTraceData;
                      const [trialEntity, trialProject] =
                        trialPredict?.project_id.split('/') ?? [];
                      const trialOpName = parseRefMaybe(
                        trialPredict?.op_name ?? ''
                      )?.artifactName;
                      const trialCallId = trial.predictAndScore.callId;

                      if (
                        trialEntity &&
                        trialProject &&
                        trialOpName &&
                        trialCallId
                      ) {
                        return (
                          <Box
                            style={{
                              overflow: 'hidden',
                              height: '100%',
                              width: '100%',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              cursor: 'pointer',
                            }}
                            onClick={() =>
                              navigateToCall(
                                trialEntity,
                                trialProject,
                                trialCallId
                              )
                            }>
                            <CallLink
                              entityName={trialEntity}
                              projectName={trialProject}
                              opName={trialOpName}
                              callId={trialCallId}
                              noName
                            />
                          </Box>
                        );
                      }
                    }
                  }
                  return null;
                },
              } as GridColDef<RowData>)
          )),
      ...outputColumnKeys.flatMap(key => {
        if (modelGroups) {
          // When merging by model, create one column per model per output key
          return Array.from(modelGroups.entries()).map(
            ([modelName, evalCallIds]) => {
              return {
                field: `output.${key}.${modelName}`,
                headerName: `${key}`,
                width: outputWidths[key],
                maxWidth: DYNAMIC_COLUMN_MAX_WIDTH,
                ...DISABLED_ROW_SPANNING,
                disableColumnMenu: false,
                disableReorder: true,
                renderHeader: () => {
                  return (
                    <EvaluationModelLink
                      callId={evalCallIds[0]}
                      state={props.state}
                    />
                  );
                },
                valueGetter: (value: any, row: RowData) => {
                  // Return the first non-null value from any evaluation in this model group
                  for (const evalCallId of evalCallIds) {
                    const val = row.output?.[key]?.[evalCallId];
                    if (val != null) {
                      return val;
                    }
                  }
                  return null;
                },
                renderCell: (params: GridRenderCellParams<RowData>) => {
                  // Find first non-null value from any evaluation in this model group
                  let valueToShow = null;
                  for (const evalCallId of evalCallIds) {
                    const val = params.row.output?.[key]?.[evalCallId];
                    if (val != null) {
                      valueToShow = val;
                      break;
                    }
                  }

                  return (
                    <DenseCellValue
                      value={valueToShow}
                      lineClamp={props.lineClamp}
                    />
                  );
                },
              } as GridColDef<RowData>;
            }
          );
        } else {
          // Original logic when not merging
          return props.state.evaluationCallIdsOrdered.map(evaluationCallId => {
            return {
              field: `output.${key}.${evaluationCallId}`,
              headerName: `${key}.${evaluationCallId}`,
              width: outputWidths[key],
              maxWidth: DYNAMIC_COLUMN_MAX_WIDTH,
              ...DISABLED_ROW_SPANNING,
              disableColumnMenu: false,
              disableReorder: true,
              renderHeader: (params: GridColumnHeaderParams<RowData>) => {
                return (
                  <EvaluationModelLink
                    callId={evaluationCallId}
                    state={props.state}
                  />
                );
              },
              valueGetter: (value: any, row: RowData) => {
                return row.output?.[key]?.[evaluationCallId];
              },
              renderCell: (params: GridRenderCellParams<RowData>) => {
                if (params.row._type === 'summary') {
                  // TODO: Should we indicate that this is just the first trial?
                  return (
                    <DenseCellValue
                      value={params.row.output?.[key]?.[evaluationCallId]}
                      lineClamp={props.lineClamp}
                    />
                  );
                }
                return (
                  <DenseCellValue
                    value={params.row.output?.[key]?.[evaluationCallId]}
                    lineClamp={props.lineClamp}
                  />
                );
              },
            } as GridColDef<RowData>;
          });
        }
      }),
      ...Object.entries(compositeMetrics).flatMap(
        ([metricGroupKey, metricGroupDef]) => {
          return Object.entries(metricGroupDef.metrics).flatMap(
            ([keyPath, metricDef]) => {
              if (modelGroups) {
                // When merging by model, create one column per model per metric
                return Array.from(modelGroups.entries()).map(
                  ([modelName, evalCallIds]) => {
                    const metricSubpath = Object.values(metricDef.scorerRefs)[0]
                      .metric.metricSubPath;
                    return {
                      field: `scores.${keyPath}.${modelName}`,
                      headerName:
                        metricSubpath.length > 0
                          ? metricSubpath.join('.')
                          : keyPath,
                      ...SCORE_COLUMN_SETTINGS,
                      ...DISABLED_ROW_SPANNING,
                      disableColumnMenu: false,
                      disableReorder: true,
                      renderHeader: () => {
                        return (
                          <EvaluationModelLink
                            callId={evalCallIds[0]}
                            state={props.state}
                          />
                        );
                      },
                      valueGetter: (value: any, row: RowData) => {
                        const dimension = Object.values(metricDef.scorerRefs)[0]
                          .metric;
                        // Return the first non-null value from any evaluation in this model group
                        for (const evalCallId of evalCallIds) {
                          const val = lookupMetricValueDirect(
                            row.scores,
                            evalCallId,
                            dimension,
                            compositeMetrics
                          );
                          if (val != null) {
                            return val;
                          }
                        }
                        return null;
                      },
                      renderCell: (params: GridRenderCellParams<RowData>) => {
                        const dimension = Object.values(metricDef.scorerRefs)[0]
                          .metric;

                        // Find first non-null value from any evaluation in this model group
                        let summaryValue = null;
                        for (const evalCallId of evalCallIds) {
                          const val = lookupMetricValueDirect(
                            params.row.scores,
                            evalCallId,
                            dimension,
                            compositeMetrics
                          );
                          if (val != null) {
                            summaryValue = val;
                            break;
                          }
                        }

                        const baselineValue = props.disableBaselineStats
                          ? undefined
                          : lookupMetricValueDirect(
                              params.row.scores,
                              props.state.evaluationCallIdsOrdered[0],
                              dimension,
                              compositeMetrics
                            );

                        return evalAggScorerMetricCompGeneric(
                          dimension,
                          summaryValue ?? undefined,
                          baselineValue
                        );
                      },
                    } as GridColDef<RowData>;
                  }
                );
              } else {
                // Original logic when not merging
                return props.state.evaluationCallIdsOrdered.map(
                  evaluationCallId => {
                    return {
                      field: `scores.${keyPath}.${evaluationCallId}`,
                      ...SCORE_COLUMN_SETTINGS,
                      ...DISABLED_ROW_SPANNING,
                      disableColumnMenu: false,
                      disableReorder: true,
                      renderHeader: (
                        params: GridColumnHeaderParams<RowData>
                      ) => {
                        return (
                          <EvaluationModelLink
                            callId={evaluationCallId}
                            state={props.state}
                          />
                        );
                      },
                      valueGetter: (value: any, row: RowData) => {
                        // follow this pattern in the other table type
                        const dimension = Object.values(metricDef.scorerRefs)[0]
                          .metric;
                        return lookupMetricValueDirect(
                          row.scores,
                          evaluationCallId,
                          dimension,
                          compositeMetrics
                        );
                      },
                      renderCell: (params: GridRenderCellParams<RowData>) => {
                        const dimension = Object.values(metricDef.scorerRefs)[0]
                          .metric;
                        const summaryValue = lookupMetricValueDirect(
                          params.row.scores,
                          evaluationCallId,
                          dimension,
                          compositeMetrics
                        );
                        const baselineValue = props.disableBaselineStats
                          ? undefined
                          : lookupMetricValueDirect(
                              params.row.scores,
                              props.state.evaluationCallIdsOrdered[0],
                              dimension,
                              compositeMetrics
                            );

                        return evalAggScorerMetricCompGeneric(
                          dimension,
                          summaryValue,
                          baselineValue
                        );
                      },
                    } as GridColDef<RowData>;
                  }
                );
              }
            }
          );
        }
      ),
    ];

    return res;
  }, [
    inputSubFields.inputSubFields,
    setSelectedInputDigest,
    props.onShowSplitView,
    props.state,
    inputWidths,
    hasTrials,
    toggleDefaultExpansionState,
    defaultExpandState,
    isExpanded,
    toggleExpansion,
    outputColumnKeys,
    compositeMetrics,
    outputWidths,
    filteredRows,
    props.lineClamp,
    navigateToCall,
    props.mergeDatasetResultsPerModel,
    props.disableBaselineStats,
  ]);

  const columnGroupingModel: GridColumnGroupingModel = useMemo(() => {
    // Group evaluations by model if mergeDatasetResultsPerModel is true
    const modelGroups = props.mergeDatasetResultsPerModel
      ? groupEvaluationsByModel(
          props.state.evaluationCallIdsOrdered,
          props.state.summary.evaluationCalls
        )
      : null;

    return [
      {
        groupId: 'inputs',
        headerName: 'Inputs',
        children: [
          ...inputSubFields.inputSubFields.map(key => ({
            field: `inputs.${key}`,
          })),
        ],
      },
      {
        groupId: 'predictCalls',
        headerName: 'Calls',
        [CUSTOM_GROUP_KEY_TO_CONTROL_CHILDREN_VISIBILITY]: true,
        children: modelGroups
          ? Array.from(modelGroups.keys()).map(modelName => ({
              field: `predictCall.${modelName}`,
            }))
          : props.state.evaluationCallIdsOrdered.map(evaluationCallId => ({
              field: `predictCall.${evaluationCallId}`,
            })),
      },
      {
        groupId: 'output',
        headerName: 'Output',
        children: outputColumnKeys.map(key => {
          return {
            groupId: `output.${key}`,
            headerName: removePrefix(key, 'output.'),
            [CUSTOM_GROUP_KEY_TO_CONTROL_CHILDREN_VISIBILITY]: true,
            children: modelGroups
              ? Array.from(modelGroups.keys()).map(modelName => ({
                  field: `output.${key}.${modelName}`,
                }))
              : props.state.evaluationCallIdsOrdered.map(evaluationCallId => ({
                  field: `output.${key}.${evaluationCallId}`,
                })),
          };
        }),
      },
      {
        groupId: 'scores',
        headerName: 'Scores',
        children: Object.entries(compositeMetrics).flatMap(
          ([metricGroupKey, metricGroupDef]) => {
            const firstChildKeyPath = Object.entries(
              metricGroupDef.metrics
            )[0][0];
            const children: GridColumnNode[] = Object.entries(
              metricGroupDef.metrics
            ).map(([keyPath, metricDef]) => {
              const metricSubpath = Object.values(metricDef.scorerRefs)[0]
                .metric.metricSubPath;
              return {
                groupId: `scores.${metricGroupKey}.${keyPath}`,
                [CUSTOM_GROUP_KEY_TO_CONTROL_CHILDREN_VISIBILITY]: true,
                headerName:
                  metricSubpath.length > 0 ? metricSubpath.join('.') : keyPath,
                children: modelGroups
                  ? Array.from(modelGroups.keys()).map(modelName => ({
                      field: `scores.${keyPath}.${modelName}`,
                    }))
                  : props.state.evaluationCallIdsOrdered.map(
                      evaluationCallId => ({
                        field: `scores.${keyPath}.${evaluationCallId}`,
                      })
                    ),
              };
            });

            if (
              metricGroupKey === DERIVED_SCORER_REF_PLACEHOLDER ||
              (children.length === 1 && firstChildKeyPath === metricGroupKey)
            ) {
              return children;
            }

            const res: GridColumnNode[] = [
              {
                groupId: `scores.${metricGroupKey}`,
                headerName: metricGroupKey,
                children,
              },
            ];
            (res as any)[CUSTOM_GROUP_KEY_TO_CONTROL_CHILDREN_VISIBILITY] =
              true;

            return res;
          }
        ),
      },
    ];
  }, [
    compositeMetrics,
    inputSubFields.inputSubFields,
    outputColumnKeys,
    props.state.evaluationCallIdsOrdered,
    props.state.summary.evaluationCalls,
    props.mergeDatasetResultsPerModel,
  ]);

  const onlyExpandedRows = useOnlyExpandedRows(rows, isExpanded);

  const {columnsWithControlledWidths, onColumnWidthChange} =
    useColumnsWithControlledWidths(columns);

  // Create initial column visibility model that conditionally hides scorer metrics and input/output columns
  const initialColumnVisibilityModelAsColumns = useMemo(() => {
    const hiddenColumns: Record<string, boolean> = {};

    // If defaultHiddenScorerMetrics is provided (leaderboard context),
    // hide scorer columns that don't belong to any scorer in the leaderboard
    if (props.defaultHiddenScorerMetrics) {
      columns.forEach(col => {
        if (col.field.startsWith('scores.')) {
          // Check if this column belongs to any scorer that's in the leaderboard
          // We check if the column field starts with any of the visible scorer prefixes
          // This works for both "scores.tool_usage_scorer.metric" and
          // "scores.tool_usage_scorer.metric.call-id" formats
          const shouldShow = Array.from(props.defaultHiddenScorerMetrics!).some(
            scorerPrefix => col.field.startsWith(scorerPrefix)
          );
          const shouldHide = !shouldShow;
          if (shouldHide) {
            hiddenColumns[col.field] = false; // false means hidden in MUI DataGrid
          }
        }
      });
    }
    // If no defaultHiddenScorerMetrics provided (regular compare context),
    // show all scorer metrics by default (don't add them to hiddenColumns)

    // Hide input and output columns if requested (for leaderboard context)
    if (props.hideInputOutputColumns) {
      columns.forEach(col => {
        if (
          col.field.startsWith('inputs.') ||
          col.field.startsWith('output.')
        ) {
          hiddenColumns[col.field] = false; // false means hidden in MUI DataGrid
        }
      });
    }

    return hiddenColumns;
  }, [columns, props.defaultHiddenScorerMetrics, props.hideInputOutputColumns]);

  if (inputSubFields.loading || props.state.loadableComparisonResults.loading) {
    return <LoadingDots />;
  }

  return (
    <StyledDataGrid
      onColumnWidthChange={onColumnWidthChange}
      pinnedColumns={{
        left: ['inputDigest'],
      }}
      columnHeaderHeight={36}
      rowHeight={props.rowHeight}
      rowSelectionModel={selectedRowInputDigest}
      unstable_rowSpanning={true}
      columns={columnsWithControlledWidths}
      rows={onlyExpandedRows}
      columnGroupingModel={columnGroupingModel}
      disableRowSelectionOnClick
      pagination
      pageSizeOptions={[50]}
      initialState={{
        columns: {
          columnVisibilityModel: initialColumnVisibilityModelAsColumns,
        },
        sorting: {
          sortModel: [{field: 'dataset', sort: 'asc'}],
        },
      }}
      sx={{
        ...styledDataGridStyleOverrides,
        backgroundColor: 'white',
      }}
      slots={{
        columnsPanel: ColumnsManagementPanel,
        footer: () => (
          <CustomFooter
            setRowHeightToSingle={props.setRowHeightToSingle}
            setRowHeightToThree={props.setRowHeightToThree}
            setRowHeightToSix={props.setRowHeightToSix}
            currentRowHeight={props.rowHeight}
            onlyOneModel={props.onlyOneModel}
            setModelsAsRows={props.setModelsAsRows}
            shouldHighlightSelectedRow={props.shouldHighlightSelectedRow}
            onShowSplitView={props.onShowSplitView}
            mergeDatasetResultsPerModel={props.mergeDatasetResultsPerModel}
          />
        ),
      }}
    />
  );
};

const useColumnsWithControlledWidths = (columns: GridColDef<RowData>[]) => {
  const columnWdithOverrides = useRef<{[key: string]: number}>({});

  const columnsWithControlledWidths = useMemo(() => {
    return columns.map(col => {
      return {
        ...col,
        width: columnWdithOverrides.current[col.field] ?? col.width,
      };
    });
  }, [columns]);

  const onColumnWidthChange: GridEventListener<
    'columnWidthChange'
  > = params => {
    columnWdithOverrides.current[params.colDef.field] = params.width;
  };

  return {
    columnsWithControlledWidths,
    onColumnWidthChange,
  };
};
