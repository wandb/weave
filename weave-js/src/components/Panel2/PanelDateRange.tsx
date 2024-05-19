import {MOON_50, MOON_800} from '@wandb/weave/common/css/color.styles';
import {
  constTimestampList,
  NodeOrVoidNode,
  opNumbersMax,
  opNumbersMin,
  voidNode,
} from '@wandb/weave/core';
import {useMutation, useNodeValue} from '@wandb/weave/react';
import React, {useCallback, useMemo} from 'react';
import styled from 'styled-components';

import {monthRoundedTime} from '../../common/util/time';
import {ValidatingTextInput} from '../ValidatingTextInput';
import * as ConfigPanel from './ConfigPanel';
import * as Panel from './panel';
import {useUpdateConfig2} from './PanelComp';

const inputType = {
  type: 'union' as const,
  members: [
    'none' as const,
    {
      type: 'list' as const,
      objectType: {
        type: 'union' as const,
        members: ['none' as const, {type: 'timestamp' as const}],
      },
    },
  ],
};
const StyledConfigOpt = styled(ConfigPanel.ConfigOption)`
  && {
    font-size: 15px;
  }
`;
StyledConfigOpt.displayName = 'StyledConfigOpt';
const StyledTextBox = styled.div`
  background-color: ${MOON_50};
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 15px;
  line-height: 20px;
  min-height: 32px;
  > div {
    width: 100%;
  }
  &&& input {
    font-family: Source Sans Pro;
    font-size: 15px;
    background-color: ${MOON_50};
    outline: none;
    color: ${MOON_800};
  }
  display: flex;
  align-content: center;
  flex-wrap: wrap;
`;
StyledTextBox.displayName = 'StyledTextBox';
interface PanelDateRangeConfig {
  domain: NodeOrVoidNode;
}
type PanelDateRangeProps = Panel.PanelProps<
  typeof inputType,
  PanelDateRangeConfig
>;

// From GPT-4
// This is the inverse of our monthRoundedTime function (except that takes seconds)
export function deltaStringToMilliseconds(timeString: string) {
  const units: {[key: string]: number} = {
    mo: 60 * 60 * 24 * 30, // month in seconds
    d: 60 * 60 * 24, // day in seconds
    h: 60 * 60, // hour in seconds
    m: 60, // minute in seconds
    s: 1, // second
  };

  let timestamp = 0;

  // matches a number followed by a unit
  const regex = /(-?\d+)(mo|d|h|m|s)/g;
  let match;

  // To track which units have been found already
  const foundUnits: {[key: string]: true} = {};

  // If its good enough for chatgpt its good enough for me!
  // tslint:disable-next-line: no-conditional-assignment
  while ((match = regex.exec(timeString)) !== null) {
    const value = parseInt(match[1], 10);
    const unit = match[2];

    if (units[unit] == null) {
      return null;
    }

    // Check for invalid inputs: negative values, or a unit appearing more than once
    if (value < 0 || foundUnits[unit]) {
      return null;
    }

    foundUnits[unit] = true;
    timestamp += value * (units[unit] || 0);
  }

  // If no matches, return null
  if (Object.keys(foundUnits).length === 0) {
    return null;
  }

  return timestamp * 1000;
}

// Forcing to U.S. format is not ideal, but in the browsers tested (Chrome, Firefox, Safari)
// the string can be parsed back into a Date object, which is not true for all locales.
//
// Will use system time zone because timeZone is not specified.
const formatterUnitedStates = new Intl.DateTimeFormat('en-US', {
  year: 'numeric', // 4-digit year
  month: 'numeric', // no leading zero
  day: 'numeric', // no leading zero
  hour: 'numeric', // no leading zero
  minute: '2-digit',
  second: '2-digit',
  // It would be nice to include a timezone indicator, but it gets truncated in the
  // varbar at the currently hardcoded width.
  // timeZoneName: 'short',
});

const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp);
  return formatterUnitedStates.format(date);
};

// Will assume the datetime is system timezone if not specified.
// Attempted to use moment with an explicit string here, but it is overly
// forgiving, and interprets some of our delta formats as dates.
const parseDateTime = (datetime: string): number => {
  return new Date(datetime).getTime();
};

