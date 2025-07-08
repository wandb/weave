import {useEntityProject} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {buttonClicked} from '@wandb/weave/integrations/analytics/userEvents';
import React, {useCallback} from 'react';

import {Button, ButtonProps} from './Button';

export const TrackedButton = (props: ButtonProps & {trackedName: string}) => {
  const {entity, project} = useEntityProject();

  const {trackedName, onClick: clientOnClick, ...restProps} = props;

  const onClick = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      clientOnClick?.(event);
      buttonClicked({entity, project, buttonName: trackedName});
    },
    [entity, project, trackedName, clientOnClick]
  );

  return <Button {...restProps} onClick={onClick} />;
};
