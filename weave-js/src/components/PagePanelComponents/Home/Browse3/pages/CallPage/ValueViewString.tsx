import React from 'react';
import styled from 'styled-components';

type ValueViewStringProps = {
  value: string;
  isExpanded: boolean;
};

const Collapsed = styled.div`
  min-height: 38px;
  line-height: 38px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;
Collapsed.displayName = 'S.Collapsed';

const Expanded = styled.div`
  min-height: 38px;
  max-height: 300px;
  display: flex;
  align-items: center;
  overflow: auto;
  white-space: break-spaces;
`;
Expanded.displayName = 'S.Expanded';

const ExpandedInner = styled.div`
  max-height: 300px;
`;
ExpandedInner.displayName = 'S.ExpandedInner';

export const ValueViewString = ({value, isExpanded}: ValueViewStringProps) => {
  if (isExpanded) {
    return (
      <Expanded>
        <ExpandedInner>{value}</ExpandedInner>
      </Expanded>
    );
  }
  return <Collapsed>{value}</Collapsed>;
};
