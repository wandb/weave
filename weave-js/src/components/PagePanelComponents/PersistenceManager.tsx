import {useMutation as useApolloMutation} from '@apollo/client';
import Popover from '@mui/material/Popover';
import {KeyboardShortcut} from '@wandb/weave/common/components/elements/KeyboardShortcut';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {WBButton} from '@wandb/weave/common/components/elements/WBButtonNew';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {isMac} from '@wandb/weave/common/util/browser';
import {useIsAuthenticated} from '@wandb/weave/context/WeaveViewerContext';
import {
  constString,
  isConstNode,
  isOutputNode,
  mapNodes,
  NodeOrVoidNode,
  opGet,
  opProjectArtifact,
  opRootProject,
  OutputNode,
  varNode,
  voidNode,
} from '@wandb/weave/core';
import {opWeaveServerVersion} from '@wandb/weave/core/ops/primitives/server';
import {useMutation, useNodeWithServerType} from '@wandb/weave/react';
import {useNodeValue} from '@wandb/weave/react';
import {urlProjectAssets} from '@wandb/weave/urls';
import {trackPublishBoardClicked} from '@wandb/weave/util/events';
import _ from 'lodash';
import moment from 'moment';
import React, {
  Dispatch,
  SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';
import {Button, Input, Modal} from 'semantic-ui-react';
import styled, {css} from 'styled-components';

import {getFullChildPanel} from '../Panel2/ChildPanel';
import {
  IconAddNew,
  IconBack,
  IconCopy,
  IconDelete,
  IconDocs,
  IconDown as IconDownUnstyled,
  IconPencilEdit,
  IconRedo,
  IconUndo,
  IconUp as IconUpUnstyled,
  IconWeaveLogo,
} from '../Panel2/Icons';
import {PanelGroupConfig} from '../Panel2/PanelGroup';
import {
  useNewDashFromItems,
  useNewPanelFromRootQueryCallback,
} from '../Panel2/PanelRootBrowser/util';
import {mapPanels} from '../Panel2/panelTree';
import {DeleteActionModal} from './DeleteActionModal';
import {UPDATE_ARTIFACT_COLLECTION} from './graphql';
import {DELETE_ARTIFACT_SEQUENCE} from './graphql';
import {
  useBranchPointFromURIString,
  usePreviousVersionFromURIString,
} from './hooks';
import {
  getAvailableActions,
  PersistenceAction,
  PersistenceDeleteActionType,
  PersistenceRenameActionType,
  PersistenceState,
  PersistenceStoreActionType,
  TakeActionType,
  useStateMachine,
} from './persistenceStateMachine';
import {PublishModal} from './PublishModal';
import {
  branchPointIsRemote,
  BranchPointType,
  determineURIIdentifier,
  determineURISource,
  isLocalURI,
  uriFromNode,
  weaveTypeIsPanel,
  weaveTypeIsPanelGroup,
} from './util';

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

const iconStyles = css`
  color: ${globals.GRAY_500};
  width: 18px;
  height: 18px;
`;
const IconUp = styled(IconUpUnstyled)`
  ${iconStyles}
`;
const IconDown = styled(IconDownUnstyled)`
  ${iconStyles}
`;

const controlsStyles = css`
  &:hover {
    ${IconUp}, ${IconDown} {
      color: ${globals.GRAY_800};
    }
  }
`;

const HeaderCenterControlsPrimary = styled.span`
  font-weight: 600;
`;

const HeaderCenterControlsSecondary = styled.span`
  color: ${globals.GRAY_500};
`;

const HeaderCenterControls = styled.div`
  ${controlsStyles}
  flex: 0 1 auto;
  cursor: pointer;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  font-size: 16px;
`;

const CustomMenu = styled.div<{width?: number}>`
  padding: 8px 0;
  ${p =>
    p.width != null &&
    css`
      width: ${p.width}px;
    `}
`;

const MenuItem = styled.div<{disabled?: boolean; noIcon?: boolean}>`
  display: flex;
  flex-direction: row;
  justify-content: left;
  align-items: center;
  padding: 4px 16px 4px ${p => (p.noIcon ? 18 : 16)}px;
  gap: 10px;
  font-size: 15px;

  ${p =>
    p.disabled
      ? css`
          color: ${globals.GRAY_500};
        `
      : css`
          cursor: pointer;
          &:hover {
            background-color: #f5f5f5;
          }
        `}
`;

const MenuIcon = styled.div`
  width: 18px;
  height: 18px;
  svg {
    width: 100%;
    height: 100%;
  }
`;

const MenuText = styled.div`
  flex-grow: 1;
`;

const MenuShortcut = styled(KeyboardShortcut).attrs({lightMode: true})``;

const MenuDivider = styled.div`
  height: 1px;
  margin: 6px 0;
  background-color: ${globals.GRAY_350};
`;

const HeaderLeftControls = styled.div`
  ${controlsStyles}
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  flex: 1 1 30px;
`;

const WeaveLogo = styled(IconWeaveLogo).attrs({
  className: 'night-aware',
})<{open: boolean}>`
  width: 32px;
  height: 32px;
  transform: rotate(${props => (props.open ? 180 : 0)}deg);
  transition: transform 0.3s ease-out;
`;

export const PersistenceManager: React.FC<{
  inputNode: NodeOrVoidNode;
  inputConfig: any;
  updateNode: (node: NodeOrVoidNode) => void;
  goHome?: () => void;
}> = props => {
  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);

  const maybeURI = uriFromNode(props.inputNode);
  const branchPoint = useBranchPointFromURIString(maybeURI);
  const hasRemote = branchPointIsRemote(branchPoint);
  const {name: currName} = determineURIIdentifier(maybeURI);

  const {nodeState, takeAction, acting} = useStateMachine(
    props.inputNode,
    props.updateNode,
    hasRemote
  );

  const isAuthenticated = useIsAuthenticated();
  const availableActions = useMemo(
    () => getAvailableActions(nodeState, isAuthenticated ?? false),
    [nodeState, isAuthenticated]
  );

  const headerRef = useRef<HTMLDivElement>(null);
  return (
    <MainHeaderWrapper ref={headerRef}>
      <PublishModal
        defaultName={currName}
        open={isPublishModalOpen}
        acting={acting}
        takeAction={takeAction}
        onClose={() => setIsPublishModalOpen(false)}
      />

      <HeaderLogoControls
        inputNode={props.inputNode}
        inputConfig={props.inputConfig}
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
          deleteAction={availableActions.deleteAction}
          takeAction={takeAction}
          goHome={props.goHome}
        />
      )}

      <HeaderPersistenceControls
        storeAction={availableActions.storeAction}
        acting={acting}
        takeAction={takeAction}
        nodeState={nodeState}
        setIsPublishModalOpen={setIsPublishModalOpen}
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
  commit: 'Publish changes',
  rename_local: 'Rename',
  commit_rename: 'Rename & publish',
  publish_as: 'Publish As',
  publish_new: 'Publish board',
  rename_remote: 'Rename',
  delete_local: 'Delete board',
  delete_remote: 'Delete board',
};

