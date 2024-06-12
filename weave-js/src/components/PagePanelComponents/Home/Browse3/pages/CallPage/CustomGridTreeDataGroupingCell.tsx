import {ExpandMore, KeyboardArrowRight} from '@mui/icons-material';
import {ButtonProps} from '@mui/material';
import Box from '@mui/material/Box';
import MuiButton from '@mui/material/Button';
import {GridRenderCellParams, useGridApiContext} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, MouseEvent, useMemo} from 'react';
import styled from 'styled-components';

import {MOON_500} from '../../../../../../common/css/color.styles';
import {IconParentBackUp} from '../../../../../Icon';
import {Tooltip} from '../../../../../Tooltip';
import {opNiceName} from '../common/Links';
import {StatusChip} from '../common/StatusChip';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CursorBox} from './CursorBox';
import {TraceUsageStats} from './TraceUsageStats';

const INSET_SPACING = 54;
const TREE_COLOR = '#aaaeb2';
const BORDER_STYLE = `1px solid ${TREE_COLOR}`;

const CallOrCountRow = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-items: center;
  gap: 6px;
  padding-top: 10px;
`;
CallOrCountRow.displayName = 'S.CallOrCountRow';

/**
 * Utility component to render the grouping cell for the trace tree.
 * Most of the work here is to rendering the tree structure (i.e. the
 * lines connecting the cells, expanding/collapsing the tree, etc).
 */
export const CustomGridTreeDataGroupingCell: FC<
  GridRenderCellParams & {onClick?: (event: MouseEvent) => void}
> = props => {
  const {id, field, rowNode, row} = props;
  const {isParentRow} = row;
  const call = row.call as CallSchema;
  const apiRef = useGridApiContext();
  const handleClick: ButtonProps['onClick'] = event => {
    if (rowNode.type !== 'group') {
      return;
    }

    apiRef.current.setRowChildrenExpansion(id, !rowNode.childrenExpanded);
    apiRef.current.setCellFocus(id, field);

    if (props.onClick) {
      props.onClick(event);
    }

    event.stopPropagation();
  };

  const hasCountRow = apiRef.current.getRowNode('HIDDEN_SIBLING_COUNT') != null;
  const isLastChild = useMemo(() => {
    if (rowNode.parent == null) {
      return false;
    }
    const parentRow = apiRef.current.getRowNode(rowNode.parent);
    if (parentRow == null) {
      return false;
    }
    const childrenIds = apiRef.current.getRowGroupChildren({
      groupId: parentRow.id,
    });
    if (childrenIds == null) {
      return false;
    }
    const lastChildId = childrenIds[childrenIds.length - 1];
    return rowNode.id === lastChildId;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiRef, rowNode.id, rowNode.parent, hasCountRow]);

  const tooltip = isParentRow
    ? 'This is the parent of the currently viewed call. Click to view.'
    : undefined;
  const rowTypeIndicator = isParentRow ? (
    <IconParentBackUp color={MOON_500} width={18} height={18} />
  ) : null;

  const isHiddenCount = id === 'HIDDEN_SIBLING_COUNT';

  const box = (
    <CursorBox
      $isClickable={!isHiddenCount}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'left',
        width: '100%',
      }}>
      {_.range(rowNode.depth).map(i => {
        return (
          <Box
            key={i}
            sx={{
              flex: `0 0 ${INSET_SPACING / 2}px`,
              width: `${INSET_SPACING / 2}px`,
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <Box
              sx={{
                width: '100%',
                height: '100%',
                borderRight: BORDER_STYLE,
              }}></Box>
            <Box
              sx={{
                width: '100%',
                height: '100%',
                borderRight:
                  isLastChild && i === rowNode.depth - 1 ? '' : BORDER_STYLE,
              }}></Box>
          </Box>
        );
      })}
      <Box
        sx={{
          flex: `0 0 ${INSET_SPACING}px`,
          width: `${INSET_SPACING}px`,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'top',
        }}>
        {rowNode.type === 'group' ? (
          <MuiButton
            onClick={handleClick}
            tabIndex={-1}
            size="small"
            style={{
              height: '26px',
              width: '26px',
              minWidth: '26px',
              borderRadius: '50%',
              color: TREE_COLOR,
              marginTop: '8px',
            }}>
            {rowNode.childrenExpanded ? <ExpandMore /> : <KeyboardArrowRight />}
          </MuiButton>
        ) : (
          <Box
            sx={{
              width: '100%',
              height: '100%',
              pr: 2,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <Box
              sx={{
                width: '100%',
                height: '100%',
                borderBottom: BORDER_STYLE,
              }}></Box>
            <Box sx={{width: '100%', height: '100%'}}></Box>
          </Box>
        )}
      </Box>
      <CallOrCountRow>
        {isHiddenCount ? (
          <Box>{row.count.toLocaleString()} hidden calls</Box>
        ) : (
          <>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}>
              <Box
                sx={{
                  mr: 1,
                }}>
                <StatusChip value={row.status} iconOnly />
              </Box>
              <Box
                sx={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  flex: '1 1 auto',
                }}>
                {opNiceName(call.spanName)}
              </Box>
            </Box>
            {call?.rawSpan?.summary && (
              <TraceUsageStats
                usage={call.rawSpan.summary.usage}
                latency_s={call.rawSpan.summary.latency_s}
              />
            )}
          </>
        )}
        {rowTypeIndicator && <Box>{rowTypeIndicator}</Box>}
      </CallOrCountRow>
    </CursorBox>
  );

  return tooltip ? <Tooltip content={tooltip} trigger={box} /> : box;
};
