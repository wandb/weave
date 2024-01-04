import * as globals from '@wandb/weave/common/css/globals.styles';
import * as _ from 'lodash';
import React, {useCallback, useState} from 'react';
import styled, {css} from 'styled-components';

import {Icon, IconHideHidden, IconLockClosed} from '../Icon';
import {IconButton} from '../IconButton';
import {getPanelStacksForType} from '../Panel2/availablePanels';
import {ChildPanelConfig, ChildPanelFullConfig} from '../Panel2/ChildPanel';
import {
  IconCaret as IconCaretUnstyled,
  IconOverflowHorizontal as IconOverflowHorizontalUnstyled,
} from '../Panel2/Icons';
import {PanelGroupConfig} from '../Panel2/PanelGroup';
import {
  usePanelIsHoveredByPath,
  useSetPanelIsHoveredInOutline,
} from '../Panel2/PanelInteractContext';
import {getPanelIcon} from '../Panel2/PanelRegistry';
import {panelChildren} from '../Panel2/panelTree';
import {Tooltip} from '../Tooltip';
import {OutlineItemPopupMenu} from './OutlineItemPopupMenu';

const OutlineItem = styled.div``;
OutlineItem.displayName = 'S.OutlineItem';

const OutlineItemMenuButton = styled(IconButton).attrs({small: true})`
  flex-shrink: 0;
  margin: 0 8px 0 4px;
`;
OutlineItemMenuButton.displayName = 'S.OutlineItemMenuButton';

const OutlineItemTitle = styled.div<{level: number; panelIsHovered: boolean}>`
  display: flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
  padding-top: 4px;
  padding-bottom: 4px;
  padding-left: ${p => p.level * 11 + 8}px;
  line-height: 130%;

  &:hover {
    background-color: ${globals.GRAY_50};
  }
  ${p =>
    p.panelIsHovered &&
    css`
      background-color: ${globals.GRAY_50};
    `}

  &:not(:hover) ${OutlineItemMenuButton} {
    visibility: hidden;
  }
`;
OutlineItemTitle.displayName = 'S.OutlineItemTitle';

const OutlineItemToggle = styled.div<{expanded: boolean}>`
  flex-shrink: 0;
  display: flex;
  width: 18px;
  margin-right: 4px;
  cursor: pointer;
  transform: rotate(${p => (p.expanded ? 0 : -90)}deg);

  color: ${globals.GRAY_500};
  &:hover {
    color: ${globals.GRAY_600};
    background-color: ${globals.GRAY_50};
  }
`;
OutlineItemToggle.displayName = 'S.OutlineItemToggle';

const OutlineItemIcon = styled.div`
  flex-shrink: 0;
  display: flex;
  margin-right: 8px;
`;
OutlineItemIcon.displayName = 'S.OutlineItemIcon';

const OutlineItemName = styled.div`
  flex-shrink: 0;
  overflow-wrap: break-word;
`;
OutlineItemName.displayName = 'S.OutlineItemName';

const OutlineItemPanelID = styled.div`
  color: ${globals.MOON_450};
  font-size: 15px;
  font-family: 'Inconsolata', monospace;
  margin-left: 10px;
  flex-grow: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;
OutlineItemPanelID.displayName = 'S.OutlineItemPanelID';

const iconStyles = css`
  height: 18px;
  width: 18px;
`;

const IconCaret = styled(IconCaretUnstyled)`
  ${iconStyles}
`;
IconCaret.displayName = 'S.IconCaret';

const IconOverflowHorizontal = styled(IconOverflowHorizontalUnstyled)`
  ${iconStyles}