export const DateEditor: React.FC<{
  timestamp: number | null;
  onCommit: (newValue: number) => void;
  allowDelta?: boolean;
  deltaDirection?: 'up' | 'down';
  deltaFromOffset?: number | null;
}> = props => {
  const {timestamp} = props;
  const allowDelta = props.allowDelta && props.deltaFromOffset != null;
  const dateS = timestamp == null ? 'none' : formatTime(timestamp);
  return (
    <ValidatingTextInput
      key={dateS}
      initialValue={dateS}
      dataTest={''}
      onCommit={(newValue: string) => {
        if (!isNaN(parseDateTime(newValue))) {
          props.onCommit(parseDateTime(newValue));
        } else if (allowDelta && props.deltaFromOffset != null) {
          const delta = deltaStringToMilliseconds(newValue);
          if (delta != null) {
            const newTimestamp =
              props.deltaDirection === 'up'
                ? props.deltaFromOffset + delta
                : props.deltaFromOffset - delta;
            props.onCommit(newTimestamp);
            return;
          }
        }
      }}
      validateInput={(value: string) => {
        if (!isNaN(new Date(value).getTime())) {
          return true;
        }
        if (allowDelta) {
          const delta = deltaStringToMilliseconds(value);
          if (delta != null) {
            return true;
          }
        }
        return false;
      }}
    />
  );
};

export function initializedPanelDateRange(): PanelDateRangeConfig {
  return {
    domain: voidNode(),
  };
}

export const PanelDateRangeConfigComponent: React.FC<
  PanelDateRangeProps
> = props => {
  const updateConfig2 = useUpdateConfig2(props);
  const config = props.config!;

  const updateDomain = useCallback(
    async (newExpr: NodeOrVoidNode) => {
      updateConfig2(oldConfig => {
        return {
          ...oldConfig,
          domain: newExpr,
        };
      });
    },
    [updateConfig2]
  );

  return (
    <>
      <StyledConfigOpt label={`domain`}>
        <ConfigPanel.ExpressionConfigField
          expr={config.domain}
          setExpression={updateDomain}
        />
      </StyledConfigOpt>
    </>
  );
};

export const PanelDateRange: React.FC<PanelDateRangeProps> = props => {
  const config = props.config!;
  const valueNode = props.input;
  const valueQuery = useNodeValue(valueNode as any);
  const setVal = useMutation(valueNode, 'set');

  const domainMin = useMemo(() => {
    return config.domain.nodeType === 'void'
      ? voidNode()
      : opNumbersMin({numbers: config.domain});
  }, [config.domain]);
  const domainMax = useMemo(() => {
    return config.domain.nodeType === 'void'
      ? voidNode()
      : opNumbersMax({numbers: config.domain});
  }, [config.domain]);

  const domainMinQuery = useNodeValue(domainMin);
  const domainMaxQuery = useNodeValue(domainMax);

  const {start, end} = useMemo(() => {
    if (valueQuery.result != null) {
      return {start: valueQuery.result[0], end: valueQuery.result[1]};
    }
    return {
      start: domainMinQuery.result,
      end: domainMaxQuery.result,
    };
  }, [domainMaxQuery.result, domainMinQuery.result, valueQuery.result]);

  const updateStart = useCallback(
    (newStart: number) => {
      setVal({val: constTimestampList([newStart, end])});
    },
    [end, setVal]
  );
  const updateEnd = useCallback(
    (newEnd: number) => {
      setVal({val: constTimestampList([start, newEnd])});
    },
    [setVal, start]
  );

  const durationMillis = useMemo(() => {
    if (end == null || start == null) {
      return null;
    }
    return end - start;
  }, [end, start]);

  return (
    <div
      style={{
        height: '100%',
        padding: '0 16px',
        display: 'flex',
        flexDirection: 'column',
      }}>
      <StyledConfigOpt label="Start">
        <StyledTextBox>
          <DateEditor
            timestamp={start}
            onCommit={updateStart}
            allowDelta={true}
            deltaDirection="down"
            deltaFromOffset={end}
          />
        </StyledTextBox>
      </StyledConfigOpt>
      <StyledConfigOpt label="End">
        <StyledTextBox>
          <DateEditor
            timestamp={end}
            onCommit={updateEnd}
            allowDelta={true}
            deltaDirection="up"
            deltaFromOffset={start}
          />
        </StyledTextBox>
      </StyledConfigOpt>
      <StyledConfigOpt label="Duration">
        <StyledTextBox>
          {durationMillis != null
            ? monthRoundedTime(durationMillis / 1000) || 'N/A'
            : 'N/A'}
        </StyledTextBox>
      </StyledConfigOpt>
    </div>
  );
};

export const Spec: Panel.PanelSpec = {
  hidden: true,
  id: 'DateRange',
  icon: 'date',
  initialize: initializedPanelDateRange,
  ConfigComponent: PanelDateRangeConfigComponent,
  Component: PanelDateRange,
  inputType,
};
