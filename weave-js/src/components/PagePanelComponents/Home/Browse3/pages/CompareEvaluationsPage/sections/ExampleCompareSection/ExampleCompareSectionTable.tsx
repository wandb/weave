import {Box, SxProps, Tooltip} from '@mui/material';
import {
  GridColDef,
  GridColumnGroupingModel,
  GridColumnHeaderParams,
  GridColumnNode,
  GridEventListener,
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import {MOON_50} from '@wandb/weave/common/css/color.styles';
import {Icon} from '@wandb/weave/components/Icon';
import {IconButton} from '@wandb/weave/components/IconButton';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {CellValue} from '@wandb/weave/components/PagePanelComponents/Home/Browse2/CellValue';
import {parseRefMaybe} from '@wandb/weave/react';
import _ from 'lodash';
import React, {useCallback, useMemo, useRef, useState} from 'react';

import {NotApplicable} from '../../../../NotApplicable';
import {StyledDataGrid} from '../../../../StyledDataGrid';
import {IdPanel} from '../../../common/Id';
import {CallLink} from '../../../common/Links';
import {
  CompareEvaluationContext,
  useCompareEvaluationsState,
} from '../../compareEvaluationsContext';
import {
  buildCompositeMetricsMap,
  DERIVED_SCORER_REF_PLACEHOLDER,
} from '../../compositeMetricsUtil';
import {EvaluationComparisonState} from '../../ecpState';
import {HorizontalBox, VerticalBox} from '../../Layout';
import {EvaluationModelLink} from '../ComparisonDefinitionSection/EvaluationDefinition';
import {
  ColumnsManagementPanel,
  CUSTOM_GROUP_KEY_TO_CONTROL_CHILDREN_VISIBILITY,
} from './ColumnsManagementPanel';
import {HEADER_HIEGHT_PX} from './common';
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
  width: '100%',
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
}

interface ExampleCompareSectionTableProps {
  state: EvaluationComparisonState;
  shouldHighlightSelectedRow?: boolean;
  onShowSplitView: () => void;
}

/**
 * Constants
 */
const DISABLED_ROW_SPANNING = {
  rowSpanValueGetter: (value: any, row: RowData) => row.id,
};

const SCORE_COLUMN_SETTINGS = {
  flex: 1,
  minWidth: 120,
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
  return <DenseCellValue value={row.targetRowValue?.[props.inputKey]} />;
};

const DenseCellValue: React.FC<
  React.ComponentProps<typeof CellValue>
> = props => {
  if (props.value == null) {
    return <NotApplicable />;
  }
  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '4px',
      }}>
      <CellValue
        value={props.value}
        stringStyle={{
          maxHeight: '100%',
          width: '100%',
          overflow: 'auto',
          textAlign: 'left',
          lineHeight: '1.2',
          flex: 1,
          whiteSpace: 'pre-wrap',
          wordWrap: 'break-word',
          textOverflow: 'ellipsis',
          display: 'flex',
        }}
      />
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
  const [modelsAsRows, setModelsAsRows] = useState(false);
  const [rowHeight, setRowHeight] = useState(70);
  const increaseRowHeight = useCallback(() => {
    setRowHeight(v => clip(v * 2, 35, 35 * 2 ** 4));
  }, []);
  const decreaseRowHeight = useCallback(() => {
    setRowHeight(v => clip(v / 2, 35, 35 * 2 ** 4));
  }, []);
  const onlyOneModel = props.state.evaluationCallIdsOrdered.length === 1;
  const header = (
    <HorizontalBox
      sx={{
        justifyContent: 'space-between',
        alignItems: 'center',
        bgcolor: MOON_50,
        padding: '16px',
        height: HEADER_HIEGHT_PX,
      }}>
      <HorizontalBox
        sx={{
          justifyContent: 'flex-start',
          alignItems: 'center',
        }}>
        <Tooltip title="Increase Row Height">
          <IconButton onClick={increaseRowHeight}>
            <Icon name="expand-uncollapse" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Decrease Row Height">
          <IconButton onClick={decreaseRowHeight}>
            <Icon name="collapse" />
          </IconButton>
        </Tooltip>
        {!onlyOneModel && (
          <Tooltip title="Pivot on Model">
            <IconButton onClick={() => setModelsAsRows(v => !v)}>
              <Icon name="table" />
            </IconButton>
          </Tooltip>
        )}
      </HorizontalBox>
      <HorizontalBox
        sx={{
          justifyContent: 'flex-start',
          alignItems: 'center',
        }}>
        {!props.shouldHighlightSelectedRow && (
          <Tooltip title="Show Detail Panel">
            <IconButton onClick={props.onShowSplitView}>
              <Icon name="panel" />
            </IconButton>
          </Tooltip>
        )}
      </HorizontalBox>
    </HorizontalBox>
  );
  const inner =
    modelsAsRows || onlyOneModel ? (
      <ExampleCompareSectionTableModelsAsRows
        {...props}
        rowHeight={rowHeight}
      />
    ) : (
      <ExampleCompareSectionTableModelsAsColumns
        {...props}
        rowHeight={rowHeight}
      />
    );
  return (
    <VerticalBox
      sx={{
        height: '100%',
        width: '100%',
        gridGap: '0px',
      }}>
      {header}
      {inner}
    </VerticalBox>
  );
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

