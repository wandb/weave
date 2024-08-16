import {ErrorPanel} from '@wandb/weave/components/ErrorPanel';
import React, {FC} from 'react';

import {Button} from '../../../Button';
import {useClosePeek} from './context';

export const NotFoundPanel: FC<{title: string}> = ({title}) => {
  const close = useClosePeek();
  return (
    <div style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
      <div style={{alignSelf: 'flex-end', margin: 10}}>
        <Button icon="close" variant="ghost" onClick={close} />
      </div>
      <div style={{flex: 1}}>
        <ErrorPanel title={title} subtitle="" subtitle2="" />
      </div>
    </div>
  );
};
