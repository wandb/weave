import {voidNode} from '@wandb/weave/core';
import moment from 'moment';
import React, {useCallback, useState} from 'react';
import getConfig from '../../../config';

import styled from 'styled-components';
import {WBButton} from '../../../common/components/elements/WBButtonNew';
import {useWeaveContext} from '../../../context';
import {
  IconAddNew as IconAddNewUnstyled,
  IconWeaveLogo,
} from '../../Panel2/Icons';
import {useNewPanelFromRootQueryCallback} from '../../Panel2/PanelRootBrowser/util';
import {NavigateToExpressionType} from './common';

export const HomeTopBar: React.FC<{
  navigateToExpression: NavigateToExpressionType;
  inJupyter: boolean;
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
    <TopBar>
      <TopBarLeft>
        <WeaveLogo />
        Weave
      </TopBarLeft>
      <TopBarRight>
        <WBButton variant={`confirm`} onClick={newDashboard}>
          <IconAddNew />
          New board
        </WBButton>
      </TopBarRight>
    </TopBar>
  );
};

const TopBar = styled.div`
  height: 64px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const TopBarLeft = styled.div`
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: 600;
`;

const TopBarRight = styled.div`
  display: flex;
  align-items: center;
`;

const WeaveLogo = styled(IconWeaveLogo)`
  width: 32px;
  height: 32px;
  margin-right: 12px;
`;

const IconAddNew = styled(IconAddNewUnstyled)`
  width: 18px;
  height: 18px;
  margin-right: 6px;
`;