`;
IconOverflowHorizontal.displayName = 'S.IconOverflowHorizontal';

export type OutlinePanelProps = OutlineProps & {
  name: string;
  localConfig: ChildPanelFullConfig;
  path: string[];
  level?: number;
};

export const shouldDisablePanelDelete = (
  config: ChildPanelFullConfig,
  path: string[]
) =>
  (config?.id === 'Group' && config?.config.disableDeletePanel) ||
  // This exclusion below was added July 2023
  // all future dashboards should have the disableDeletePanel flag set to true for root, main, and sidebar to not need the below
  // we can remove the 2 lines below in like 6 months
  path.length === 0 ||
  (path.length === 1 && ['main', 'sidebar'].includes(path[0]));

const getPanelTypeIcon = (panelId: string | undefined) => {
  if (!panelId) {
    return 'panel';
  }
  if (panelId.startsWith('row.')) {
    panelId = panelId.slice(4);
  }
  if (panelId.startsWith('maybe.')) {
    panelId = panelId.slice(6);
  }
  return getPanelIcon(panelId);
};

const OutlinePanel: React.FC<OutlinePanelProps> = props => {
  const {
    name,
    localConfig,
    selected,
    setSelected,
    path,
    config,
    updateConfig,
    updateConfig2,
    level = 0,
  } = props;

  const panelIsHovered = usePanelIsHoveredByPath(path);
  const setPanelIsHoveredInOutline = useSetPanelIsHoveredInOutline();

  const curPanelId = getPanelStacksForType(
    localConfig?.input_node?.type ?? 'invalid',
    localConfig?.id
  ).curPanelId;
  const children = panelChildren(localConfig); // TODO: curPanelId!

  const [expanded, setExpanded] = useState(true);
  const [isOutlineMenuOpen, setIsOutlineMenuOpen] = useState(false);

  const toggleExpanded = useCallback(() => {
    if (children != null) {
      setExpanded(prev => !prev);
    }
  }, [children]);

  const iconName = getPanelTypeIcon(curPanelId);
  const shouldHideMenu = shouldDisablePanelDelete(localConfig, path);
  const isPanelHidden = config.config.panelInfo?.[name]?.hidden;

  return (
    <OutlineItem>
      <OutlineItemTitle
        level={level}
        panelIsHovered={panelIsHovered}
        onClick={() => {
          setSelected(path);
          setPanelIsHoveredInOutline(path, false);
        }}
        onMouseEnter={() => {
          setPanelIsHoveredInOutline(path, true);
        }}
        onMouseLeave={() => {
          setPanelIsHoveredInOutline(path, false);
        }}>
        <OutlineItemToggle
          expanded={expanded}
          onClick={e => {
            e.stopPropagation();
            toggleExpanded();
          }}>
          {children != null && <IconCaret />}
        </OutlineItemToggle>
        <OutlineItemIcon>
          <Tooltip
            trigger={
              <Icon
                name={iconName}
                width={18}
                height={18}
                color={globals.MOON_400}
              />
            }
            content={curPanelId}
          />
        </OutlineItemIcon>

        <OutlineItemName>{name}</OutlineItemName>
        <OutlineItemPanelID>{curPanelId}</OutlineItemPanelID>
        {shouldHideMenu ? (
          <Tooltip
            content={`The ${name} panel is a structural component of the board and cannot be edited.`}
            trigger={
              <OutlineItemMenuButton>
                <IconLockClosed />
              </OutlineItemMenuButton>
            }
          />
        ) : (
          <OutlineItemPopupMenu
            config={config}
            localConfig={localConfig}
            path={path}
            updateConfig={updateConfig}
            updateConfig2={updateConfig2}
            trigger={
              <OutlineItemMenuButton onClick={e => e.stopPropagation()}>
                <IconOverflowHorizontal />
              </OutlineItemMenuButton>
            }
            isOpen={isOutlineMenuOpen}
            onOpen={() => setIsOutlineMenuOpen(true)}
            onClose={() => setIsOutlineMenuOpen(false)}
          />
        )}
        {isPanelHidden && (
          <Tooltip
            content="This panel is a part of the group but it is hidden from view."
            trigger={
              <IconHideHidden
                style={{marginRight: '10px'}}
                color={globals.MOON_500}
                height={18}
                width={18}
              />
            }
          />
        )}
      </OutlineItemTitle>
      {expanded &&
        children != null &&
        _.map(children, (conf, key) => (
          <OutlinePanel
            key={key}
            name={key}
            // root config is passed all the way down so we can operate on the whole thing
            config={props.config}
            localConfig={conf}
            updateConfig={props.updateConfig}
            updateConfig2={props.updateConfig2}
            selected={selected}
            setSelected={setSelected}
            path={[...path, key]}
            level={level + 1}
          />
        ))}
    </OutlineItem>
  );
};

export interface OutlineProps {
  config: ChildPanelFullConfig<PanelGroupConfig>;
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  updateConfig2: (
    change: (oldConfig: ChildPanelConfig) => ChildPanelFullConfig
  ) => void;
  selected: string[];
  setSelected: (path: string[]) => void;
}

export const Outline: React.FC<OutlineProps> = props => {
  return (
    <OutlineContainer>
      <OutlinePanel
        name="root"
        // root config is passed all the way down so we can operate on the whole thing
        config={props.config}
        updateConfig={props.updateConfig}
        updateConfig2={props.updateConfig2}
        localConfig={props.config}
        selected={props.selected}
        setSelected={props.setSelected}
        path={[]}
      />
    </OutlineContainer>
  );
};

const OutlineContainer = styled.div`
  padding: 8px 0;
`;
OutlineContainer.displayName = 'S.OutlineContainer';
