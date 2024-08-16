import {ErrorPanel} from '@wandb/weave/components/ErrorPanel';
import React, {FC, useContext} from 'react';

import {Button} from '../../../Button';
import {useClosePeek, WeaveflowPeekContext} from './context';

export const NotFoundPanel: FC<{title: string}> = ({title}) => {
  const close = useClosePeek();
  const {isPeeking} = useContext(WeaveflowPeekContext);
  return (
    <div style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
      <div style={{alignSelf: 'flex-end', margin: 10}}>
        {isPeeking && <Button icon="close" variant="ghost" onClick={close} />}
      </div>
      <div style={{flex: 1}}>
        <ErrorPanel title={title} subtitle="" subtitle2="" />
      </div>
    </div>
  );
};
