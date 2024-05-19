import React, {SVGProps} from 'react';

import {ReactComponent as AddNew} from '../../assets/icon-add-new.svg';
import {ReactComponent as ImportIconBack} from '../../assets/icon-back.svg';
import {ReactComponent as ImportIconCaret} from '../../assets/icon-caret.svg';
import {ReactComponent as Checkmark} from '../../assets/icon-checkmark.svg';
import {ReactComponent as DownSVGRaw} from '../../assets/icon-chevron-down.svg';
import {ReactComponent as NextSVGRaw} from '../../assets/icon-chevron-next.svg';
import {ReactComponent as UpSVGRaw} from '../../assets/icon-chevron-up.svg';
import {ReactComponent as ImportIconClose} from '../../assets/icon-close.svg';
import {ReactComponent as ImportIconColumnAlt} from '../../assets/icon-column-alt.svg';
import {ReactComponent as ImportIconCopy} from '../../assets/icon-copy.svg';
import {ReactComponent as DashboardBlackboard} from '../../assets/icon-dashboard-blackboard.svg';
import {ReactComponent as Delete} from '../../assets/icon-delete.svg';
import {ReactComponent as Docs} from '../../assets/icon-docs.svg';
import {ReactComponent as ToolSVGRaw} from '../../assets/icon-flash-bolt.svg';
import {ReactComponent as PromptSVGRaw} from '../../assets/icon-forum-chat-bubble.svg';
import {ReactComponent as ImportIconFullScreenModeExpand} from '../../assets/icon-full-screen-mode-expand.svg';
import {ReactComponent as Home} from '../../assets/icon-home.svg';
import {ReactComponent as Info} from '../../assets/icon-info.svg';
import {ReactComponent as LaptopLocalComputer} from '../../assets/icon-laptop-local-computer.svg';
import {ReactComponent as ChainSVGRaw} from '../../assets/icon-link-alt.svg';
import {ReactComponent as ImportIconMinimizeMode} from '../../assets/icon-minimize-mode.svg';
import {ReactComponent as LLMSVGRaw} from '../../assets/icon-model.svg';
import {ReactComponent as OpenNewTab} from '../../assets/icon-open-new-tab.svg';
import {ReactComponent as ImportIconOverflowHorizontal} from '../../assets/icon-overflow-horizontal.svg';
import {ReactComponent as PencilEdit} from '../../assets/icon-pencil-edit.svg';
import {ReactComponent as ImportIconRedo} from '../../assets/icon-redo.svg';
import {ReactComponent as AgentSVGRaw} from '../../assets/icon-robot-service-member.svg';
import {ReactComponent as ImportIconSplit} from '../../assets/icon-split.svg';
import {ReactComponent as Table} from '../../assets/icon-table.svg';
import {ReactComponent as ImportIconUndo} from '../../assets/icon-undo.svg';
import {ReactComponent as UserProfilePersonal} from '../../assets/icon-user-profile-personal.svg';
import {ReactComponent as UsersTeam} from '../../assets/icon-users-team.svg';
import {ReactComponent as ImportIconWeave} from '../../assets/icon-weave.svg';
import {ReactComponent as WeaveLogo} from '../../assets/icon-weave-logo.svg';
import {ReactComponent as WeaveLogoGray} from '../../assets/icon-weave-logo-gray.svg';

type SVGIconProps = SVGProps<SVGElement>;
const updateIconProps = (props: SVGIconProps) => {
  return {
    width: 20,
    height: 20,
    ...props,
  };
};

