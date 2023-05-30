import React, {useState} from 'react';
import {IconSizeProp} from 'semantic-ui-react/dist/commonjs/elements/Icon/Icon';

import {LegacyWBIcon} from './elements/LegacyWBIcon';

type ShowMoreContainerProps = {
  children: JSX.Element[];
  className?: string;
  iconSize?: IconSizeProp;
};

const ShowMoreContainerComp = (props: ShowMoreContainerProps) => {
  const [open, setOpen] = useState<boolean>(false);
  const iconSize = props.iconSize;

  const iconProps = {size: iconSize, onClick: () => setOpen(!open)};

  return (
    <div
      className={props.className ?? ''}
      style={{display: 'flex', maxWidth: 600}}>
      <LegacyWBIcon
        {...iconProps}
        name="next"
        style={{
          cursor: 'pointer',
          transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
        }}
        className="open show-more-container-toggle"
      />
      <div
        style={{
          maxHeight: open ? undefined : 32,
          overflow: 'hidden',
        }}>
        {props.children}
      </div>
    </div>
  );
};
export const ShowMoreContainer = React.memo(ShowMoreContainerComp);
