import {Popover} from '@mui/material';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import copyToClipboard from 'copy-to-clipboard';
import _ from 'lodash';
import moment from 'moment';
import React, {ReactNode, useCallback, useRef} from 'react';
import TimeAgo, {Formatter} from 'react-timeago';
import styled from 'styled-components';

import {toast} from '../../../../common/components/elements/Toast';
import * as Colors from '../../../../common/css/color.styles';
import {Button} from '../../../Button';
import {
  DraggableGrow,
  DraggableHandle,
  PoppedBody,
  StyledTooltip,
  TooltipHint,
} from '../../../DraggablePopups';
import {Icon} from '../../../Icon';
import {formatTimestamp} from '../../../Timestamp';

type CellValueTimestampProps = {
  value: string;
};

const Collapsed = styled.div`
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
`;
Collapsed.displayName = 'S.Collapsed';

const TooltipContent = styled.div`
  display: flex;
  flex-direction: column;
`;
TooltipContent.displayName = 'S.TooltipContent';

const TooltipText = styled.div`
  max-height: 35vh;
  overflow: auto;
  white-space: break-spaces;
`;
TooltipText.displayName = 'S.TooltipText';

const Popped = styled.div`
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 0.8rem;
  word-wrap: break-word;
  background-color: #fff;
  color: ${Colors.MOON_700};
  border: 1px solid ${Colors.MOON_300};
`;
Popped.displayName = 'S.Popped';

const Toolbar = styled.div`
  display: flex;
  align-items: center;
  padding: 4px 0;
`;
Toolbar.displayName = 'S.Toolbar';

const Spacer = styled.div`
  flex: 1 1 auto;
`;
Spacer.displayName = 'S.Spacer';

// See: https://www.npmjs.com/package/react-timeago#formatter-optional
const TIMEAGO_FORMATTER: Formatter = (
  value,
  unit,
  suffix,
  epochSeconds,
  nextFormatter
) =>
  unit === 'second'
    ? 'just now'
    : nextFormatter!(value, unit, suffix, epochSeconds);

type TableRowProps = {
  label: string;
  value: string | ReactNode;
  allowCopy: boolean;
  onCopy?: (text: string) => void;
};

const TableRow = ({label, value, allowCopy, onCopy}: TableRowProps) => {
  return (
    <tr className="group">
      <th className="pr-4 text-right">{label}</th>
      <td>{value}</td>
      {allowCopy && onCopy && _.isString(value) && (
        <td className="pl-2">
          <Button
            size="small"
            variant="ghost"
            icon="copy"
            tooltip="Copy to clipboard"
            className="invisible group-hover:visible"
            onClick={e => {
              e.stopPropagation();
              onCopy(value);
            }}
          />
        </td>
      )}
    </tr>
  );
};

type FormatsTableProps = {
  value: string;
  allowCopy?: boolean;
};

const FormatsTable = ({value, allowCopy = false}: FormatsTableProps) => {
  const then = moment(value);
  const asLong = then.format('dddd, MMMM Do YYYY [at] h:mm:ss a Z');
  const asIso = new Date(value).toISOString();
  const asUnix = new Date(value).getTime() / 1000;

  const onCopy = useCallback((text: string) => {
    copyToClipboard(text);
    toast('Copied to clipboard');
  }, []);

  return (
    <Tailwind>
      <TooltipText>
        <table className="w-full border-collapse">
          <tbody>
            <TableRow
              label="Long"
              value={asLong}
              allowCopy={allowCopy}
              onCopy={onCopy}
            />
            <TableRow
              label="ISO"
              value={asIso}
              allowCopy={allowCopy}
              onCopy={onCopy}
            />
            <TableRow
              label="Relative"
              value={
                <TimeAgo
                  title="" // Suppress the default tooltip
                  minPeriod={10}
                  formatter={TIMEAGO_FORMATTER}
                  date={then.format('YYYY-MM-DDTHH:mm:ssZ')}
                  live={true}
                />
              }
              allowCopy={false}
            />
            <TableRow
              label="Unix seconds"
              value={asUnix.toString()}
              allowCopy={allowCopy}
              onCopy={onCopy}
            />
          </tbody>
        </table>
      </TooltipText>
    </Tailwind>
  );
};

export const CellValueTimestamp = ({value}: CellValueTimestampProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
  };

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  const trimmed = value.trim();

  const title = open ? (
    '' // Suppress tooltip when popper is open.
  ) : (
    <TooltipContent onClick={onClick}>
      <FormatsTable value={trimmed} />
      <TooltipHint>Click for more details</TooltipHint>
    </TooltipContent>
  );

  // Unfortunate but necessary to get appear on top of peek drawer.
  const stylePopper = {zIndex: 1};

  const formatted = formatTimestamp(trimmed);

  return (
    <>
      <StyledTooltip enterDelay={500} title={title}>
        <Collapsed ref={ref} onClick={onClick}>
          <Tailwind>
            <div className="flex items-center gap-4">
              <div className="flex h-[22px] w-[22px] flex-none items-center justify-center rounded-full bg-moon-300/[0.48]">
                <Icon
                  role="presentation"
                  className="h-[14px] w-[14px]"
                  name="recent-clock"
                />
              </div>
              {formatted.short}
            </div>
          </Tailwind>
        </Collapsed>
      </StyledTooltip>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        style={stylePopper}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
        onClose={() => setAnchorEl(null)}
        TransitionComponent={DraggableGrow}>
        <Popped>
          <TooltipContent>
            <DraggableHandle>
              <Toolbar>
                <div>
                  <b>Python datetime.datetime object</b>
                </div>
                <Spacer />
                <Button
                  size="small"
                  variant="ghost"
                  icon="close"
                  tooltip="Close preview"
                  onClick={e => {
                    e.stopPropagation();
                    setAnchorEl(null);
                  }}
                />
              </Toolbar>
            </DraggableHandle>
            <PoppedBody>
              <FormatsTable value={trimmed} allowCopy={true} />
            </PoppedBody>
          </TooltipContent>
        </Popped>
      </Popover>
    </>
  );
};
