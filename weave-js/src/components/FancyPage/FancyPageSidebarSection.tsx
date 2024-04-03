import {
  hexToRGB,
  MEDIUM_BREAKPOINT,
  MOON_250,
  MOON_800,
  MOONBEAM,
  OBLIVION,
  TEAL_450,
  TEAL_550,
} from '@wandb/weave/common/css/globals.styles';
import {TargetBlank} from '@wandb/weave/common/util/links';
import {Icon} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React from 'react';
import {Link} from 'react-router-dom';
import styled from 'styled-components';

import {isInNightMode} from '../nightMode';
import {FancyPageSidebarItem} from './FancyPageSidebar';

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

type FancyPageSidebarSectionProps = {
  selectedItem?: FancyPageSidebarItem;
  items: FancyPageSidebarItem[];
  baseUrl: string;
};

const FancyPageSidebarSection = (props: FancyPageSidebarSectionProps) => {
  const isNightMode = isInNightMode();

  const [hoveredItem, setHoveredItem] =
    React.useState<FancyPageSidebarItem | null>(null);
  return (
    <>
      {props.items.map(item => {
        const onMouseEnter = (e: React.MouseEvent<HTMLElement, MouseEvent>) => {
          setHoveredItem(item);
        };
        const onMouseLeave = (e: React.MouseEvent<HTMLElement, MouseEvent>) => {
          setHoveredItem(null);
        };
        let colorIconBg: string = 'transparent';
        let colorIcon: string = isNightMode ? MOON_250 : MOON_800;
        let colorText: string = isNightMode ? MOON_250 : MOON_800;
        if (item === props.selectedItem) {
          colorIconBg = hexToRGB(TEAL_550, isNightMode ? 0.16 : 0.1);
          colorIcon = colorText = isNightMode ? TEAL_450 : TEAL_550;
        } else if (item.isDisabled) {
          colorIcon = colorText = isNightMode ? MOON_800 : MOON_250;
        } else if (item === hoveredItem) {
          colorIconBg = isNightMode
            ? hexToRGB(MOONBEAM, 0.08)
            : hexToRGB(OBLIVION, 0.04);
        }
        const baseLinkProps = {
          key: item.name,
          onClick: () => {
            item.onClick?.();
          },
          onMouseEnter,
          onMouseLeave,
          'data-test': item.slug + '-tab',
        };
        if (item.externalLink) {
          const externalLinkProps = {
            ...baseLinkProps,
            href: item.externalLink,
          };
          return (
            <SidebarWrapper key={item.name} className="night-aware">
              <TargetBlank
                {...externalLinkProps}
                style={{
                  pointerEvents: item.isDisabled ? 'none' : 'auto',
                  cursor: item.isDisabled ? 'default' : 'pointer',
                }}>
                <SidebarButton>
                  <ItemIcon color={colorIconBg}>
                    <Icon name={item.iconName} color={colorIcon} />
                  </ItemIcon>
                  <ItemLabel color={colorText}>{item.name}</ItemLabel>
                </SidebarButton>
              </TargetBlank>
            </SidebarWrapper>
          );
        }

        const linkProps = {
          ...baseLinkProps,
          to: item.isDisabled
            ? {}
            : {
                pathname: item.slug
                  ? `${props.baseUrl}/${item.slug}`
                  : props.baseUrl,
                // Preserve query string. Gets updated because the component happens to re-render on hover.
                search: window.location.search,
              },
        };

        const wrapper = (
          <SidebarWrapper key={item.name} className="night-aware">
            <Link
              {...linkProps}
              style={{
                pointerEvents: item.isDisabled ? 'none' : 'auto',
                cursor: item.isDisabled ? 'default' : 'pointer',
              }}>
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

export default FancyPageSidebarSection;
