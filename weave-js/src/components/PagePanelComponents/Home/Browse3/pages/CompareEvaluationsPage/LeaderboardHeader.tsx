import React from 'react';
import styled from 'styled-components';

interface LeaderboardHeaderProps {
  title: string;
}

export const LeaderboardHeader: React.FC<LeaderboardHeaderProps> = ({
  title,
}) => (
  <HeaderContainer>
    <Title>{title}</Title>
  </HeaderContainer>
);

const HeaderContainer = styled.div`
  background-color: #2c3e50;
  color: white;
  padding: 24px;
  border-radius: 8px;
`;

const Title = styled.h1`
  margin: 0;
  font-size: 28px;
`;
