import {
  hexToRGB,
  MEDIUM_BREAKPOINT,
  MOON_250,
  MOON_800,
  MOONBEAM,
  OBLIVION,
  TEAL_450,
  TEAL_550,
  TRANSPARENT,
} from '@wandb/weave/common/css/globals.styles';
import {Icon} from '@wandb/weave/components/Icon';
import React from 'react';
import {Link} from 'react-router-dom';
import styled from 'styled-components';

import {isInNightMode} from '../../../nightMode';
import {Tooltip} from '../../../Tooltip';
import {SidebarItem} from './Sidebar';

const SidebarWrapper = styled.div`
  @media only screen and (max-width: ${MEDIUM_BREAKPOINT}px) {
    display: flex;
    align-items: center;
  }
`;
SidebarWrapper.displayName = 'S.SidebarWrapper';

const SidebarButton = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
`;
SidebarButton.displayName = 'S.SidebarButton';

type ItemIconProps = {
  color: string;
};
const ItemIcon = styled.div<ItemIconProps>`
  height: 32px;
  box-sizing: border-box;
  border-radius: 8px;
  padding: 6px 12px;
  background-color: ${props => props.color};
  display: flex;
  align-items: center;
  @media only screen and (max-width: ${MEDIUM_BREAKPOINT}px) {
    padding: 0 12px;
  }
`;
ItemIcon.displayName = 'S.ItemIcon';

type ItemLabelProps = {
  color: string;
};
const ItemLabel = styled.div<ItemLabelProps>`
  color: ${props => props.color};
  font-family: 'Source Sans Pro';
  font-weight: 600;
  height: 14px;
  font-size: 10px;
  line-height: 14px;
  text-align: center;
`;
ItemLabel.displayName = 'S.ItemLabel';

type SidebarSectionProps = {
  selectedItem: string | null;
  items: SidebarItem[];
};

type UrlParts = {
  pathname: string;
  search?: string;
};

const parseUrl = (path: string): UrlParts => {
  const [pathname, search] = path.split('?');
  return {
    pathname,
    search: search ? search : undefined,
  };
};

const SidebarSection = (props: SidebarSectionProps) => {
  const isNightMode = isInNightMode();

  const [hoveredItem, setHoveredItem] = React.useState<string | null>(null);
  return (
    <>
      {props.items.map(item => {
        const onMouseEnter = (e: React.MouseEvent<HTMLElement, MouseEvent>) => {
          setHoveredItem(item.id);
        };
        const onMouseLeave = (e: React.MouseEvent<HTMLElement, MouseEvent>) => {
          setHoveredItem(null);
        };
        let colorIconBg: string = TRANSPARENT;
        let colorIcon: string = isNightMode ? MOON_250 : MOON_800;
        let colorText: string = isNightMode ? MOON_250 : MOON_800;
        if (item.id === props.selectedItem) {
          colorIconBg = hexToRGB(TEAL_550, isNightMode ? 0.16 : 0.1);
          colorIcon = colorText = isNightMode ? TEAL_450 : TEAL_550;
        } else if (item.id === hoveredItem) {
          colorIconBg = isNightMode
            ? hexToRGB(MOONBEAM, 0.08)
            : hexToRGB(OBLIVION, 0.04);
        }
        const baseLinkProps = {
          key: item.id,
          onMouseEnter,
          onMouseLeave,
          'data-test': item.id + '-tab',
        };

        const linkProps = {
          ...baseLinkProps,
          to: {
            ...parseUrl(item.path),
          },
        };

        const wrapper = (
          <SidebarWrapper key={item.name} className="night-aware">
            <Link {...linkProps}>
              <SidebarButton>
                <ItemIcon color={colorIconBg}>
                  <Icon name={item.iconName} color={colorIcon} />
                </ItemIcon>
                <ItemLabel color={colorText}>{item.name}</ItemLabel>
              </SidebarButton>
            </Link>
          </SidebarWrapper>
        );

        if (item.nameTooltip) {
          return (
            <Tooltip
              key={item.name}
              content={<span>{item.nameTooltip}</span>}
              trigger={wrapper}
              position="right center"
            />
          );
        }
        return wrapper;
      })}
    </>
  );
};

export default SidebarSection;
