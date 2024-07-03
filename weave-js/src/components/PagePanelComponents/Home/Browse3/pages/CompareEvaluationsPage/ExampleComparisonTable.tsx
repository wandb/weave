import {Box} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import {
  GridColDef,
  GridColumnGroup,
  GridColumnGroupingModel,
  GridValueGetterParams,
} from '@mui/x-data-grid-pro';
import React, {useMemo} from 'react';

import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {Icon, IconNames} from '../../../../../Icon';
import {SmallRef} from '../../../Browse2/SmallRef';
import {StyledDataGrid} from '../../StyledDataGrid';
import {ValueViewNumber} from '../CallPage/ValueViewNumber';
import {CallLink} from '../common/Links';
import {useFilteredAggregateRows} from './comparisonTableUtil';
import {CIRCLE_SIZE, SIGNIFICANT_DIGITS} from './constants';
import {HorizontalBox} from './Layout';
import {EvaluationComparisonState} from './types';

export const CompareEvaluationsCallsTable: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {filteredRows, inputColumnKeys, outputColumnKeys, scoreMap, leafDims} =
    useFilteredAggregateRows(props.state);

  const {cols: columns, grouping: groupingModel} = useMemo(() => {
    const cols: Array<GridColDef<(typeof filteredRows)[number]>> = [];
    const grouping: GridColumnGroupingModel = [];
    // Columns:
    // 1. dataset row identifier
    // 2. dataset row contents (input)
    // (Grouped Aggregates - Model Outputs)
    // 3. Model Output (Grouping here is odd - likely just take last?)
    // 3.(n) -> split for each comparison
    // 4. Model Latency (average)
    // 4.(n) -> split for each comparison
    // 5. Model Tokens (average)
    // 5.(n) -> split for each comparison
    // (Grouped Aggregates - Scoring Function)
    // 6.(s) Each scoring key (average)
    // 6.(s).(n) -> split for each comparison
    const headerMap = Object.fromEntries(
      leafDims.map(dim => {
        const evalCall = props.state.data.evaluationCalls[dim];
        return [
          dim,
          <CallLink
            entityName={
              evalCall._rawEvaluationTraceData.project_id.split('/')[0]
            }
            projectName={
              evalCall._rawEvaluationTraceData.project_id.split('/')[1]
            }
            opName={evalCall._rawEvaluationTraceData.op_name}
            callId={dim}
            icon={<Circle sx={{color: evalCall.color, height: CIRCLE_SIZE}} />}
            noName
          />,
        ];
      })
    );

    const recursiveGetChildren = (
      params: GridValueGetterParams<(typeof filteredRows)[number]>
    ) => {
      let rowNode = params.rowNode;
      while (rowNode.type === 'group') {
        rowNode = params.api.getRowNode(rowNode.children[0])!;
      }
      return params.api.getRow(rowNode.id);
    };

    const removePrefix = (key: string, prefix: string) => {
      if (key.startsWith(prefix)) {
        return key.slice(prefix.length);
      }
      return key;
    };

    const inputGroup: GridColumnGroup = {
      groupId: 'input',
      children: [],
    };

    cols.push({
      field: 'rowDigest',
      headerName: '',
      sortable: false,
      width: 30,
      renderHeader: params => {
        return (
          <HorizontalBox
            sx={{
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
            }}>
            <Icon name={IconNames.LinkAlt} />
          </HorizontalBox>
        );
      },
      valueGetter: params => {
        return recursiveGetChildren(params).inputRef;
      },
      renderCell: params => {
        const refStr = params.value;
        const refParsed = parseRef(refStr) as WeaveObjectRef;
        return (
          <HorizontalBox
            sx={{
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
            }}>
            <SmallRef objRef={refParsed} iconOnly />
          </HorizontalBox>
        );
      },
    });

    inputGroup.children.push({field: 'rowDigest'});

    inputColumnKeys.forEach(key => {
      cols.push({
        field: 'input.' + key,
        headerName: removePrefix(key, 'input.'),
        valueGetter: params => {
          return recursiveGetChildren(params).input[key];
        },
      });
      inputGroup.children.push({field: 'input.' + key});
    });
    grouping.push(inputGroup);

    const outputGroup: GridColumnGroup = {
      groupId: 'output',
      renderHeaderGroup: params => {
        return 'Output  (Last)';
      },
      children: [],
    };
    outputColumnKeys.forEach(key => {
      const outputSubGroup: GridColumnGroup = {
        groupId: 'output.' + key,
        renderHeaderGroup: params => {
          return removePrefix(key, 'output.');
        },
        children: [],
      };
      leafDims.forEach(dim => {
        cols.push({
          field: 'output.' + key + '.' + dim,
          flex: 1,
          // headerName: key + ' (Last)',
          // headerName: removePrefix(key, 'output.'),
          renderHeader: params => headerMap[dim],
          valueGetter: params => {
            return recursiveGetChildren(params).output[key][dim];
          },
        });
        outputSubGroup.children.push({field: 'output.' + key + '.' + dim});
      });
      outputGroup.children.push(outputSubGroup);
    });
    grouping.push(outputGroup);

    const latencyGroup: GridColumnGroup = {
      groupId: 'modelLatency',
      renderHeaderGroup: params => {
        return 'Latency (Avg)';
      },
      children: [],
    };
    leafDims.forEach(dim => {
      cols.push({
        field: 'modelLatency.' + dim,
        renderHeader: params => headerMap[dim],
        valueGetter: params => {
          return recursiveGetChildren(params).latency[dim];
        },
        renderCell: params => {
          return (
            <ValueViewNumber
              fractionDigits={SIGNIFICANT_DIGITS}
              value={params.value}
            />
          );
        },
      });
      latencyGroup.children.push({field: 'modelLatency.' + dim});
    });
    grouping.push(latencyGroup);

    const tokenGroup: GridColumnGroup = {
      groupId: 'totalTokens',
      renderHeaderGroup: params => {
        return 'Tokens (Avg)';
      },
      children: [],
    };
    leafDims.forEach(dim => {
      cols.push({
        field: 'totalTokens.' + dim,
        renderHeader: params => headerMap[dim],
        valueGetter: params => {
          return recursiveGetChildren(params).totalTokens[dim];
        },
        renderCell: params => {
          return (
            <ValueViewNumber
              fractionDigits={SIGNIFICANT_DIGITS}
              value={params.value}
            />
          );
        },
      });
      tokenGroup.children.push({field: 'totalTokens.' + dim});
    });
    grouping.push(tokenGroup);

    const scoresGroup: GridColumnGroup = {
      groupId: 'scores',
      renderHeaderGroup: params => {
        return 'Scores';
      },
      children: [],
    };
    Object.keys(scoreMap).forEach(scoreId => {
      const scoresSubGroup: GridColumnGroup = {
        groupId: 'scorer.' + scoreId,
        renderHeaderGroup: params => {
          const scorer = scoreMap[scoreId];
          const scorerRefParsed = parseRef(scorer.scorerRef) as WeaveObjectRef;

          return <SmallRef objRef={scorerRefParsed} />;
        },
        children: [],
      };
      leafDims.forEach(dim => {
        cols.push({
          field: 'scorer.' + scoreId + '.' + dim,
          renderHeader: params => headerMap[dim],
          valueGetter: params => {
            return recursiveGetChildren(params).scores[scoreId][dim];
          },
          renderCell: params => {
            return (
              <ValueViewNumber
                fractionDigits={SIGNIFICANT_DIGITS}
                value={params.value}
              />
            );
          },
        });
        scoresSubGroup.children.push({field: 'scorer.' + scoreId + '.' + dim});
      });
      scoresGroup.children.push(scoresSubGroup);
    });
    grouping.push(scoresGroup);

    return {cols, grouping};
  }, [
    inputColumnKeys,
    leafDims,
    outputColumnKeys,
    props.state.data.evaluationCalls,
    scoreMap,
  ]);

  // const {setSelectedInputDigest} = useCompareEvaluationsState();

  // const getTreeDataPath: DataGridProProps['getTreeDataPath'] = row => row.path;
  return (
    <Box
      sx={{
        height: 'calc(100vh - 114px)',
        width: '100%',
        overflow: 'hidden',
      }}>
      <StyledDataGrid
        // Start Column Menu
        // ColumnMenu is only needed when we have other actions
        // such as filtering.
        disableColumnMenu={true}
        // In this context, we don't need to filter columns. I suppose
        // we can add this in the future, but we should be intentional
        // about what we enable.
        disableColumnFilter={true}
        disableMultipleColumnsFiltering={true}
        // ColumnPinning seems to be required in DataGridPro, else it crashes.
        disableColumnPinning={false}
        // There is no need to reorder the 2 columns in this context.
        disableColumnReorder={true}
        // Resizing columns might be helpful to show more data
        disableColumnResize={false}
        // There are only 2 columns, let's not confuse the user.
        disableColumnSelector={true}
        // We don't need to sort multiple columns.
        disableMultipleColumnsSorting={true}
        // End Column Menu
        // treeData
        // getTreeDataPath={row => row.path.toStringArray()}
        rows={filteredRows}
        columns={columns}
        // isGroupExpandedByDefault={node => {
        //   return expandedIds.includes(node.id);
        // }}
        columnHeaderHeight={38}
        rowHeight={60}
        experimentalFeatures={{columnGrouping: true}}
        columnGroupingModel={groupingModel}
        // groupingColDef={}
        // treeData
        // getTreeDataPath={getTreeDataPath}
        // getRowHeight={(params: GridRowHeightParams) => {
        //   const isNonRefString =
        //     params.model.valueType === 'string' && !isRef(params.model.value);
        //   const isArray = params.model.valueType === 'array';
        //   const isTableRef =
        //     isRef(params.model.value) &&
        //     (parseRefMaybe(params.model.value) as any).weaveKind === 'table';
        //   const {isCode} = params.model;
        //   if (
        //     isNonRefString ||
        //     (isArray && USE_TABLE_FOR_ARRAYS) ||
        //     isTableRef ||
        //     isCode
        //   ) {
        //     return 'auto';
        //   }
        //   return 38;
        // }}
        // hideFooter
        // rowSelection={false}
        // groupingColDef={groupingColDef}
        // rowSelection={true}
        // rowSelectionModel={
        //   props.state.selectedInputDigest
        //     ? [props.state.selectedInputDigest]
        //     : []
        // }
        // disableMultipleRowSelection
        // onRowSelectionModelChange={newSelection => {
        //   setSelectedInputDigest(newSelection[0].toString() ?? null);
        // }}
        sx={{
          '& .MuiDataGrid-cell': {
            textWrap: 'wrap !important',
            // whiteSpace: 'normal',
            overflow: 'auto !important',
            alignItems: 'flex-start',
            // textOverflow: 'ellipsis',
          },
        }}
      />
    </Box>
  );
};