const inputFields = (
  inputSubFields: string[],
  setSelectedInputDigest: (inputDigest: string) => void,
  onShowSplitView: () => void,
  columnWidths: {[key: string]: number}
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
          }}
          onClick={() => {
            setSelectedInputDigest(params.row.inputDigest);
            onShowSplitView();
          }}>
          <span style={{flexShrink: 1}}>
            <IdPanel clickable>{params.row.inputDigest.slice(-4)}</IdPanel>
          </span>
        </Box>
      );
    },
  },
  ...inputSubFields.map(key => ({
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
        />
      );
    },
  })),
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
      <IconButton onClick={toggleDefaultExpansionState}>
        <Icon
          name={
            defaultExpandState === 'expanded' ? 'collapse' : 'expand-uncollapse'
          }
        />
      </IconButton>
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
        <IconButton
          onClick={() => {
            toggleExpansion(params.row._expansionId);
          }}>
          <Icon name={itemIsExpanded ? 'collapse' : 'expand-uncollapse'} />
        </IconButton>
      </Box>
    );
  },
});

// Component for displaying models as rows
export const ExampleCompareSectionTableModelsAsRows: React.FC<
  ExampleCompareSectionTableProps & {rowHeight: number}
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

  const columns: GridColDef<RowData>[] = useMemo(() => {
    const res: GridColDef<RowData>[] = [
      ...inputFields(
        inputSubFields.inputSubFields,
        setSelectedInputDigest,
        props.onShowSplitView,
        inputWidths
      ),
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
            },
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
                  display: 'flex',
                  alignItems: 'center',
                }}>
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
      ...outputColumnKeys.map(key => ({
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
                value={params.row.output[key]?.[params.row.evaluationCallId]}
              />
            );
          }
          return (
            <DenseCellValue
              value={params.row.output[key]?.[params.row.evaluationCallId]}
            />
          );
        },
      })),
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
                  const baselineValue = lookupMetricValueDirect(
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
              };
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
  ]);

  console.log(compositeMetrics);

  const columnGroupingModel: GridColumnGroupingModel = useMemo(() => {
    return [
      {
        groupId: 'inputs',
        headerName: 'Inputs',
        children: inputSubFields.inputSubFields.map(key => ({
          field: `inputs.${key}`,
        })),
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

  if (inputSubFields.loading || props.state.loadableComparisonResults.loading) {
    return <LoadingDots />;
  }
  return (
    <StyledDataGrid
      onColumnWidthChange={onColumnWidthChange}
      pinnedColumns={{
        left: ['inputDigest'],
      }}
      rowHeight={props.rowHeight}
      rowSelectionModel={selectedRowInputDigest}
      unstable_rowSpanning={true}
      columns={columnsWithControlledWidths}
      rows={onlyExpandedRows}
      columnGroupingModel={columnGroupingModel}
      disableRowSelectionOnClick
      pagination
      pageSizeOptions={[50]}
      sx={styledDataGridStyleOverrides}
      slots={{columnsPanel: ColumnsManagementPanel}}
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
  ExampleCompareSectionTableProps & {rowHeight: number}
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

  const columns: GridColDef<RowData>[] = useMemo(() => {
    const res: GridColDef<RowData>[] = [
      ...inputFields(
        inputSubFields.inputSubFields,
        setSelectedInputDigest,
        props.onShowSplitView,
        inputWidths
      ),
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
      ...outputColumnKeys.flatMap(key => {
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
                  />
                );
              }
              return (
                <DenseCellValue
                  value={params.row.output?.[key]?.[evaluationCallId]}
                />
              );
            },
          };
        });
      }),
      ...Object.entries(compositeMetrics).flatMap(
        ([metricGroupKey, metricGroupDef]) => {
          return Object.entries(metricGroupDef.metrics).flatMap(
            ([keyPath, metricDef]) => {
              return props.state.evaluationCallIdsOrdered.map(
                evaluationCallId => {
                  return {
                    field: `scores.${keyPath}.${evaluationCallId}`,
                    ...SCORE_COLUMN_SETTINGS,
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
                      const baselineValue = lookupMetricValueDirect(
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
                  };
                }
              );
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
  ]);

  console.log(compositeMetrics);

  const columnGroupingModel: GridColumnGroupingModel = useMemo(() => {
    return [
      {
        groupId: 'inputs',
        headerName: 'Inputs',
        children: inputSubFields.inputSubFields.map(key => ({
          field: `inputs.${key}`,
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
            children: props.state.evaluationCallIdsOrdered.map(
              evaluationCallId => {
                return {
                  field: `output.${key}.${evaluationCallId}`,
                };
              }
            ),
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
                children: props.state.evaluationCallIdsOrdered.map(
                  evaluationCallId => {
                    return {
                      field: `scores.${keyPath}.${evaluationCallId}`,
                    };
                  }
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
  ]);

  const onlyExpandedRows = useOnlyExpandedRows(rows, isExpanded);

  const {columnsWithControlledWidths, onColumnWidthChange} =
    useColumnsWithControlledWidths(columns);

  if (inputSubFields.loading || props.state.loadableComparisonResults.loading) {
    return <LoadingDots />;
  }

  return (
    <StyledDataGrid
      onColumnWidthChange={onColumnWidthChange}
      pinnedColumns={{
        left: ['inputDigest'],
      }}
      rowHeight={props.rowHeight}
      rowSelectionModel={selectedRowInputDigest}
      unstable_rowSpanning={true}
      columns={columnsWithControlledWidths}
      rows={onlyExpandedRows}
      columnGroupingModel={columnGroupingModel}
      disableRowSelectionOnClick
      pagination
      pageSizeOptions={[50]}
      sx={styledDataGridStyleOverrides}
      slots={{columnsPanel: ColumnsManagementPanel}}
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

const clip = (value: number, min: number, max: number) => {
  return Math.max(min, Math.min(value, max));
};
