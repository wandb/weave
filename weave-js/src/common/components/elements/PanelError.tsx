import {WBIcon} from '@wandb/ui';
import classNames from 'classnames';
import React from 'react';

import * as S from './PanelError.styles';

type PanelErrorProps = {
  message: React.ReactChild;
  className?: string;
};

const PanelError: React.FC<PanelErrorProps> = React.memo(
  ({message, className}) => {
    return (
      <div className={classNames('panel-error', className)}>
        <div>
          <S.IconWrapper>
            <WBIcon name="info" />
          </S.IconWrapper>
          <div>{message}</div>
        </div>
      </div>
    );
  }
);
export default PanelError;
