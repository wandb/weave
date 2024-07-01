import {useMediaQuery} from '@material-ui/core';
import {MEDIUM_BREAKPOINT} from '@wandb/weave/common/css/breakpoints.styles';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import {Icon, IconOverflowHorizontal} from '@wandb/weave/components/Icon';
import {Link} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import React, {useState} from 'react';

import {ItemIcon, ItemLabel, MenuButton} from './FancyPageButton';
import {FancyPageSidebarItem} from './FancyPageSidebar';

type FancyPageMenuProps = {
  baseUrl: string;
  menuItems: FancyPageSidebarItem[];
  colorIconBg: string;
  colorText: string;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
};

// Unfortunately needed to appear above the artifacts UI.
const STYLE_MENU_CONTENT = {zIndex: 2};

export const FancyPageMenu = ({
  baseUrl,
  menuItems,
  colorIconBg,
  colorText,
  onMouseEnter,
  onMouseLeave,
}: FancyPageMenuProps) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const isHorizontal: boolean = useMediaQuery(
    `@media (max-width:${MEDIUM_BREAKPOINT}px)`
  );
  const menuSide = isHorizontal ? 'bottom' : 'right';

  return (
    <DropdownMenu.Root open={isMenuOpen} onOpenChange={setIsMenuOpen}>
      <DropdownMenu.Trigger>
        <div style={{alignSelf: 'stretch'}}>
          <MenuButton onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>
            <ItemIcon color={colorIconBg}>
              <IconOverflowHorizontal />
            </ItemIcon>
            <ItemLabel color={colorText}>More</ItemLabel>
          </MenuButton>
        </div>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          side={menuSide}
          style={STYLE_MENU_CONTENT}>
          {menuItems.map((menuItem, i) => {
            if (menuItem.type !== 'button') {
              return null;
            }
            const linkProps = {
              key: menuItem.slug,
              to: menuItem.isDisabled
                ? {}
                : {
                    pathname: menuItem.slug
                      ? `${baseUrl}/${menuItem.slug}`
                      : baseUrl,
                  },
            };

            const menuItemProps = {
              onClick: () => {
                setIsMenuOpen(false);
              },
            };
            return (
              <Link {...linkProps}>
                <DropdownMenu.Item {...menuItemProps}>
                  <Icon name={menuItem.iconName} />
                  {menuItem.nameTooltip || menuItem.name}
                </DropdownMenu.Item>
              </Link>
            );
          })}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
};
