/**
 * This is the component used to render the left-most "tree" part of the grid,
 * handling indentation and expansion.
 */

import {Box, BoxProps} from '@mui/material';
import {GridRenderCellParams, useGridApiContext} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, MouseEvent} from 'react';

import {GOLD_400, MOON_600} from '../../../../../common/css/color.styles';
import {Button} from '../../../../Button';
import {Tooltip} from '../../../../Tooltip';
import {CursorBox} from '../pages/CallPage/CursorBox';
import {UNCHANGED} from './compare';

const INSET_SPACING = 32;

export const CompareGridGroupingCell: FC<
  GridRenderCellParams & {onClick?: (event: MouseEvent) => void}
> = props => {
  const {id, field, rowNode, row} = props;
  const isGroup = rowNode.type === 'group';
  const hasExpandableRefs = row.expandableRefs.length > 0;
  const isExpandable = (isGroup || hasExpandableRefs) && !row.isCode;
  const apiRef = useGridApiContext();
  const onClick: BoxProps['onClick'] = event => {
    if (isGroup) {
      apiRef.current.setRowChildrenExpansion(id, !rowNode.childrenExpanded);
      apiRef.current.setCellFocus(id, field);
    }

    if (props.onClick) {
      props.onClick(event);
    }

    event.stopPropagation();
  };

  const tooltipContent = row.path ? row.path.toString() : undefined;
  const box = (
    <CursorBox
      $isClickable={isExpandable}
      onClick={onClick}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'left',
        width: '100%',
        borderLeft:
          `3px solid ` +
          (row.changeType !== UNCHANGED ? GOLD_400 : 'transparent'),
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
            }}
          />
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
          justifyContent: 'center',
        }}>
        {isExpandable ? (
          <Button
            variant="ghost"
            icon={
              isGroup && rowNode.childrenExpanded
                ? 'chevron-down'
                : 'chevron-next'
            }
          />
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
              }}></Box>
            <Box sx={{width: '100%', height: '100%'}}></Box>
          </Box>
        )}
      </Box>
      <Tooltip
        content={tooltipContent}
        trigger={
          <Box
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              flex: '1 1 auto',
              color: MOON_600,
            }}>
            {props.value}
          </Box>
        }
      />
    </CursorBox>
  );

  return box;
};
