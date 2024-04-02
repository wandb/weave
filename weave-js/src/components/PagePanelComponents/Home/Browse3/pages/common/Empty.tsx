/**
 * This component is used when we have no content to show.
 */

import React from 'react';
import styled from 'styled-components';

import * as Colors from '../../../../../../common/css/color.styles';
import {hexToRGB} from '../../../../../../common/css/utils';
import {Icon, IconName} from '../../../../../Icon';

export type EmptyProps = {
  icon: IconName;
  heading: string;
  description: string;
  moreInformation: React.ReactNode;
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

const Circle = styled.div`
  border-radius: 50%;
  width: 80px;
  height: 80px;
  background-color: ${hexToRGB(Colors.TEAL_300, 0.48)};
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
`;
Circle.displayName = 'S.Circle';

const CircleIcon = styled(Icon)`
  width: 33px;
  height: 33px;
  color: ${Colors.TEAL_600};
`;
CircleIcon.displayName = 'S.CircleIcon';

const Heading = styled.div`
  font-family: Source Sans Pro;
  font-size: 24px;
  font-weight: 600;
  line-height: 32px;
  text-align: left;
  color: ${Colors.MOON_950};
  margin-bottom: 8px;
`;
Heading.displayName = 'S.Heading';

const Description = styled.div`
  font-family: Source Sans Pro;
  font-size: 18px;
  font-weight: 400;
  line-height: 25.2px;
  text-align: center;
  color: ${Colors.MOON_750};
  margin-bottom: 8px;
`;
Description.displayName = 'S.Description';

const MoreInformation = styled.div`
  font-family: Source Sans Pro;
  font-size: 16px;
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
}: EmptyProps) => {
  return (
    <Container>
      <Content>
        <Circle>
          <CircleIcon name={icon} />
        </Circle>
        <Heading>{heading}</Heading>
        <Description>{description}</Description>
        <MoreInformation>{moreInformation}</MoreInformation>
      </Content>
    </Container>
  );
};
