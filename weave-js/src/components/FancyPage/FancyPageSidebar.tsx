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

export type FancyPageSidebarItem = {
  iconName: IconName;
  name: string;
  nameTooltip?: string;
  slug?: string;
  externalLink?: string;
  onClick?: () => void;
  /**
   * @deprecated Pass children to FancyPage instead to define rendered page contents
   */
  render?: () => React.ReactNode;
  /**
   * Enables multiple sections with dividers in between. Defaults to 0.
   */
  sectionIndex?: number;

  isDisabled?: boolean;
};

type FancyPageSidebarProps = {
  selectedItem?: FancyPageSidebarItem;
  items: FancyPageSidebarItem[];
  baseUrl: string;
};

export const FancyPageSidebar = (props: FancyPageSidebarProps) => {
  if (props.items.length < 2) {
    return <></>;
  }

  const sections = new Set<number>();
  props.items.forEach(item => {
    sections.add(item.sectionIndex || 0);
  });

  return (
    <Sidebar className="fancy-page__sidebar">
      <SidebarSections>
        {Array.from(sections)
          .sort()
          .map((section, i) => (
            <React.Fragment key={'section__' + i}>
              {i !== 0 && (
                <div className="fancy-page__sidebar__sections__divider" />
              )}
              <FancyPageSidebarSection
                selectedItem={props.selectedItem}
                items={props.items.filter(
                  item => section === (item.sectionIndex || 0)
                )}
                baseUrl={props.baseUrl}
              />
            </React.Fragment>
          ))}
      </SidebarSections>
    </Sidebar>
  );
};
