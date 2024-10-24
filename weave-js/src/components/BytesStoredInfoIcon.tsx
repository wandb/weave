import numeral from 'numeral';
import React from 'react';

import {IconInfo} from './Icon';
import {Tailwind} from './Tailwind';
import {Tooltip as WeaveTooltip} from './Tooltip';

export const BytesStoredInfoIcon = ({
  bytesStored,
  weaveKind,
}: {
  bytesStored: number;
  weaveKind: string;
}) => (
  <Tailwind>
    <div className="flex items-center gap-4">
      {numeral(bytesStored).format('0.0b')}
      <WeaveTooltip
        content={`This does not take into account any files or media logged in this ${weaveKind}.`}
        placement="top-start"
        trigger={<IconInfo className="ml-2 text-moon-500" />}
      />
    </div>
  </Tailwind>
);
