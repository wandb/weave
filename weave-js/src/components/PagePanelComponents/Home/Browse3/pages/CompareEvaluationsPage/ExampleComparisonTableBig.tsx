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

export const CompareEvaluationsCallsTableBig: React.FC<{
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
              // bgcolor: '#FAFAFA',
              height: '100%',
            }}>
            <SmallRef objRef={refParsed} iconOnly />
          </HorizontalBox>
        );
      },
    });

    inputGroup.children.push({field: 'rowDigest'});

    // inputColumnKeys.forEach(key => {
    //   cols.push({
    //     field: 'input.' + key,
    //     width: 400,
    //     headerName: removePrefix(key, 'input.'),
    //     valueGetter: params => {
    //       return recursiveGetChildren(params).input[key];
    //     },
    //   });
    //   inputGroup.children.push({field: 'input.' + key});
    // });
    // grouping.push(inputGroup);

    const KeyValTable: React.FC<{
      entries: Array<{key: React.ReactNode; val: React.ReactNode}>;
      noKey?: boolean;
      noPadding?: boolean;
      evenHeight?: boolean;
    }> = ({entries, noKey, noPadding, evenHeight}) => {
      return (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: noKey ? '1rf' : 'min-content 1fr',
            gridTemplateRows: (evenHeight ? '1fr ' : 'auto ').repeat(
              entries.length
            ),
            height: '100%',
            width: '100%',
          }}>
          {entries.map(({key, val}, ndx) => {
            return (
              <React.Fragment key={ndx}>
                {!noKey && (
                  <div
                    style={{
                      borderTop: '1px solid rgba(224, 224, 224, 1)',
                      fontWeight: 'bold',
                      // backgroundColor: '#FAFAFA',
                      padding: 8,
                      color: '#79808A',
                      borderRight: '1px solid rgba(224, 224, 224, 1)',
                      textAlign: 'right',
                    }}>
                    {key}
                  </div>
                )}
                <div
                  style={{
                    borderTop: '1px solid rgba(224, 224, 224, 1)',
                    // '&:first-child': {
                    //   borderTop: 'none',
                    // },
                    padding: noPadding ? 0 : 8,
                    // textWrap: 'wrap' as any,
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'break-word',
                    overflow: 'auto',
                  }}>
                  {val}
                </div>
              </React.Fragment>
            );
          })}
        </div>
      );
    };

    cols.push({
      field: 'allInput',
      minWidth: 300,
      flex: 1,
      headerName: 'Input',
      renderCell: params => {
        return (
          <KeyValTable
            entries={inputColumnKeys.map(key => {
              const val = params.row.input[key];
              return {key: removePrefix(key, 'input.'), val};
            })}
          />
        );
      },
    });

    // const outputGroup: GridColumnGroup = {
    //   groupId: 'output',
    //   renderHeaderGroup: params => {
    //     return 'Output  (Last)';
    //   },
    //   children: [],
    // };
    // outputColumnKeys.forEach(key => {
    //   const outputSubGroup: GridColumnGroup = {
    //     groupId: 'output.' + key,
    //     renderHeaderGroup: params => {
    //       return removePrefix(key, 'output.');
    //     },
    //     children: [],
    //   };
    //   leafDims.forEach(dim => {
    //     cols.push({
    //       field: 'output.' + key + '.' + dim,
    //       flex: 1,
    //       // headerName: key + ' (Last)',
    //       // headerName: removePrefix(key, 'output.'),
    //       renderHeader: params => headerMap[dim],
    //       valueGetter: params => {
    //         return recursiveGetChildren(params).output[key][dim];
    //       },
    //     });
    //     outputSubGroup.children.push({field: 'output.' + key + '.' + dim});
    //   });
    //   outputGroup.children.push(outputSubGroup);
    // });
    // grouping.push(outputGroup);

    cols.push({
      field: 'allOutput',
      minWidth: 500,
      flex: 2,
      headerName: 'Output (Last)',
      renderCell: params => {
        return (
          <KeyValTable
            evenHeight
            noPadding
            entries={leafDims.map(dim => {
              return {
                key: headerMap[dim],
                val: (
                  <KeyValTable
                    entries={outputColumnKeys.map(oKey => {
                      return {
                        key: removePrefix(oKey, 'output.'),
                        val: params.row.output[oKey][dim].toString(),
                      };
                    })}
                  />
                ),
              };
            })}
          />
        );
      },
    });

    // const latencyGroup: GridColumnGroup = {
    //   groupId: 'modelLatency',
    //   renderHeaderGroup: params => {
    //     return 'Latency (Avg)';
    //   },
    //   children: [],
    // };
    // leafDims.forEach(dim => {
    //   cols.push({
    //     field: 'modelLatency.' + dim,
    //     renderHeader: params => headerMap[dim],
    //     valueGetter: params => {
    //       return recursiveGetChildren(params).latency[dim];
    //     },
    //     renderCell: params => {
    //       return (
    //         <ValueViewNumber
    //           fractionDigits={SIGNIFICANT_DIGITS}
    //           value={params.value}
    //         />
    //       );
    //     },
    //   });
    //   latencyGroup.children.push({field: 'modelLatency.' + dim});
    // });
    // grouping.push(latencyGroup);

    cols.push({
      field: 'modelLatency',
      headerName: 'Latency (Avg)',
      minWidth: 75,
      renderCell: params => {
        return (
          <KeyValTable
            noKey
            evenHeight
            entries={leafDims.map(dim => {
              return {
                key: dim,
                val: (
                  <ValueViewNumber
                    fractionDigits={SIGNIFICANT_DIGITS}
                    value={params.row.latency[dim]}
                  />
                ),
              };
            })}
          />
        );
      },
    });

    // const tokenGroup: GridColumnGroup = {
    //   groupId: 'totalTokens',
    //   renderHeaderGroup: params => {
    //     return 'Tokens (Avg)';
    //   },
    //   children: [],
    // };
    // leafDims.forEach(dim => {
    //   cols.push({
    //     field: 'totalTokens.' + dim,
    //     renderHeader: params => headerMap[dim],
    //     valueGetter: params => {
    //       return recursiveGetChildren(params).totalTokens[dim];
    //     },
    //     renderCell: params => {
    //       return (
    //         <ValueViewNumber
    //           fractionDigits={SIGNIFICANT_DIGITS}
    //           value={params.value}
    //         />
    //       );
    //     },
    //   });
    //   tokenGroup.children.push({field: 'totalTokens.' + dim});
    // });
    // grouping.push(tokenGroup);
    cols.push({
      field: 'totalTokens',
      headerName: 'Tokens (Avg)',
      minWidth: 75,
      renderCell: params => {
        return (
          <KeyValTable
            noKey
            evenHeight
            entries={leafDims.map(dim => {
              return {
                key: dim,
                val: (
                  <ValueViewNumber
                    fractionDigits={SIGNIFICANT_DIGITS}
                    value={params.row.totalTokens[dim]}
                  />
                ),
              };
            })}
          />
        );
      },
    });

    // const scoresGroup: GridColumnGroup = {
    //   groupId: 'scores',
    //   renderHeaderGroup: params => {
    //     return 'Scores';
    //   },
    //   children: [],
    // };
    // Object.keys(scoreMap).forEach(scoreId => {
    //   const scoresSubGroup: GridColumnGroup = {
    //     groupId: 'scorer.' + scoreId,
    //     renderHeaderGroup: params => {
    //       const scorer = scoreMap[scoreId];
    //       const scorerRefParsed = parseRef(scorer.scorerRef) as WeaveObjectRef;

    //       return <SmallRef objRef={scorerRefParsed} />;
    //     },
    //     children: [],
    //   };
    //   leafDims.forEach(dim => {
    //     cols.push({
    //       field: 'scorer.' + scoreId + '.' + dim,
    //       renderHeader: params => headerMap[dim],
    //       valueGetter: params => {
    //         return recursiveGetChildren(params).scores[scoreId][dim];
    //       },
    //       renderCell: params => {
    //         return (
    //           <ValueViewNumber
    //             fractionDigits={SIGNIFICANT_DIGITS}
    //             value={params.value}
    //           />
    //         );
    //       },
    //     });
    //     scoresSubGroup.children.push({field: 'scorer.' + scoreId + '.' + dim});
    //   });
    //   scoresGroup.children.push(scoresSubGroup);
    // });
    // grouping.push(scoresGroup);

    // const scoresGroup: GridColumnGroup = {
    //   groupId: 'scores',
    //   renderHeaderGroup: params => {
    //     return 'Scores';
    //   },
    //   children: [],
    // };
    Object.keys(scoreMap).forEach(scoreId => {
      // const scoresSubGroup: GridColumnGroup = {
      //   groupId: 'scorer.' + scoreId,
      //   renderHeaderGroup: params => {
      //     const scorer = scoreMap[scoreId];
      //     const scorerRefParsed = parseRef(scorer.scorerRef) as WeaveObjectRef;

      //     return <SmallRef objRef={scorerRefParsed} />;
      //   },
      //   children: [],
      // };
      // leafDims.forEach(dim => {
      cols.push({
        minWidth: 50,
        flex: 1,
        maxWidth: 150,
        field: 'scorer.' + scoreId,
        renderHeader: params => {
          const scorer = scoreMap[scoreId];
          const scorerRefParsed = parseRef(scorer.scorerRef) as WeaveObjectRef;

          return <SmallRef objRef={scorerRefParsed} />;
        },
        renderCell: params => {
          return (
            <KeyValTable
              noKey
              evenHeight
              entries={leafDims.map(dim => {
                return {
                  key: dim,
                  val: (
                    <ValueViewNumber
                      fractionDigits={SIGNIFICANT_DIGITS}
                      value={params.row.scores[scoreId][dim]}
                    />
                  ),
                };
              })}
            />
          );
          // return (
          //   <ValueViewNumber
          //     fractionDigits={SIGNIFICANT_DIGITS}
          //     value={params.value}
          //   />
          // );
        },
      });
      // scoresSubGroup.children.push({field: 'scorer.' + scoreId + '.' + dim});
      // });
      // scoresGroup.children.push(scoresSubGroup);
    });
    // grouping.push(scoresGroup);

    return {cols, grouping};
  }, [
    leafDims,
    inputColumnKeys,
    outputColumnKeys,
    props.state.data.evaluationCalls,
    scoreMap,
  ]);

  // const {setSelectedInputDigest} = useCompareEvaluationsState();

  // const getTreeDataPath: DataGridProProps['getTreeDataPath'] = row => row.path;
  return (
    <Box
      sx={{
        // height: '50vh',
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
        rowHeight={inputColumnKeys.length * 150}
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
        rowSelection={false}
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
            padding: '0px',
          },
        }}
      />
    </Box>
  );
};
