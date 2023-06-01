import {constStringList, Node} from '@wandb/weave/core';
import React, {useMemo, useState} from 'react';

import * as CGReact from '../../react';

const HOVER_COLOR = '#00879d';
const ACTIVE_COLOR = '#6ba6fa';

export const Tabs: React.FC<{
  input: Node;
  activeIndex: number;
  setActiveIndex: (newActiveIndex: number) => void;
}> = props => {
  const {input, activeIndex, setActiveIndex} = props;
  const tabNamesQuery = CGReact.useNodeValue(input);
  const tabNames = useMemo(() => {
    return tabNamesQuery.result ?? ['loading...'];
  }, [tabNamesQuery.result]);
  const [hoveringIndex, setHoveringIndex] = useState<number | null>(null);

  return (
    <div
      style={{
        display: 'flex',
        width: '100%',
        overflowX: 'auto',
        flex: '0 0 auto',
      }}
      onMouseLeave={() => setHoveringIndex(null)}>
      {tabNames.map((name: string, i: number) => (
        <div
          key={i}
          style={{
            flexShrink: 0,
            margin: '0 5px 4px',
            minWidth: 50,
            maxWidth: 100,
            display: 'flex',
            justifyContent: 'center',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            cursor: 'pointer',
            color:
              hoveringIndex === i
                ? HOVER_COLOR
                : activeIndex === i
                ? ACTIVE_COLOR
                : undefined,
            borderBottom:
              hoveringIndex === i
                ? `2px solid ${HOVER_COLOR}`
                : activeIndex === i
                ? `2px solid ${ACTIVE_COLOR}`
                : '2px solid #aaa',
          }}
          onMouseEnter={() => setHoveringIndex(i)}
          onClick={() => setActiveIndex(i)}>
          <div>{name}</div>
        </div>
      ))}
    </div>
  );
};

export const LayoutTabs: React.FC<{
  tabNames: string[];
  renderPanel: (panel: {id: string}) => React.ReactNode;
}> = props => {
  const [activeIndex, setActiveIndex] = useState(0);
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}>
      <Tabs
        input={constStringList(props.tabNames)}
        activeIndex={activeIndex}
        setActiveIndex={setActiveIndex}
      />
      <div
        style={{
          flex: '1 1 auto',
          overflow: 'hidden',
        }}>
        {props.renderPanel({id: props.tabNames[activeIndex]})}
      </div>
    </div>
  );
};
