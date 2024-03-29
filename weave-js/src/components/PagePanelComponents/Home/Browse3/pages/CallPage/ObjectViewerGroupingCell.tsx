import {Box, ButtonProps} from '@mui/material';
import {GridRenderCellParams, useGridApiContext} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, MouseEvent} from 'react';

import {Button} from '../../../../../Button';
import {Tooltip} from '../../../../../Tooltip';
import {CursorBox} from './CursorBox';

const INSET_SPACING = 40;

/**
 * Utility component for the ObjectViewer to allow expanding/collapsing of keys.
 */
export const ObjectViewerGroupingCell: FC<
  GridRenderCellParams & {onClick?: (event: MouseEvent) => void}
> = props => {
  const {id, field, rowNode, row} = props;
  const isGroup = rowNode.type === 'group';
  const apiRef = useGridApiContext();
  const onClick: ButtonProps['onClick'] = event => {
    if (!isGroup) {
      return;
    }

    apiRef.current.setRowChildrenExpansion(id, !rowNode.childrenExpanded);
    apiRef.current.setCellFocus(id, field);

    if (props.onClick) {
      props.onClick(event);
    }

    event.stopPropagation();
  };

  const tooltipContent = row.path.toString();
  const box = (
    <CursorBox
      $isClickable={isGroup}
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
        {rowNode.type === 'group' ? (
          <Button
            variant="quiet"
            icon={rowNode.childrenExpanded ? 'chevron-down' : 'chevron-next'}
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
            }}>
            {props.value}
          </Box>
        }
      />
    </CursorBox>
  );

  return box;
};
