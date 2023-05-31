import * as globals from '@wandb/weave/common/css/globals.styles';
import {NodeOrVoidNode, voidNode} from '@wandb/weave/core';
import {
  useMakeMutation,
  useMutation,
  useNodeWithServerType,
} from '@wandb/weave/react';
import React, {useMemo, useRef, useState} from 'react';
import {useCallback} from 'react';
import {Button, Input, Modal} from 'semantic-ui-react';

import {
  branchPointIsRemote,
  isLocalURI,
  uriFromNode,
  useIsAuthenticated,
  weaveTypeIsPanel,
  determineURISource,
  determineURIIdentifier,
  BranchPointType,
} from './util';
import {
  IconAddNew,
  IconDelete,
  IconDocs,
  IconDown,
  IconLeftArrow,
  IconPencilEdit,
  IconStack,
  IconSystem,
  IconUndo,
  IconUp,
  IconWeaveLogo,
} from '../Panel2/Icons';
import styled from 'styled-components';
import {Popover} from '@material-ui/core';
import moment from 'moment';
import {useNewPanelFromRootQueryCallback} from '../Panel2/PanelRootBrowser/util';
import {
  useBranchPointFromURIString,
  usePreviousVersionFromURIString,
} from './hooks';
import {
  PersistenceAction,
  PersistenceRenameActionType,
  PersistenceState,
  PersistenceStoreActionType,
  TakeActionType,
  getAvailableActions,
  useStateMachine,
} from './persistenceStateMachine';
import {WBButton} from '../../common/components/elements/WBButtonNew';

const CustomPopover = styled(Popover)`
  .MuiPaper-root {
    box-shadow: 0px 16px 32px 0px rgba(14, 16, 20, 0.16);
  }
`;

const PersistenceLabel = styled.div`
  color: #76787a;
`;

const PersistenceControlsWrapper = styled.div`
  flex: 1 1 30px;
  display: flex;
  flex-direction: row;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
`;

const HEADER_HEIGHT = 48;

const MainHeaderWrapper = styled.div`
  position: relative;
  flex: 0 0 ${HEADER_HEIGHT}px;
  height: ${HEADER_HEIGHT}px;
  overflow: hidden;
  z-index: 100;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px;
  background-color: ${globals.WHITE};
  border-bottom: 1px solid ${globals.GRAY_350};
  font-size: 15px;
`;

const HeaderCenterControlsPrimary = styled.span`
  font-weight: bold;
`;

const HeaderCenterControlsSecondary = styled.span`
  color: #d5d5d5;
`;

const HeaderCenterControls = styled.div`
  flex: 0 1 auto;
  cursor: pointer;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  font-size: 16px;
`;

const CustomMenu = styled.div`
  /* width: 250px; */
`;

const MenuText = styled.div``;

const MenuIcon = styled.div`
  display: flex;
  flex-direction: row;
  justify-content: center;
  width: 16px;
  height: 100%;
`;

const MenuItem = styled.div<{hasBorder?: boolean}>`
  display: flex;
  flex-direction: row;
  justify-content: left;
  align-items: center;
  padding: 4px 16px;
  gap: 10px;
  cursor: pointer;
  border-bottom: ${props => (props.hasBorder ? '1px solid #ddd;' : 'default')};
  font-size: 15px;

  &:hover {
    background-color: #f5f5f5;
  }
`;

const HeaderLeftControls = styled.div`
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  flex: 1 1 30px;
`;

const WeaveLogo = styled(IconWeaveLogo)`
  width: 32px;
  height: 32px;
  transform: rotate(0deg);
  transition: all 0.3s ease-out;
  transform: ${props => (props.rotate ? `rotate(180deg)` : '')};
`;

export const PersistenceManager: React.FC<{
  inputNode: NodeOrVoidNode;
  updateNode: (node: NodeOrVoidNode) => void;
  goHome?: () => void;
}> = props => {
  const maybeURI = uriFromNode(props.inputNode);
  const branchPoint = useBranchPointFromURIString(maybeURI);
  const hasRemote = branchPointIsRemote(branchPoint);

  const {nodeState, takeAction, acting} = useStateMachine(
    props.inputNode,
    props.updateNode,
    hasRemote
  );

  const isAuthenticated = useIsAuthenticated();
  const availableActions = useMemo(
    () => getAvailableActions(nodeState, isAuthenticated),
    [nodeState, isAuthenticated]
  );

  const headerRef = useRef<HTMLDivElement>(null);

  return (
    <MainHeaderWrapper ref={headerRef}>
      <HeaderLogoControls
        inputNode={props.inputNode}
        updateNode={props.updateNode}
        headerEl={headerRef.current}
        goHome={props.goHome}
      />

      {maybeURI && (
        <HeaderFileControls
          inputNode={props.inputNode}
          updateNode={props.updateNode}
          headerEl={headerRef.current}
          maybeURI={maybeURI}
          branchPoint={branchPoint}
          renameAction={availableActions.renameAction}
          takeAction={takeAction}
          goHome={props.goHome}
        />
      )}

      <HeaderPersistenceControls
        storeAction={availableActions.storeAction}
        acting={acting}
        takeAction={takeAction}
        nodeState={nodeState}
      />
    </MainHeaderWrapper>
  );
};

