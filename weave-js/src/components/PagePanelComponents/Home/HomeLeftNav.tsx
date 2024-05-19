import {MOON_800} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {voidNode} from '@wandb/weave/core';
import {trackNewBlankBoardClicked} from '@wandb/weave/util/events';
import moment from 'moment';
import React, {useCallback, useState} from 'react';
import styled from 'styled-components';

import {Link} from '../../../common/util/links';
import getConfig from '../../../config';
import {useWeaveContext} from '../../../context';
import {useNewPanelFromRootQueryCallback} from '../../Panel2/PanelRootBrowser/util';
import {NavigateToExpressionType} from './common';
import * as LayoutElements from './LayoutElements';

const LeftNavItemBlock = styled(LayoutElements.HBlock)`
  margin: 0px 0px 0px 12px;
  padding: 0px 0px 0px 12px;
  border-radius: 4px;
  height: 36px;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  cursor: pointer;
  &:hover {
    background-color: #f5f6f7;
  }
`;
LeftNavItemBlock.displayName = 'S.LeftNavItemBlock';

const NewBoardButtonWrapper = styled.div`
  margin: 0px 24px 16px 24px;
`;
NewBoardButtonWrapper.displayName = 'S.NewBoardButton';

export const LeftNav: React.FC<{
  sections: LeftNavSectionProps[];
  inJupyter: boolean;
  navigateToExpression: NavigateToExpressionType;
}> = props => {
  const now = moment().format('YY_MM_DD_hh_mm_ss');
  const inJupyter = props.inJupyter;
  const defaultName = now;
  const [newName] = useState('');
  const weave = useWeaveContext();
  const name = 'dashboard-' + (newName === '' ? defaultName : newName);
  const makeNewDashboard = useNewPanelFromRootQueryCallback();
  const {urlPrefixed} = getConfig();
  const newDashboard = useCallback(() => {
    makeNewDashboard(name, voidNode(), true, newDashExpr => {
      if (inJupyter) {
        const expStr = weave
          .expToString(newDashExpr)
          .replace(/\n+/g, '')
          .replace(/\s+/g, '');
        window.open(
          urlPrefixed(`?exp=${encodeURIComponent(expStr)}`),
          '_blank'
        );
      } else {
        props.navigateToExpression(newDashExpr);
      }
    });
  }, [inJupyter, makeNewDashboard, name, props, urlPrefixed, weave]);

  return (
    <LayoutElements.VBlock
      style={{
        width: '288px', // Makes up for 12px gap
        paddingTop: '0px', // Cecile's design has spacing here, but i kind of like it without
        overflowY: 'auto',
      }}>
      <NewBoardButtonWrapper>
        <Button
          variant="secondary"
          onClick={() => {
            newDashboard();
            trackNewBlankBoardClicked('home');
          }}
          icon="add-new"
          size="large">
          New blank board
        </Button>
      </NewBoardButtonWrapper>

      {props.sections.map((section, i) => (
        <LeftNavSection key={i} {...section} />
      ))}
    </LayoutElements.VBlock>
  );
};

type LeftNavSectionProps = {
  title: string;
  items: LeftNavItemProps[];
};

const LeftNavSection: React.FC<LeftNavSectionProps> = props => {
  return (
    <LayoutElements.VBlock
      style={{
        marginBottom: '16px',
      }}>
      {/* Header */}
      <LayoutElements.BlockHeader
        style={{
          textTransform: 'uppercase',
          padding: '10px 24px',
          fontSize: '14px',
          position: 'sticky',
          backgroundColor: '#fff',
          top: 0,
        }}>
        {props.title}
      </LayoutElements.BlockHeader>
      {/* Items */}
      <LayoutElements.VBlock>
        {props.items.map((item, i) => (
          <LeftNavItem key={i} {...item} />
        ))}
      </LayoutElements.VBlock>
    </LayoutElements.VBlock>
  );
};

type LeftNavItemProps = {
  icon: React.FC;
  label: string;
  active?: boolean;
  to: string;
  onClick?: () => void;
};
const LeftNavItem: React.FC<LeftNavItemProps> = props => {
  return (
    <Link to={props.to} onClick={props.onClick}>
      <LeftNavItemBlock
        style={{
          backgroundColor: props.active ? '#A9EDF252' : '',
          color: props.active ? '#038194' : MOON_800,
          fontWeight: props.active ? 600 : '',
        }}>
        <props.icon />
        {props.label}
      </LeftNavItemBlock>
    </Link>
  );
};
