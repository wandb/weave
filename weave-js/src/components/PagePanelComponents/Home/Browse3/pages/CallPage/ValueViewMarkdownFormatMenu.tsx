import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import React, {useState} from 'react';

import {Button} from '../../../../../Button';

export type Format = 'Markdown' | 'Code' | 'Text';

type ValueViewMarkdownFormatMenuProps = {
  format: Format;
  onSetFormat: (format: Format) => void;
};

// Unfortunately necessary to be visible above drawer.
const STYLE_MENU_CONTENT = {zIndex: 1};

export const ValueViewMarkdownFormatMenu = ({
  format,
  onSetFormat,
}: ValueViewMarkdownFormatMenuProps) => {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div>
      <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
        <DropdownMenu.Trigger>
          <Button size="small" variant="ghost" active={isOpen}>
            {format}
          </Button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="end" style={STYLE_MENU_CONTENT}>
            <DropdownMenu.Item onClick={() => onSetFormat('Markdown')}>
              Markdown
            </DropdownMenu.Item>
            <DropdownMenu.Item onClick={() => onSetFormat('Code')}>
              Code
            </DropdownMenu.Item>
            <DropdownMenu.Item onClick={() => onSetFormat('Text')}>
              Text
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div>
  );
};
