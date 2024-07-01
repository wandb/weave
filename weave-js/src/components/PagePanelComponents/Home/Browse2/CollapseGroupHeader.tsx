/**
 * A datagrid group column header that can be collapsed.
 */
import React from 'react';
import styled from 'styled-components';

import {Button} from '../../../Button';
import {Tooltip} from '../../../Tooltip';

type CollapseGroupHeaderProps = {
  headerName: string;
  field: string;
  onCollapse: (col: string) => void;
};

export const Header = styled.div`
  display: flex;
  align-items: center;
  font-weight: 600;
`;
Header.displayName = 'S.Header';

export const CollapseHeader = ({
  headerName,
  field,
  onCollapse,
}: CollapseGroupHeaderProps) => {
  const onClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCollapse(field);
  };
  return (
    <Header>
      <Tooltip trigger={<div>{headerName}</div>} content={field} />
      <Tooltip
        content="Collapse refs"
        trigger={
          <Button
            className="ml-4"
            variant="quiet"
            size="small"
            icon="chevron-back"
            onClick={onClick}
          />
        }
      />
    </Header>
  );
};