const persistenceStateToLabel: {[state in PersistenceState]: string} = {
  local_untracked: 'Unsaved changes',
  local_saved_no_remote: 'Saved',
  local_uncommitted_with_remote: 'Uncommitted changes',
  local_published: 'Published',
  cloud_untracked: 'Unsaved changes',
  cloud_saved_no_remote: 'Not published',
  cloud_uncommitted_with_remote: 'Uncommitted changes',
  cloud_published: 'Published',
};

const persistenceActionToLabel: {[action in PersistenceAction]: string} = {
  save: 'Make object',
  commit: 'Commit',
  rename_local: 'Rename',
  publish_as: 'Publish As',
  publish_new: 'Publish',
  rename_remote: 'Rename',
};

const HeaderPersistenceControls: React.FC<{
  storeAction: PersistenceStoreActionType | null;
  acting: boolean;
  nodeState: PersistenceState;
  takeAction: TakeActionType;
}> = ({storeAction, acting, takeAction, nodeState}) => {
  return (
    <PersistenceControlsWrapper>
      {acting ? (
        <WBButton loading variant={`confirm`}>
          Working
        </WBButton>
      ) : storeAction ? (
        <>
          <PersistenceLabel>
            {persistenceStateToLabel[nodeState]}
          </PersistenceLabel>
          <WBButton
            variant={`confirm`}
            onClick={() => {
              takeAction(storeAction);
            }}>
            {persistenceActionToLabel[storeAction]}
          </WBButton>
        </>
      ) : (
        <WBButton disabled variant={`plain`}>
          {persistenceStateToLabel[nodeState]}
        </WBButton>
      )}
    </PersistenceControlsWrapper>
  );
};

const HeaderFileControls: React.FC<{
  inputNode: NodeOrVoidNode;
  headerEl: HTMLElement | null;
  maybeURI: string | null;
  renameAction: PersistenceRenameActionType | null;
  takeAction: TakeActionType;
  branchPoint: BranchPointType | null;
  updateNode: (node: NodeOrVoidNode) => void;
  goHome?: () => void;
}> = ({
  inputNode,
  goHome,
  headerEl,
  maybeURI,
  branchPoint,
  renameAction,
  takeAction,
  updateNode,
}) => {
  const [actionRenameOpen, setActionRenameOpen] = useState(false);
  const [acting, setActing] = useState(false);
  const isLocal = maybeURI != null && isLocalURI(maybeURI);
  const entityProjectName = determineURISource(maybeURI, branchPoint);
  const {name: currName, version: currentVersion} =
    determineURIIdentifier(maybeURI);
  const [anchorFileEl, setAnchorFileEl] = useState<HTMLElement | null>(null);
  const expandedFileControls = Boolean(anchorFileEl);

  const makeMutation = useMakeMutation();
  const deleteCurrentNode = useCallback(async () => {
    if (isLocal) {
      await makeMutation(inputNode, 'delete_artifact', {});
      goHome?.();
    }
  }, [goHome, inputNode, isLocal, makeMutation]);

  const previousVersionURI = usePreviousVersionFromURIString(maybeURI);

  const undoArtifact = useMutation(inputNode, 'undo_artifact', updateNode);

  const onBack = useCallback(() => {
    undoArtifact({});
  }, [undoArtifact]);

  return (
    <>
      <HeaderCenterControls>
        {previousVersionURI && maybeURI && <IconUndo onClick={onBack} />}
        {entityProjectName && (
          <HeaderCenterControlsSecondary
            onClick={() => {
              setAnchorFileEl(headerEl);
            }}>
            {entityProjectName.entity}/{entityProjectName.project}/
          </HeaderCenterControlsSecondary>
        )}
        <HeaderCenterControlsPrimary
          onClick={() => {
            setAnchorFileEl(headerEl);
          }}>
          {currName}
        </HeaderCenterControlsPrimary>
        {expandedFileControls ? (
          <IconUp
            onClick={() => {
              setAnchorFileEl(null);
            }}
          />
        ) : (
          <IconDown
            onClick={() => {
              setAnchorFileEl(headerEl);
            }}
          />
        )}
      </HeaderCenterControls>

      <CustomPopover
        open={expandedFileControls}
        anchorEl={anchorFileEl}
        onClose={() => setAnchorFileEl(null)}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}>
        <CustomMenu>
          {currentVersion && (
            <MenuItem
              hasBorder={true}
              onClick={() => {
                setAnchorFileEl(null);
              }}>
              <MenuIcon>
                <IconSystem />
              </MenuIcon>
              <MenuText>
                Version ({isLocal ? 'Local' : 'W&B'}): {currentVersion}
              </MenuText>
            </MenuItem>
          )}
          {renameAction && (
            <MenuItem
              onClick={() => {
                setAnchorFileEl(null);
                setActionRenameOpen(true);
              }}>
              <MenuIcon>
                <IconPencilEdit />
              </MenuIcon>
              <MenuText>Rename</MenuText>
            </MenuItem>
          )}
          {isLocal && (
            <MenuItem
              onClick={() => {
                setAnchorFileEl(null);
                deleteCurrentNode();
              }}>
              <MenuIcon>
                <IconDelete />
              </MenuIcon>
              <MenuText>Delete</MenuText>
            </MenuItem>
          )}
        </CustomMenu>
      </CustomPopover>

      {renameAction && (
        <RenameActionModal
          currName={currName ?? ''}
          acting={acting}
          actionName={renameAction}
          open={actionRenameOpen}
          onClose={() => setActionRenameOpen(false)}
          onRename={newName => {
            setActing(true);
            takeAction(renameAction, {name: newName}, () => {
              setActing(false);
              setActionRenameOpen(false);
            });
          }}
        />
      )}
    </>
  );
};

