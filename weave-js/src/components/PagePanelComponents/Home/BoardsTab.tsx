import * as globals from '@wandb/weave/common/css/globals.styles';
import {constString, NodeOrVoidNode, opGet} from '@wandb/weave/core';
import {trackNewBoardFromTemplateClicked} from '@wandb/weave/util/events';
import moment from 'moment';
import React from 'react';
import styled from 'styled-components';

import {maybePluralize} from '../../../core/util/string';
import {Button} from '../../Button';
import {IconChevronNext, IconDashboardBlackboard} from '../../Icon';
import {useArtifactDependencyOfForNode} from '../../Panel2/pyArtifactDep';
import {useMakeLocalBoardFromNode} from '../../Panel2/pyBoardGen';
import {BoardsTabNone} from './BoardsTabNone';
import {NavigateToExpressionType, WANDB_ARTIFACT_SCHEME} from './common';
import {SEED_BOARD_OP_NAME} from './HomePreviewSidebar';
import * as LayoutElements from './LayoutElements';
import * as S from './styles';

const BoardList = styled.div`
  flex: 1 1 auto;
  padding: 16px;
  overflow-y: auto;
`;
BoardList.displayName = 'S.BoardList';

const Board = styled.div`
  cursor: pointer;
  border-radius: 4px;
  border: 1px solid ${globals.MOON_250};
  padding: 12px 12px 12px 16px;
  margin-bottom: 8px;
  display: flex;
  gap: 8px;
  &:hover {
    border: 1px solid ${globals.TEAL_400};
  }
`;
Board.displayName = 'S.Board';

const BoardTitle = styled.div`
  color: ${globals.MOON_800};
  font-family: Source Sans Pro;
  font-size: 16px;
  font-style: normal;
  font-weight: 600;
  line-height: 24px;
`;
BoardTitle.displayName = 'S.BoardTitle';

const BoardSource = styled.div`
  color: ${globals.MOON_500};
  font-family: Source Sans Pro;
  font-size: 14px;
  font-style: normal;
  font-weight: 400;
  line-height: 20px;
`;
BoardSource.displayName = 'S.BoardSource';

const BoardCreatedAt = styled.div`
  color: ${globals.MOON_500};
  font-family: Source Sans Pro;
  font-size: 14px;
  font-style: normal;
  font-weight: 400;
  line-height: 24px;
  white-space: nowrap;
`;
BoardCreatedAt.displayName = 'S.BoardCreatedAt';

const Footer = styled.div`
  border-top: 1px solid ${globals.MOON_250};
  padding: 16px 12px;
  flex: 0 0 auto;
`;
Footer.displayName = 'S.Footer';

const getCalendarFormats = (date: moment.Moment) => {
  const currentYear = moment().year();
  const yearOfDate = date.year();
  const sameElse = currentYear === yearOfDate ? 'MMM DD' : 'MMM DD, YYYY';
  return {
    sameDay: '[Today]',
    nextDay: '[Tomorrow]',
    nextWeek: 'dddd',
    lastDay: '[Yesterday]',
    lastWeek: 'MMM DD',
    sameElse,
  };
};

export const BoardsTab = ({
  dependencyQuery,
  navigateToExpression,
  isLoadingTemplates,
  setIsGenerating,
  setTabValue,
  hasTemplates,
  refinedExpression,
}: {
  dependencyQuery: ReturnType<typeof useArtifactDependencyOfForNode>;
  navigateToExpression: NavigateToExpressionType;
  isLoadingTemplates: boolean;
  setIsGenerating: React.Dispatch<React.SetStateAction<boolean>>;
  setTabValue: React.Dispatch<React.SetStateAction<string>>;
  hasTemplates: boolean;
  refinedExpression: {
    loading: boolean;
    result: NodeOrVoidNode;
  };
}) => {
  const numBoards = dependencyQuery.result.length;

  const makeBoardFromNode = useMakeLocalBoardFromNode();

  const onNewBoard = () => {
    setIsGenerating(true);
    makeBoardFromNode(
      SEED_BOARD_OP_NAME,
      refinedExpression.result as any,
      newDashExpr => {
        setIsGenerating(false);
        navigateToExpression(newDashExpr);
      }
    );
    trackNewBoardFromTemplateClicked(
      'table-board-tab',
      'simple-table-visualization'
    );
  };

  return (
    <LayoutElements.VStack style={{gap: '16px', overflow: 'auto'}}>
      {dependencyQuery.loading ? (
        // TODO: Do we want to use loading indicators?
        <div></div>
      ) : numBoards === 0 ? (
        <BoardsTabNone
          hasTemplates={hasTemplates}
          onNewBoard={onNewBoard}
          setTabValue={setTabValue}
        />
      ) : (
        <BoardList>
          <div style={{marginBottom: '8px'}}>
            <S.ObjectCount>
              {maybePluralize(numBoards, 'board', 's')}
            </S.ObjectCount>
          </div>
          {dependencyQuery.result.map(board => {
            const {entityName, projectName, artifactSequence} = board;
            const artName = artifactSequence.name;
            const boardUri = `${WANDB_ARTIFACT_SCHEME}///${entityName}/${projectName}/${artName}:latest/obj`;
            const navigateExpr = opGet({uri: constString(boardUri)});
            const onClick = () => {
              navigateToExpression(navigateExpr);
            };

            const createdAt = moment(board.createdAt);
            return (
              <Board key={board.artifactSequence.id} onClick={onClick}>
                <IconDashboardBlackboard />
                <div>
                  <BoardTitle>{board.artifactSequence.name}</BoardTitle>
                  <BoardSource>
                    {board.createdByUsername} in {board.entityName}/
                    {board.projectName}
                  </BoardSource>
                </div>
                <BoardCreatedAt>
                  {createdAt.calendar(null, getCalendarFormats(createdAt))}
                </BoardCreatedAt>
                <IconChevronNext />
              </Board>
            );
          })}
        </BoardList>
      )}
      {numBoards !== 0 && (
        <Footer>
          <Button
            size="large"
            icon="add-new"
            className="w-full"
            onClick={onNewBoard}>
            New board
          </Button>
        </Footer>
      )}
    </LayoutElements.VStack>
  );
};
