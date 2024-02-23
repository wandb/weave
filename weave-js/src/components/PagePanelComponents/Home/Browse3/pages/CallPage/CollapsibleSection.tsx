import {Collapse} from '@mui/material';
import React, {useState} from 'react';
import styled from 'styled-components';

import {Button} from '../../../../../Button';

type CollapsibleSectionProps = {
  headerTitle: string;
  children: React.ReactNode;
};

const Header = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;

  font-family: Source Sans Pro;
  font-size: 16px;
  font-weight: 600;
  line-height: 32px;
  letter-spacing: 0px;
  text-align: left;
`;
Header.displayName = 'S.Header';

const HeaderTitle = styled.div`
  cursor: pointer;
`;
HeaderTitle.displayName = 'S.HeaderTitle';

export const CollapsibleSection = ({
  headerTitle,
  children,
}: CollapsibleSectionProps) => {
  const [open, setOpen] = useState(true);
  const onClick = () => {
    setOpen(!open);
  };
  const icon = open ? 'chevron-down' : 'chevron-next';
  return (
    <>
      <Header>
        <Button size="small" icon={icon} variant="ghost" onClick={onClick} />
        <HeaderTitle onClick={onClick}>{headerTitle}</HeaderTitle>
      </Header>
      <Collapse in={open}>{children}</Collapse>
    </>
  );
};