const HeaderPersistenceControls: React.FC<{
  storeAction: PersistenceStoreActionType | null;
  acting: boolean;
  nodeState: PersistenceState;
  takeAction: TakeActionType;
  setIsPublishModalOpen: Dispatch<SetStateAction<boolean>>;
}> = ({storeAction, acting, takeAction, nodeState, setIsPublishModalOpen}) => {
  return (
    <PersistenceControlsWrapper>
      {acting ? (
        <WBButton loading variant="confirm">
          Working
        </WBButton>
      ) : storeAction ? (
        <>
          <PersistenceLabel>
            {persistenceStateToLabel[nodeState]}
          </PersistenceLabel>
          <WBButton
            variant="confirm"
            onClick={() => {
              if (storeAction === 'publish_new') {
                setIsPublishModalOpen(true);
              } else {
                takeAction(storeAction);
              }
              if (storeAction === 'commit') {
                trackPublishBoardClicked('commit-changes', 'board-toolbar');
              }
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
  deleteAction: PersistenceDeleteActionType | null;
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
  deleteAction,
  takeAction,
  updateNode,
}) => {
  const history = useHistory();
  const [actionRenameOpen, setActionRenameOpen] = useState(false);
  const [actionDeleteOpen, setActionDeleteOpen] = useState(false);
  const [acting, setActing] = useState(false);
  const [deleteArtifactCollection] = useApolloMutation(
    DELETE_ARTIFACT_SEQUENCE
  );
  const isLocal = maybeURI != null && isLocalURI(maybeURI);
  const [updateArtifactCollection] = useApolloMutation(
    UPDATE_ARTIFACT_COLLECTION
  );
  const entityProjectName = determineURISource(maybeURI, branchPoint);
  const {name: currName, version: currentVersion} =
    determineURIIdentifier(maybeURI);
  const [anchorFileEl, setAnchorFileEl] = useState<HTMLElement | null>(null);
  const expandedFileControls = Boolean(anchorFileEl);

  const previousVersionURI = usePreviousVersionFromURIString(maybeURI);
  const canUndo = !!(previousVersionURI && maybeURI);
  const undoArtifact = useMutation(inputNode, 'undo_artifact', updateNode);
  const undo = useCallback(() => {
    undoArtifact({});
  }, [undoArtifact]);

  // TODO: Implement redo
  const canRedo = false;
  const redo = useCallback(() => {}, []);

  const inputType = useNodeWithServerType(inputNode).result?.type;
  const isPanel = weaveTypeIsPanel(inputType || ('any' as const));

  const entityName = useMemo(
    () => entityProjectName?.entity ?? '',
    [entityProjectName]
  );

  const projectName = useMemo(
    () => entityProjectName?.project ?? '',
    [entityProjectName]
  );

  const artifactNode = useMemo(() => {
    return opProjectArtifact({
      project: opRootProject({
        entityName: constString(entityName),
        projectName: constString(projectName),
      }),
      artifactName: constString(currName ?? ''),
    } as any);
  }, [entityName, projectName, currName]);

  const artifactNodeValue = useNodeValue(artifactNode, {
    skip: entityName === '' || projectName === '',
  });

  const artifactSequenceID = useMemo(() => {
    return !artifactNodeValue.loading && artifactNodeValue.result
      ? (artifactNodeValue.result.id as any)
      : '';
  }, [artifactNodeValue.result, artifactNodeValue.loading]);

  const renameRemoteBoard = useCallback(
    async (newName: string) => {
      try {
        await updateArtifactCollection({
          variables: {
            artifactSequenceID,
            name: newName,
          },
        });
        // Refresh the board
        const uri = `wandb-artifact:///${entityName}/${projectName}/${newName}:latest/obj`;
        updateNode(opGet({uri: constString(uri)}));
        setActing(false);
        setActionRenameOpen(false);
      } catch (e) {
        console.error('Failed to rename artifact collection.');
        toast('Something went wrong while trying to rename this board.');
      }
    },
    [
      entityName,
      projectName,
      updateNode,
      artifactSequenceID,
      updateArtifactCollection,
    ]
  );

  const resetAfterDeletion = useCallback(() => {
    setActing(false);
    setActionDeleteOpen(false);
    if (entityName && projectName) {
      history.push(urlProjectAssets(entityName, projectName, 'board'));
    } else {
      goHome?.();
    }
  }, [entityName, projectName, history, goHome]);

  const deleteRemoteBoard = useCallback(async () => {
    try {
      await deleteArtifactCollection({
        variables: {
          artifactSequenceID,
        },
      });
    } catch (e) {
      console.error('Failed to delete artifact collection.');
      toast('Something went wrong while trying to delete this board.');
    }
  }, [deleteArtifactCollection, artifactSequenceID]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent): void {
      if ((isMac && !e.metaKey) || (!isMac && !e.ctrlKey)) {
        return;
      }
      if (e.key === `z` && canUndo) {
        undo();
        return;
      }
      if (e.key === `y` && canRedo) {
        redo();
        return;
      }
    }

    document.addEventListener(`keydown`, onKeyDown);
    return () => {
      document.removeEventListener(`keydown`, onKeyDown);
    };
  }, [canUndo, undo, canRedo, redo]);

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

  // TODO: Implement dashboard duplication
  const canDuplicateDashboard = false;
  const duplicateDashboard = useCallback(() => {}, []);

  // TODO: Hiding code export temporarily as it is partially broken */
  // const {onCopy} = useCopyCodeFromURI(maybeURI);

  return (
    <>
      <HeaderCenterControls data-testid="header-center-controls">
        {entityProjectName && (
          <HeaderCenterControlsSecondary
            onClick={() => {
              setAnchorFileEl(headerEl);
            }}>
            {entityName}/{projectName}/
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
        <CustomMenu width={242}>
          {currentVersion && (
            <MenuItem disabled noIcon>
              <MenuText>
                Version ({isLocal ? 'Local' : 'W&B'}): {currentVersion}
              </MenuText>
            </MenuItem>
          )}

          {(renameAction || canUndo || canRedo) && <MenuDivider />}
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
          {canUndo && (
            <MenuItem
              onClick={() => {
                setAnchorFileEl(null);
                undo();
              }}>
              <MenuIcon>
                <IconUndo />
              </MenuIcon>
              <MenuText>Undo</MenuText>
              <MenuShortcut keys={[isMac ? `Cmd` : `Ctrl`, `Z`]} />
            </MenuItem>
          )}
          {canRedo && (
            <MenuItem
              onClick={() => {
                setAnchorFileEl(null);
                redo();
              }}>
              <MenuIcon>
                <IconRedo />
              </MenuIcon>
              <MenuText>Redo</MenuText>
              <MenuShortcut keys={[isMac ? `Cmd` : `Ctrl`, `Y`]} />
            </MenuItem>
          )}

          <MenuDivider />

          {/* TODO: Hiding code export temporarily as it is partially broken */}
          {/* {maybeURI && (
            <MenuItem
              onClick={() => {
                onCopy().finally(() => setAnchorFileEl(null));
              }}>
              <MenuIcon>
                <IconCopy />
              </MenuIcon>
              <MenuText>Copy Code</MenuText>
            </MenuItem>
          )}

          <MenuDivider /> */}

          <MenuItem
            data-testid="new-board-button"
            onClick={() => {
              setAnchorFileEl(null);
              newDashboard();
            }}>
            <MenuIcon>
              <IconAddNew />
            </MenuIcon>
            <MenuText>New board</MenuText>
          </MenuItem>
          {canDuplicateDashboard && (
            <MenuItem
              onClick={() => {
                setAnchorFileEl(null);
                duplicateDashboard();
              }}>
              <MenuIcon>
                <IconCopy />
              </MenuIcon>
              <MenuText>Duplicate board</MenuText>
            </MenuItem>
          )}

          {deleteAction && <MenuDivider />}
          {deleteAction && (
            <MenuItem
              onClick={() => {
                setAnchorFileEl(null);
                setActionDeleteOpen(true);
              }}>
              <MenuIcon>
                <IconDelete />
              </MenuIcon>
              <MenuText>Delete board</MenuText>
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
          onRename={async newName => {
            if (renameAction === 'rename_remote') {
              renameRemoteBoard(newName);
            } else if (renameAction === 'commit_rename') {
              setActing(true);
              takeAction('commit', {name: newName}, () => {
                renameRemoteBoard(newName).then(() => {
                  // console.log("Board renamed successfully.")
                });
              });
            } else {
              takeAction(renameAction, {name: newName});
            }
          }}
        />
      )}
      {deleteAction && (
        <DeleteActionModal
          open={actionDeleteOpen}
          onClose={() => setActionDeleteOpen(false)}
          acting={acting}
          onDelete={async () => {
            setActing(true);
            if (deleteAction === 'delete_remote') {
              await deleteRemoteBoard();
              resetAfterDeletion();
            } else {
              takeAction(deleteAction, {}, resetAfterDeletion);
            }
          }}
        />
      )}
    </>
  );
};

const HeaderLogoControls: React.FC<{
  inputNode: NodeOrVoidNode;
  inputConfig: any;
  updateNode: (node: NodeOrVoidNode) => void;
  headerEl: HTMLElement | null;
  goHome?: () => void;
}> = ({inputNode, headerEl, goHome, updateNode, inputConfig}) => {
  const [anchorHomeEl, setAnchorHomeEl] = useState<HTMLElement | null>(null);
  const expandedHomeControls = Boolean(anchorHomeEl);

  return (
    <>
      <HeaderLeftControls
        onClick={e => {
          setAnchorHomeEl(headerEl);
        }}>
        <WeaveLogo open={anchorHomeEl != null} />
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
        <HeaderLogoPopoverContent
          inputNode={inputNode}
          inputConfig={inputConfig}
          updateNode={updateNode}
          goHome={goHome}
          onClose={() => setAnchorHomeEl(null)}
        />
      </CustomPopover>
    </>
  );
};

const HeaderLogoPopoverContent: React.FC<{
  inputNode: NodeOrVoidNode;
  inputConfig: any;
  updateNode: (node: NodeOrVoidNode) => void;
  goHome?: () => void;
  onClose: () => void;
}> = ({inputNode, goHome, updateNode, inputConfig, onClose}) => {
  const inputType = useNodeWithServerType(inputNode).result?.type;
  const isPanel = weaveTypeIsPanel(inputType || ('any' as const));
  const isGroup = weaveTypeIsPanelGroup(inputType);
  const seedItems = useMemo(() => {
    if (isGroup) {
      const groupConfig: PanelGroupConfig | null = inputConfig?.config;
      if (groupConfig == null) {
        return null;
      }
      const isDash =
        isGroup &&
        'sidebar' in groupConfig.items &&
        'main' in groupConfig.items;
      if (isDash) {
        return null;
      }
      return _.mapValues(groupConfig.items, getFullChildPanel);
    } else if (isPanel) {
      return {panel0: getFullChildPanel(inputConfig)};
    } else {
      return {panel0: getFullChildPanel(inputNode)};
    }
  }, [inputConfig, inputNode, isGroup, isPanel]);

  const {processedSeedItems, vars} = useMemo(() => {
    const varMap: {[uri: string]: {name: string; node: NodeOrVoidNode}} = {};
    const names = new Set<string>();
    const processedSeedItemsInner = _.mapValues(seedItems, (item, key) => {
      return mapPanels(item, [], (panelNode, stack) => {
        const {input_node} = panelNode;
        const newInputNode = mapNodes(input_node, inNode => {
          if (isOutputNode(inNode) && inNode.fromOp.name === 'get') {
            const uriNode = inNode.fromOp.inputs.uri;
            if (uriNode != null && isConstNode(uriNode)) {
              const uriVal = uriNode.val;
              if (uriVal != null && typeof uriVal === 'string') {
                if (!(uriVal in varMap)) {
                  const baseNameParts = uriVal.split(':')[1].split('/');
                  let baseName = baseNameParts[baseNameParts.length - 1];
                  baseName = baseName.replace(/[^a-z0-9_]/gi, '_');
                  //  if the first character is not a letter, prepend `v_`
                  if (!/^[a-z]/i.test(baseName)) {
                    baseName = 'v_' + baseName;
                  }
                  let count = 0;
                  let varName = baseName + '_' + count;
                  while (names.has(varName)) {
                    count++;
                    varName = baseName + '_' + count;
                  }
                  names.add(varName);

                  varMap[uriVal] = {
                    name: varName,
                    node: inNode,
                  };
                }
                return varNode(inNode.type, varMap[uriVal].name);
              }
            }
          }
          return inNode;
        });
        return {
          ...panelNode,
          input_node: newInputNode as NodeOrVoidNode,
        };
      });
    });
    const varsInner = _.fromPairs(
      Object.entries(varMap).map(([uri, {name: varMapName, node}]) => {
        return [varMapName, node];
      })
    );
    return {processedSeedItems: processedSeedItemsInner, vars: varsInner};
  }, [seedItems]);

  const name = 'dashboard-' + moment().format('YY_MM_DD_hh_mm_ss');
  const makeNewDashboard = useNewDashFromItems();
  const newDashboard = useCallback(() => {
    if (processedSeedItems) {
      makeNewDashboard(name, processedSeedItems, vars, newDashExpr => {
        updateNode(newDashExpr);
      });
    }
  }, [makeNewDashboard, name, processedSeedItems, vars, updateNode]);

  const versionNode = opWeaveServerVersion({}) as OutputNode<'string'>;
  const versionValue = useNodeValue(versionNode);

  return (
    <CustomMenu>
      {seedItems != null && (
        <MenuItem
          onClick={() => {
            onClose();
            newDashboard();
          }}>
          <MenuIcon>
            <IconAddNew />
          </MenuIcon>
          <MenuText>Seed new board</MenuText>
        </MenuItem>
      )}
      <MenuItem
        onClick={() => {
          onClose();
          goHome?.();
        }}>
        <MenuIcon>
          <IconBack />
        </MenuIcon>
        <MenuText>Back to home</MenuText>
      </MenuItem>
      <MenuItem
        onClick={() => {
          onClose();
          window.open('https://github.com/wandb/weave', '_blank');
        }}>
        <MenuIcon>
          <IconDocs />
        </MenuIcon>
        <MenuText>Weave documentation</MenuText>
      </MenuItem>
      <MenuDivider />
      <MenuItem disabled>
        <MenuText>
          Weave {versionValue.result}
          <br />
          by Weights & Biases
        </MenuText>
      </MenuItem>
    </CustomMenu>
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
