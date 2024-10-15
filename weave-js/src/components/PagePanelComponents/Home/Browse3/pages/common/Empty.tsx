/**
 * This component is used when we have no content to show.
 */

import React from 'react';
import styled from 'styled-components';

import * as Colors from '../../../../../../common/css/color.styles';
import {hexToRGB} from '../../../../../../common/css/utils';
import {Icon, IconName} from '../../../../../Icon';

type EmptySize = 'small' | 'medium';

export type EmptyProps = {
  icon: IconName;
  heading: string;
  description: string;
  moreInformation: React.ReactNode;
  size?: EmptySize;
};

const Container = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
`;
Container.displayName = 'S.Container';

const Content = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 600px;
`;
Content.displayName = 'S.Content';

const Circle = styled.div<{size: EmptySize}>`
  border-radius: 50%;
  width: ${props => (props.size === 'small' ? '60px' : '80px')};
  height: ${props => (props.size === 'small' ? '60px' : '80px')};
  background-color: ${hexToRGB(Colors.TEAL_300, 0.48)};
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
`;
Circle.displayName = 'S.Circle';

const CircleIcon = styled(Icon)<{size: EmptySize}>`
  width: ${props => (props.size === 'small' ? '25px' : '33px')};
  height: ${props => (props.size === 'small' ? '25px' : '33px')};
  color: ${Colors.TEAL_600};
`;
CircleIcon.displayName = 'S.CircleIcon';

const Heading = styled.div<{size: EmptySize}>`
  font-family: Source Sans Pro;
  font-size: ${props => (props.size === 'small' ? '20px' : '24px')};
  font-weight: 600;
  line-height: 32px;
  text-align: left;
  color: ${Colors.MOON_950};
  margin-bottom: 8px;
`;
Heading.displayName = 'S.Heading';

const Description = styled.div<{size: EmptySize}>`
  font-family: Source Sans Pro;
  font-size: ${props => (props.size === 'small' ? '14px' : '18px')};
  font-weight: 400;
  line-height: 25.2px;
  text-align: center;
  color: ${Colors.MOON_750};
  margin-bottom: 8px;
`;
Description.displayName = 'S.Description';

const MoreInformation = styled.div<{size: EmptySize}>`
  font-family: Source Sans Pro;
  font-size: ${props => (props.size === 'small' ? '14px' : '16px')};
  font-weight: 400;
  line-height: 22.4px;
  text-align: center;
  color: ${Colors.MOON_500};
`;
MoreInformation.displayName = 'S.MoreInformation';

export const Empty = ({
  icon,
  heading,
  description,
  moreInformation,
  size = 'medium',
}: EmptyProps) => {
  return (
    <Container>
      <Content>
        <Circle size={size}>
          <CircleIcon size={size} name={icon} />
        </Circle>
        <Heading size={size}>{heading}</Heading>
        <Description size={size}>{description}</Description>
        <MoreInformation size={size}>{moreInformation}</MoreInformation>
      </Content>
    </Container>
  );
};
