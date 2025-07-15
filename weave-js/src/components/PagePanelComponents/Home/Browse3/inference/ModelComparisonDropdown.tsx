import {Button} from '@wandb/weave/components/Button';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import React, {useState} from 'react';

import {Icon} from '../../../../Icon';

type ModelComparisonDropdownProps = {
  index: number;
  numModels: number;
  onMakeBaseline: () => void;
  onRemoveFromComparison: () => void;
};

export const ModelComparisonDropdown = ({
  index,
  numModels,
  onMakeBaseline,
  onRemoveFromComparison,
}: ModelComparisonDropdownProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isSubOpen, setIsSubOpen] = useState(false);

  const hasStart = index !== 0 && numModels > 2;
  const hasLeft = index !== 0;
  const hasRight = index !== numModels - 1;
  const hasEnd = index !== numModels - 1 && numModels > 2;

  return (
    <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenu.Trigger>
        <Button variant="ghost" icon="overflow-horizontal" active={isOpen} />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="start">
          {/* <DropdownMenu.Sub open={isSubOpen} onOpenChange={setIsSubOpen}>
            <DropdownMenu.SubTrigger>
              <Icon name="swap" />
              Move model
              <Icon name="chevron-next" className="text-moon-450" />
            </DropdownMenu.SubTrigger>
            <DropdownMenu.Portal>
              <DropdownMenu.SubContent>
                {hasStart && (
                  <DropdownMenu.Item>
                    <Icon name="back" />
                    Start
                  </DropdownMenu.Item>
                )}
                {hasLeft && (
                  <DropdownMenu.Item>
                    <Icon name="chevron-back" />
                    Left
                  </DropdownMenu.Item>
                )}
                {hasRight && (
                  <DropdownMenu.Item>
                    <Icon name="chevron-next" />
                    Right
                  </DropdownMenu.Item>
                )}
                {hasEnd && (
                  <DropdownMenu.Item>
                    <Icon name="forward-next" />
                    End
                  </DropdownMenu.Item>
                )}
              </DropdownMenu.SubContent>
            </DropdownMenu.Portal>
          </DropdownMenu.Sub> */}
          <DropdownMenu.Item onClick={onMakeBaseline} disabled={index === 0}>
            <Icon name="baseline-alt" />
            Make baseline
          </DropdownMenu.Item>
          <DropdownMenu.Separator />
          <DropdownMenu.Item onClick={onRemoveFromComparison}>
            <Icon name="delete" />
            Remove from comparison
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
};