const HeaderLogoControls: React.FC<{
  inputNode: NodeOrVoidNode;
  updateNode: (node: NodeOrVoidNode) => void;
  headerEl: HTMLElement | null;
  goHome?: () => void;
}> = ({inputNode, updateNode, headerEl, goHome}) => {
  const inputType = useNodeWithServerType(inputNode).result?.type;
  const isPanel = weaveTypeIsPanel(inputType || ('any' as const));
  const [anchorHomeEl, setAnchorHomeEl] = useState<HTMLElement | null>(null);
  const expandedHomeControls = Boolean(anchorHomeEl);

  const name =
    (isPanel ? 'dashboard' : 'object') +
    '-' +
    moment().format('YY_MM_DD_hh_mm_ss');
  const makeNewDashboard = useNewPanelFromRootQueryCallback();
  const newDashboard = useCallback(() => {
    const node = isPanel ? voidNode() : inputNode;

    makeNewDashboard(name, node, true, newDashExpr => {
      updateNode(newDashExpr);
    });
  }, [inputNode, isPanel, makeNewDashboard, name, updateNode]);

  return (
    <>
      <HeaderLeftControls
        onClick={e => {
          setAnchorHomeEl(headerEl);
        }}>
        <WeaveLogo />
        {expandedHomeControls ? <IconUp /> : <IconDown />}
      </HeaderLeftControls>
      <CustomPopover
        open={expandedHomeControls}
        anchorEl={anchorHomeEl}
        onClose={() => setAnchorHomeEl(null)}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}>
        <CustomMenu>
          <MenuItem
            hasBorder={true}
            onClick={() => {
              setAnchorHomeEl(null);
              goHome?.();
            }}>
            <MenuIcon>
              <IconLeftArrow />
            </MenuIcon>
            <MenuText>Back to boards</MenuText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              setAnchorHomeEl(null);
              newDashboard();
            }}>
            <MenuIcon>
              <IconAddNew />
            </MenuIcon>
            <MenuText>{isPanel ? 'Start' : 'Seed'} new board</MenuText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              setAnchorHomeEl(null);
              window.open('https://github.com/wandb/weave-internal', '_blank');
            }}>
            <MenuIcon>
              <IconDocs />
            </MenuIcon>
            <MenuText>Weave documentation</MenuText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              setAnchorHomeEl(null);
              window.open('https://github.com/wandb/weave-internal', '_blank');
            }}>
            <MenuIcon>
              <IconStack />
            </MenuIcon>
            <MenuText>Weave 0.0.6</MenuText>
          </MenuItem>
        </CustomMenu>
      </CustomPopover>
    </>
  );
};

const RenameActionModal: React.FC<{
  actionName: string;
  currName: string;
  acting: boolean;
  open: boolean;
  onClose: () => void;
  onRename: (newName: string) => void;
}> = props => {
  const [newName, setNewName] = useState(props.currName || '');
  return (
    <Modal
      open={props.open}
      size="mini"
      content={
        <div
          style={{padding: 24, display: 'flex', flexDirection: 'column'}}
          onKeyUp={e => {
            if (e.key === 'Enter') {
              props.onRename(newName);
            }
          }}>
          <div style={{marginBottom: 24, fontWeight: 'bold'}}>Name</div>
          <Input
            style={{marginBottom: 24}}
            value={newName}
            onChange={(e, {value}) => setNewName(value)}
          />
          <div style={{display: 'flex', justifyContent: 'space-between'}}>
            {props.acting ? (
              <div>Working...</div>
            ) : (
              <>
                <Button onClick={() => props.onClose()}>Cancel</Button>
                <Button
                  primary
                  disabled={newName.length < 5}
                  onClick={() => props.onRename(newName)}>
                  {
                    persistenceActionToLabel[
                      props.actionName as PersistenceAction
                    ]
                  }
                </Button>
              </>
            )}
          </div>
        </div>
      }
    />
  );
};
