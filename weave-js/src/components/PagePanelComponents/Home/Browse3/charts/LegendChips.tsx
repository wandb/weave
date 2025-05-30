import React from 'react';

import {useChartsDispatch, useChartsState} from './ChartsContext';

const CHIP_HEIGHT = 18;
const CHIP_BORDER_WIDTH = 2;

interface LegendChipProps {
  group: string;
  color: string;
  onHover?: (group: string | null) => void;
  isHighlighted?: boolean;
}

// Component for global state usage
const GlobalLegendChip = React.memo(
  ({group, color}: {group: string; color: string}) => {
    const dispatch = useChartsDispatch();
    const {hoveredGroup} = useChartsState();
    const isHighlighted = hoveredGroup === group;

    return (
      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          boxSizing: 'border-box',
          border: `${CHIP_BORDER_WIDTH}px solid ${
            isHighlighted ? color : 'transparent'
          }`,
          outline: isHighlighted ? 'none' : '1px solid #e0e0e0',
          outlineOffset: -1,
          borderRadius: 8,
          padding: '0 6px 0 2px',
          fontSize: 10,
          fontWeight: isHighlighted ? 600 : 500,
          margin: '0 4px 0 0',
          height: CHIP_HEIGHT,
          lineHeight: `${CHIP_HEIGHT - 2 * CHIP_BORDER_WIDTH}px`,
          whiteSpace: 'nowrap',
          maxWidth: 140,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          background: isHighlighted ? `${color}15` : 'white',
          flexShrink: 0,
          cursor: 'pointer',
          transition: 'all 0.1s ease-in-out',
        }}
        onMouseEnter={() => dispatch({type: 'SET_HOVERED_GROUP', group})}
        onMouseLeave={() => dispatch({type: 'SET_HOVERED_GROUP', group: null})}>
        <span
          style={{
            width: 8,
            height: 8,
            background: color,
            display: 'inline-block',
            borderRadius: 4,
            marginRight: 4,
            flex: '0 0 auto',
          }}
        />
        <span style={{overflow: 'hidden', textOverflow: 'ellipsis'}}>
          {group}
        </span>
      </span>
    );
  }
);

// Component for local state usage
const LocalLegendChip = React.memo(
  ({
    group,
    color,
    onHover,
    isHighlighted,
  }: {
    group: string;
    color: string;
    onHover: (group: string | null) => void;
    isHighlighted: boolean;
  }) => {
    return (
      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          boxSizing: 'border-box',
          border: `${CHIP_BORDER_WIDTH}px solid ${
            isHighlighted ? color : 'transparent'
          }`,
          outline: isHighlighted ? 'none' : '1px solid #e0e0e0',
          outlineOffset: -1,
          borderRadius: 8,
          padding: '0 6px 0 2px',
          fontSize: 10,
          fontWeight: isHighlighted ? 600 : 500,
          margin: '0 4px 0 0',
          height: CHIP_HEIGHT,
          lineHeight: `${CHIP_HEIGHT - 2 * CHIP_BORDER_WIDTH}px`,
          whiteSpace: 'nowrap',
          maxWidth: 140,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          background: isHighlighted ? `${color}15` : 'white',
          flexShrink: 0,
          cursor: 'pointer',
          transition: 'all 0.1s ease-in-out',
        }}
        onMouseEnter={() => onHover(group)}
        onMouseLeave={() => onHover(null)}>
        <span
          style={{
            width: 8,
            height: 8,
            background: color,
            display: 'inline-block',
            borderRadius: 4,
            marginRight: 4,
            flex: '0 0 auto',
          }}
        />
        <span style={{overflow: 'hidden', textOverflow: 'ellipsis'}}>
          {group}
        </span>
      </span>
    );
  }
);

// Factory component to choose the right implementation
export const LegendChip = React.memo(
  ({group, color, onHover, isHighlighted}: LegendChipProps) => {
    if (onHover) {
      return (
        <LocalLegendChip
          group={group}
          color={color}
          onHover={onHover}
          isHighlighted={isHighlighted ?? false}
        />
      );
    } else {
      return <GlobalLegendChip group={group} color={color} />;
    }
  }
);

interface LegendChipsProps {
  groupValues: string[];
  groupColor: (group: string) => string;
  onHover?: (group: string | null) => void;
  hoveredGroup?: string | null;
}

export const LegendChips: React.FC<LegendChipsProps> = ({
  groupValues,
  groupColor,
  onHover,
  hoveredGroup,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'flex-start',
        justifyContent: 'center',
        gap: 4,
        padding: '2px 8px',
        width: '100%',
        maxWidth: '100%',
        minHeight: CHIP_HEIGHT + 4,
        overflowX: 'hidden',
        overflowY: 'auto',
        position: 'relative',
        zIndex: 1,
        boxSizing: 'border-box',
      }}>
      {groupValues.map(group => (
        <LegendChip
          key={group}
          group={group}
          color={groupColor(group)}
          onHover={onHover}
          isHighlighted={hoveredGroup === group}
        />
      ))}
    </div>
  );
};
