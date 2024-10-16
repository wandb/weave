import {
  hexToRGB,
  MEDIUM_BREAKPOINT,
  MOON_250,
  MOON_500,
  MOON_800,
  MOONBEAM,
  OBLIVION,
  TEAL_450,
  TEAL_550,
  TRANSPARENT,
} from '@wandb/weave/common/css/globals.styles';
import {TargetBlank} from '@wandb/weave/common/util/links';
import {Icon} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React from 'react';
import {Link} from 'react-router-dom';
import styled from 'styled-components';

import {isInNightMode} from '../nightMode';
import {ItemIcon, ItemLabel, SidebarButton} from './FancyPageButton';
import {FancyPageMenu} from './FancyPageMenu';
import {FancyPageSidebarItem} from './FancyPageSidebar';

const SidebarWrapper = styled.div`
  @media only screen and (max-width: ${MEDIUM_BREAKPOINT}px) {
    display: flex;
    align-items: center;
  }
`;
SidebarWrapper.displayName = 'S.SidebarWrapper';

const SidebarLabel = styled.div`
  font-family: Source Sans Pro;
  font-size: 12px;
  font-weight: 600;
  text-align: center;
  text-transform: uppercase;
  color: ${MOON_500};
  margin-bottom: -12px; // Undo the flex gap a bit
  @media only screen and (max-width: ${MEDIUM_BREAKPOINT}px) {
    display: none;
  }
`;
SidebarLabel.displayName = 'S.SidebarLabel';

const SidebarDivider = styled.div`
  background: #d2d2d2;
  height: 1px;
  margin: 0 12px;
  @media only screen and (max-width: ${MEDIUM_BREAKPOINT}px) {
    width: 1px;
    height: 32px;
    margin: 12px 0;
  }
`;
SidebarDivider.displayName = 'S.SidebarDivider';

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
        if (item.type === 'divider') {
          return <SidebarDivider key={item.key} />;
        }
        if (item.type === 'label') {
          return (
            <SidebarLabel key={'label' + item.label}>{item.label}</SidebarLabel>
          );
        }

        let colorIconBg: string = TRANSPARENT;
        let colorIcon: string = isNightMode ? MOON_250 : MOON_800;
        let colorText: string = isNightMode ? MOON_250 : MOON_800;
        if (item === props.selectedItem) {
          colorIconBg = hexToRGB(TEAL_550, isNightMode ? 0.16 : 0.1);
          colorIcon = colorText = isNightMode ? TEAL_450 : TEAL_550;
        } else if (item.type === 'button' && item.isDisabled) {
          colorIcon = colorText = isNightMode ? MOON_800 : MOON_250;
        } else if (item === hoveredItem) {
          colorIconBg = isNightMode
            ? hexToRGB(MOONBEAM, 0.08)
            : hexToRGB(OBLIVION, 0.04);
        }
        const onMouseEnter = () => {
          setHoveredItem(item);
        };
        const onMouseLeave = () => {
          setHoveredItem(null);
        };

        if (item.type === 'menu') {
          return (
            <FancyPageMenu
              key={item.key}
              baseUrl={props.baseUrl}
              menuItems={item.menu}
              colorIconBg={colorIconBg}
              colorText={colorText}
              onMouseEnter={onMouseEnter}
              onMouseLeave={onMouseLeave}
            />
          );
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
                    <Icon
                      name={item.iconName}
                      color={colorIcon}
                      role="presentation"
                    />
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
              },
        };

        const button = (
          <SidebarButton>
            <ItemIcon color={colorIconBg}>
              <Icon
                name={item.iconName}
                color={colorIcon}
                role="presentation"
              />
            </ItemIcon>
            <ItemLabel color={colorText}>{item.name}</ItemLabel>
          </SidebarButton>
        );
        const wrapper = (
          <SidebarWrapper key={item.name} className="night-aware">
            <Link
              {...linkProps}
              style={{
                pointerEvents: item.isDisabled ? 'none' : 'auto',
                cursor: item.isDisabled ? 'default' : 'pointer',
              }}>
              {button}
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
