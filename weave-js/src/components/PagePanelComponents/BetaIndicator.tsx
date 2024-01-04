import * as globals from '@wandb/weave/common/css/globals.styles';
import {TargetBlank} from '@wandb/weave/common/util/links';
import queryString from 'query-string';
import React, {useCallback} from 'react';
import styled from 'styled-components';

import {getCookie} from '../../common/util/cookie';
import * as LE from './Home/LayoutElements';

const BETA_VERSION_COOKIE_KEY = 'betaVersion';
export const betaVersion = getCookie(BETA_VERSION_COOKIE_KEY);

const BetaIndicatorOuter = styled(LE.HStack)`
  position: absolute;
  bottom: 2px;
  left: 0px;
  z-index: 1000;
  width: 300px;
  height: 20px;
  justify-content: center;
`;
BetaIndicatorOuter.displayName = 'S.BetaIndicatorOuter';

const BetaIndicatorInner = styled(LE.HStack)`
  font-size: 14px;
  background-color: ${globals.MAGENTA_300};
  color: ${globals.MAGENTA_600};
  line-height: 20px;
  padding: 0 16px;
  border-radius: 2px;
  width: fit-content;
`;
BetaIndicatorInner.displayName = 'S.BetaIndicatorInner';

const LinkStyle = styled.span`
  font-weight: 600;
  color: ${globals.TEAL_600};
  &:hover {
    color: ${globals.TEAL_500};
  }
`;
LinkStyle.displayName = 'S.LinkStyle';

const ButtonLink = styled.button`
  font-family: Source Sans Pro;
  font-size: 14px;
  font-weight: 600;
  color: ${globals.TEAL_600};
  &:hover {
    color: ${globals.TEAL_500};
  }

  background-color: transparent;
  border: none;
  display: inline;
  margin: 0;
  padding: 0;
  cursor: pointer;
`;

export const BetaIndicator: React.FC<{}> = () => {
  if (!betaVersion) {
    return null;
  }
  return (
    <BetaIndicatorOuter>
      <BetaPill />
    </BetaIndicatorOuter>
  );
};

const BetaPill: React.FC<{}> = () => {
  const unsetBetaVersion = useCallback(() => {
    const qsParams = queryString.parse(window.location.search);
    qsParams.unsetBetaVersion = `true`;
    window.location.search = queryString.stringify(qsParams);
  }, []);

  const urlGithub = `https://github.com/wandb/core/commit/${betaVersion}`;

  return (
    <BetaIndicatorInner>
      <LE.Block>
        Viewing{' '}
        <TargetBlank href={urlGithub}>
          <LinkStyle>beta version</LinkStyle>
        </TargetBlank>
        . <ButtonLink onClick={unsetBetaVersion}>Unset</ButtonLink>
      </LE.Block>
    </BetaIndicatorInner>
  );
};