export const IconBack = (props: SVGIconProps) => (
  <ImportIconBack {...updateIconProps(props)} />
);
export const IconCaret = (props: SVGIconProps) => (
  <ImportIconCaret {...updateIconProps(props)} />
);
export const IconClose = (props: SVGIconProps) => (
  <ImportIconClose {...updateIconProps(props)} />
);
export const IconColumnAlt = (props: SVGIconProps) => (
  <ImportIconColumnAlt {...updateIconProps(props)} />
);
export const IconCopy = (props: SVGIconProps) => (
  <ImportIconCopy {...updateIconProps(props)} />
);
export const IconFullScreenModeExpand = (props: SVGIconProps) => (
  <ImportIconFullScreenModeExpand {...updateIconProps(props)} />
);
export const IconMinimizeMode = (props: SVGIconProps) => (
  <ImportIconMinimizeMode {...updateIconProps(props)} />
);
export const IconOverflowHorizontal = (props: SVGIconProps) => (
  <ImportIconOverflowHorizontal {...updateIconProps(props)} />
);
export const IconRedo = (props: SVGIconProps) => (
  <ImportIconRedo {...updateIconProps(props)} />
);
export const IconSplit = (props: SVGIconProps) => (
  <ImportIconSplit {...updateIconProps(props)} />
);
export const IconUndo = (props: SVGIconProps) => (
  <ImportIconUndo {...updateIconProps(props)} />
);
export const IconWeave = (props: SVGIconProps) => (
  <ImportIconWeave {...updateIconProps(props)} />
);

export const IconWeaveLogo = (props: SVGIconProps) => (
  <WeaveLogo {...updateIconProps(props)} />
);

export const IconWeaveLogoGray = (props: SVGIconProps) => (
  <WeaveLogoGray {...updateIconProps(props)} />
);

export const IconUp = (props: SVGIconProps) => (
  <UpSVGRaw {...updateIconProps(props)} />
);

export const IconDown = (props: SVGIconProps) => (
  <DownSVGRaw {...updateIconProps(props)} />
);
export const IconDocs = (props: SVGIconProps) => (
  <Docs {...updateIconProps(props)} />
);
export const IconDelete = (props: SVGIconProps) => (
  <Delete {...updateIconProps(props)} />
);
export const IconPencilEdit = (props: SVGIconProps) => (
  <PencilEdit {...updateIconProps(props)} />
);
export const IconTable = (props: SVGIconProps) => (
  <Table {...updateIconProps(props)} />
);
export const IconAddNew = (props: SVGIconProps) => (
  <AddNew {...updateIconProps(props)} />
);
export const IconOpenNewTab = (props: SVGIconProps) => (
  <OpenNewTab {...updateIconProps(props)} />
);
export const IconHome = (props: SVGIconProps) => (
  <Home {...updateIconProps(props)} />
);
export const IconCheckmark = (props: SVGIconProps) => (
  <Checkmark {...updateIconProps(props)} />
);
export const IconDashboardBlackboard = (props: SVGIconProps) => (
  <DashboardBlackboard {...updateIconProps(props)} />
);
export const IconInfo = (props: SVGIconProps) => (
  <Info {...updateIconProps(props)} />
);
export const IconLaptopLocalComputer = (props: SVGIconProps) => (
  <LaptopLocalComputer {...updateIconProps(props)} />
);
export const IconUsersTeam = (props: SVGIconProps) => (
  <UsersTeam {...updateIconProps(props)} />
);
export const IconUserProfilePersonal = (props: SVGIconProps) => (
  <UserProfilePersonal {...updateIconProps(props)} />
);

const style = {
  verticalAlign: 'top',
  display: 'inline-block',
  margin: '1px 5px 0px 0px',
};

export const AgentSVG: React.FC = () => {
  return <AgentSVGRaw style={style} />;
};

export const ToolSVG: React.FC = () => {
  return <ToolSVGRaw style={style} />;
};

export const ChainSVG: React.FC = () => {
  return <ChainSVGRaw style={style} />;
};

export const LLMSVG: React.FC = () => {
  return <LLMSVGRaw style={style} />;
};

export const PromptSVG: React.FC = () => {
  return <PromptSVGRaw style={style} />;
};

export const DownSVG: React.FC = () => {
  return <DownSVGRaw style={style} />;
};

export const NextSVG: React.FC = () => {
  return <NextSVGRaw style={style} />;
};
