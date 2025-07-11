import {Box, BoxProps} from '@mui/material';
import {GridRenderCellParams, useGridApiContext} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, MouseEvent} from 'react';

import {Button} from '../../../../../Button';
import {Tooltip} from '../../../../../Tooltip';
import {CursorBox} from './CursorBox';
import {maybeGetDeletedRefValuePlaceholderFromRow} from './ObjectViewer';

const DEFAULT_INSET_SPACING = 40;

/**
 * Utility component for the ObjectViewer to allow expanding/collapsing of keys.
 */
export const ObjectViewerGroupingCell: FC<
  GridRenderCellParams & {
    insetSpacing?: number;
    onClick?: (event: MouseEvent) => void;
  }
> = props => {
  const {id, field, rowNode, row} = props;
  const insetSpacing = props.insetSpacing ?? DEFAULT_INSET_SPACING;
  const isGroup = rowNode.type === 'group';
  const isExpandableRef = row.isExpandableRef;
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

  const deletedRef = maybeGetDeletedRefValuePlaceholderFromRow(row);
  const tooltipContent = row.path.toString();
  const textContent = deletedRef ?? props.value;
  const box = (
    <CursorBox
      $isClickable={isGroup || isExpandableRef}
      onClick={onClick}
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
              flex: `0 0 ${insetSpacing / 2}px`,
              width: `${insetSpacing / 2}px`,
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
          flex: `0 0 ${insetSpacing}px`,
          width: `${insetSpacing}px`,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
        {isGroup || isExpandableRef ? (
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
              textDecoration: deletedRef ? 'line-through' : 'none',
            }}>
            {textContent}
          </Box>
        }
      />
    </CursorBox>
  );

  return box;
};
