import {Box} from '@mui/material';
import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {FC} from 'react';

import {Span} from './callTree';
import {CallViewSmall} from './CallViewSmall';

export type SpanWithChildren = Span & {child_spans: SpanWithChildren[]};
export const SpanTreeNode: FC<{
  level?: number;
  call: SpanWithChildren;
  selectedSpanId?: string;
  setSelectedSpanId: (spanId: string) => void;
}> = ({call, selectedSpanId, setSelectedSpanId, level}) => {
  const isSelected = selectedSpanId === call.span_id;
  const curLevel = level ?? 0;
  const childLevel = curLevel + 1;
  return (
    <>
      <Box
        ml={-1}
        pl={1 + curLevel * 2}
        mr={-1}
        pr={1}
        sx={{
          '& *:hover': {
            backgroundColor: globals.lightSky,
          },
          backgroundColor: isSelected ? globals.sky : 'inherit',
        }}>
        <CallViewSmall
          call={call}
          onClick={() => setSelectedSpanId(call.span_id)}
        />
      </Box>
      {call.child_spans.map(child => (
        <SpanTreeNode
          key={child.span_id}
          level={childLevel}
          call={child}
          selectedSpanId={selectedSpanId}
          setSelectedSpanId={setSelectedSpanId}
        />
      ))}
    </>
  );
};
