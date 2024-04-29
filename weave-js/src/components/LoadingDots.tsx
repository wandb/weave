/**
 * A subtle loading indicator for use in cases like Table cells.
 */

import React from 'react';
import styled from 'styled-components';

import * as Colors from '../common/css/color.styles';

const DotsContainer = styled.div`
  display: inline-flex;
  vertical-align: middle;
  align-items: center;
  padding: 0 4px;

  @keyframes fade {
    from {
      opacity: 0.2;
    }
    to {
      opacity: 1;
    }
  }
`;
DotsContainer.displayName = 'S.DotsContainer';

type DotProps = {
  marginLeft?: number;
  animationDelay?: string;
};

const Dot = styled.span<DotProps>`
  height: 4px;
  width: 4px;
  background-color: ${Colors.MOON_200};
  border-radius: 50%;
  display: inline-block;
  animation-name: fade;
  animation-duration: 1.4s;
  animation-iteration-count: infinite;
  animation-timing-function: ease-in-out;
  animation-direction: alternate;
  margin-left: ${props => (props.marginLeft ?? 0) + 'px'};
  animation-delay: ${props => props.animationDelay};
`;
Dot.displayName = 'S.Dot';

export const LoadingDots: React.FC = () => {
  return (
    <DotsContainer>
      <Dot />
      <Dot marginLeft={4} animationDelay="0.2s" />
      <Dot marginLeft={4} animationDelay="0.4s" />
    </DotsContainer>
  );
};
