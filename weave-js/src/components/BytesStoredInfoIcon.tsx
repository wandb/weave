import {IconInfo} from '@wandb/weave/components/Icon';
import numeral from 'numeral';
import React from 'react';

import {Tailwind} from './Tailwind';
import {Tooltip as WeaveTooltip} from './Tooltip';

export const BytesStoredInfoIcon = ({bytesStored}: {bytesStored: number}) => (
  <Tailwind>
    <div className="flex items-center">
      {numeral(bytesStored).format('0.0b')}
      <WeaveTooltip
        content="This doesn't account for file and media sizes."
        placement="top-start"
        trigger={<IconInfo className="ml-2 text-moon-500" />}
      />
    </div>
  </Tailwind>
);
