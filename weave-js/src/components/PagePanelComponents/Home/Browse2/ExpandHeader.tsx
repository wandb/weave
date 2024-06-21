/**
 * A datagrid column header that has an extra button to expand the column.
 */
import React from 'react';
import styled from 'styled-components';

import {Button} from '../../../Button';
import {Tooltip} from '../../../Tooltip';

type ExpandHeaderProps = {
  headerName: string;
  field: string;
  hasExpand: boolean;
  onExpand: (col: string) => void;
};

export const Header = styled.div`
  display: flex;
  align-items: center;
  font-weight: 600;
`;
Header.displayName = 'S.Header';

export const ExpandHeader = ({
  headerName,
  field,
  hasExpand,
  onExpand,
}: ExpandHeaderProps) => {
  const onClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onExpand(field);
  };
  return (
    <Header>
      <Tooltip trigger={<div>{headerName}</div>} content={field} />
      {hasExpand && (
        <Tooltip
          content="Expand refs"
          trigger={
            <Button
              className="ml-4"
              variant="quiet"
              size="small"
              icon="chevron-next"
              onClick={onClick}
            />
          }
        />
      )}
    </Header>
  );
};
