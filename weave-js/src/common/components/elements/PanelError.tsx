import classNames from 'classnames';
import React from 'react';

import {IconInfo} from '../../../components/Icon';
import {Tailwind} from '../../../components/Tailwind';

type PanelErrorProps = {
  message: React.ReactChild;
  className?: string;
};

const PanelError: React.FC<PanelErrorProps> = React.memo(
  ({message, className}) => {
    return (
      <div
        className={classNames('panel-error', className)}
        data-test="panel-error">
        <Tailwind>
          <IconInfo width={24} height={24} className="m-auto mb-4" />
          <div>{message}</div>
        </Tailwind>
      </div>
    );
  }
);
export default PanelError;
