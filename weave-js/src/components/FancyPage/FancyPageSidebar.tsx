import {
  MEDIUM_BREAKPOINT,
  MOON_250,
  WHITE,
} from '@wandb/weave/common/css/globals.styles';
import {IconName} from '@wandb/weave/components/Icon';
import React from 'react';
import styled from 'styled-components';

import FancyPageSidebarSection from './FancyPageSidebarSection';

const Sidebar = styled.div`
  background-color: ${WHITE};
  box-sizing: content-box;
  border-right: 1px solid ${MOON_250};
  width: 56px;
  @media only screen and (max-width: ${MEDIUM_BREAKPOINT}px) {
    width: 100%;
    height: 56px;
    border-right: none;
    border-bottom: 1px solid ${MOON_250};
  }
`;
Sidebar.displayName = 'S.Sidebar';

const SidebarSections = styled.div`
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: sticky;
  top: 0;
  @media only screen and (max-width: ${MEDIUM_BREAKPOINT}px) {
    gap: 14px;
    height: 100%;
    overflow-x: auto;
    &::-webkit-scrollbar {
      display: none;
    }
    margin: 0;
    padding: 0 12px;
    flex-direction: row;
    justify-content: space-between;
    align-items: stretch;
  }
`;
SidebarSections.displayName = 'S.SidebarSections';

export type FancyPageSidebarItemButton = {
  type?: 'button';

  iconName: IconName;
  name: string;
  nameTooltip?: string;
  slug: string;

  // Some buttons should get active highlighting for multiple different slugs.
  additionalSlugs?: string[];

  externalLink?: string;

  onClick?: () => void;
  /**
   * @deprecated Pass children to FancyPage instead to define rendered page contents
   */
  render?: () => React.ReactNode;

  isDisabled?: boolean;
};

export type FancyPageSidebarItemMenuPlaceholder = {
  type: 'menuPlaceholder';
  key: string;
  menu: string[];
};

export type FancyPageSidebarItemMenu = {
  type: 'menu';
  key: string;
  menu: FancyPageSidebarItemButton[];
};

type FancyPageSidebarItemLabel = {
  type: 'label';
  label: string;
};
type FancyPageSidebarItemDivider = {
  type: 'divider';
  key: string;
};

export type FancyPageSidebarItem =
  | FancyPageSidebarItemButton
  | FancyPageSidebarItemMenu
  | FancyPageSidebarItemLabel
  | FancyPageSidebarItemDivider;

type FancyPageSidebarProps = {
  selectedItem?: FancyPageSidebarItem;
  items: FancyPageSidebarItem[];
  baseUrl: string;
};

export const FancyPageSidebar = (props: FancyPageSidebarProps) => {
  // TODO: We previously would hide the sidebar if there were 0 or 1 items,
  //       took that out to better handle the fact that there is a loading delay.
  //       We could consider putting it back in.
  return (
    <Sidebar className="fancy-page__sidebar">
      <SidebarSections>
        <FancyPageSidebarSection
          selectedItem={props.selectedItem}
          items={props.items}
          baseUrl={props.baseUrl}
        />
      </SidebarSections>
    </Sidebar>
  );
};
