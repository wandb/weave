import React, {FC} from 'react';

import {Icon} from '../Icon';
import {Tailwind} from '../Tailwind';

export type RemoveActionProps = Record<string, any>;

export const RemoveAction: FC<RemoveActionProps> = (
  props: RemoveActionProps
) => {
  return (
    <Tailwind>
      <button
        type="button"
        className="ml-4 flex cursor-pointer opacity-60 hover:opacity-100"
        {...props}>
        <Icon className="h-14 w-14" name="close" />
      </button>
    </Tailwind>
  );
};
