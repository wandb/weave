/**
 * A vertically split panel with a draggable divider and the ability
 * to collapse the left panel.
 */

import Collapse from '@mui/material/Collapse';
import {hexToRGB, MOON_250} from '@wandb/weave/common/css/globals.styles';
import React, {ReactNode, useCallback, useRef, useState} from 'react';
import styled from 'styled-components';

type SplitPanelProps = {
  drawer?: ReactNode;
  main: ReactNode;
  isDrawerOpen: boolean;
  minWidth?: number;
};

const Divider = styled.span`
  background-color: ${MOON_250};
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  background-clip: padding-box;
  cursor: col-resize;
  flex: 0 0 9px;
  transition: border 1s ease;
  transition-delay: 0.5s;

  &:hover {
    border-left-color: ${hexToRGB(MOON_250, 0.5)};
    border-right-color: ${hexToRGB(MOON_250, 0.5)};
  }
`;
Divider.displayName = 'S.Divider';

export const SplitPanel = ({
  main,
  drawer,
  isDrawerOpen,
  minWidth,
}: SplitPanelProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(200);
  const [isDragging, setIsDragging] = useState(false);

  const onMouseDown = useCallback(() => {
    setIsDragging(true);
  }, [setIsDragging]);
  const onMouseUp = useCallback(() => {
    setIsDragging(false);
  }, [setIsDragging]);
  const onMouseLeave = useCallback(() => {
    setIsDragging(false);
  }, [setIsDragging]);
  const onMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      const panel = e.target as HTMLElement;
      if (panel.nodeName !== 'DIV') {
        return;
      }
      const bounds = panel.getBoundingClientRect();
      const x = e.clientX - bounds.left;
      if (minWidth && x < minWidth) {
        return;
      }
      setWidth(x);
    }
  };

  const cursor = isDragging ? 'col-resize' : undefined;
  const pointerEvents = isDragging ? 'none' : 'auto';
  const userSelect = isDragging ? 'none' : 'auto';
  return (
    <div
      className="splitpanel"
      ref={ref}
      style={{width: '100%', height: '100%', display: 'flex', cursor}}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseLeave}>
      {isDrawerOpen && (
        <>
          <Collapse
            in={isDrawerOpen}
            orientation="horizontal"
            style={{
              alignSelf: 'stretch',
              flex: `0 0 ${width}px`,
              overflow: 'auto',
              pointerEvents,
              userSelect,
            }}>
            <div style={{width, height: '100%'}}>{drawer}</div>
          </Collapse>
          <Divider className="divider" onMouseDown={onMouseDown} />
        </>
      )}
      <div
        className="right"
        style={{flex: '1 1 auto', pointerEvents, userSelect}}>
        {main}
      </div>
    </div>
  );
};
