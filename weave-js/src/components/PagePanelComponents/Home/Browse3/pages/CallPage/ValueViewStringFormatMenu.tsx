import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import * as React from 'react';

import {Button} from '../../../../../Button';

type ValueViewStringFormatMenuProps = {
  format: string;
  onSetFormat: (format: string) => void;
};

export const ValueViewStringFormatMenu = ({
  format,
  onSetFormat,
}: ValueViewStringFormatMenuProps) => {
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const onClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };
  const handleClose = () => {
    setAnchorEl(null);
  };

  const onClickMenuItem = (newFormat: string) => {
    onSetFormat(newFormat);
    handleClose();
  };

  return (
    <div>
      <Button size="small" variant="ghost" onClick={onClick}>
        {format}
      </Button>
      <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
        <MenuItem onClick={() => onClickMenuItem('Text')}>Text</MenuItem>
        <MenuItem onClick={() => onClickMenuItem('JSON')}>JSON</MenuItem>
        <MenuItem onClick={() => onClickMenuItem('Markdown')}>
          Markdown
        </MenuItem>
        <MenuItem onClick={() => onClickMenuItem('Code')}>Code</MenuItem>
      </Menu>
    </div>
  );
};
