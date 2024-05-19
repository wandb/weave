/**
 * Panel shown as body of Boards tab in table preview sidebar when
 * nothing has used the table yet.
 */

import * as globals from '@wandb/weave/common/css/globals.styles';
import {hexToRGB} from '@wandb/weave/common/css/globals.styles';
import React from 'react';
import styled from 'styled-components';

import {Button} from '../../Button';
import {IconDashboardBlackboard} from '../../Icon';

const Wrapper = styled.div`
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
`;
Wrapper.displayName = 'S.Wrapper';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: 0 16px 32px 16px;
`;
Container.displayName = 'S.Container';

const Circle = styled.div`
  border-radius: 50%;
  width: 40px;
  height: 40px;
  background-color: ${hexToRGB(globals.OBLIVION, 0.04)};
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
`;

const Title = styled.div`
  color: ${globals.MOON_950};
  text-align: center;
  font-family: Source Sans Pro;
  font-size: 18px;
  font-style: normal;
  font-weight: 600;
  line-height: 32px;
  margin-top: 16px;
`;
Title.displayName = 'S.Title';

const Description = styled.div`
  color: ${globals.MOON_750};
  text-align: center;
  font-family: Source Sans Pro;
  font-size: 14px;
  font-style: normal;
  font-weight: 400;
  line-height: 140%;
  margin-bottom: 24px;
`;
Description.displayName = 'S.Description';

type BoardsTabNoneProps = {
  hasTemplates: boolean;
  onNewBoard: () => void;
  setTabValue: React.Dispatch<React.SetStateAction<string>>;
};

export const BoardsTabNone = ({
  hasTemplates,
  onNewBoard,
  setTabValue,
}: BoardsTabNoneProps) => {
  return (
    <Wrapper>
      <Container>
        <Circle>
          <IconDashboardBlackboard />
        </Circle>
        <Title>No board yet</Title>
        <Description>
          This table isn't used in any board at the moment. Create a new board
          from scratch or explore available templates for a head-start.
        </Description>
        <Button
          size="large"
          icon="add-new"
          className="my-8 w-full"
          onClick={onNewBoard}>
          New board
        </Button>
        {hasTemplates && (
          <Button
            variant="secondary"
            size="large"
            icon="category-multimodal"
            className="w-full"
            onClick={() => setTabValue('Templates')}>
            View templates
          </Button>
        )}
      </Container>
    </Wrapper>
  );
};
