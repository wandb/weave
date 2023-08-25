import {
  Dropdown,
  DropdownItemProps,
  Form,
  Input,
  Loader,
  Modal,
} from 'semantic-ui-react';
import React, {useMemo} from 'react';
import styled from 'styled-components';
import {RED_550} from '@wandb/weave/common/css/color.styles';
import {WBButton} from '@wandb/weave/common/components/elements/WBButtonNew';
import * as query from './Home/query';
import {useIsAuthenticated} from './util';
import {useEffect, useState} from 'react';
import * as w from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {Icon} from '../Icon';
import {TakeActionType} from './persistenceStateMachine';
import * as M from './Modal.styles';

const Error = styled.div`
  font-size: 14px;
  color: ${RED_550};
`;
Error.displayName = 'S.Error';

type PublishModalProps = {
  defaultName: string | null;
  open: boolean;
  acting: boolean;
  takeAction: TakeActionType;
  onClose: () => void;
};

// TODO: Starting/ending with '.' or '-' should probably not be allowed.
const isValidBoardName = (name: string) => {
  return (
    0 < name.length && name.length <= 128 && /^[a-zA-Z0-9_.-]+$/.test(name)
  );
};

const iconStyle = {
  verticalAlign: 'middle',
  display: 'inline-block',
  marginRight: 8,
};

export const PublishModal = ({
  defaultName,
  open,
  acting,
  takeAction,
  onClose,
}: PublishModalProps) => {
  const [boardName, setBoardName] = useState(defaultName ?? '');
  const [entityName, setEntityName] = useState('');
  const [projectName, setProjectName] = useState('');
  const isValidName = isValidBoardName(boardName);
  const showError = boardName.length > 0 && !isValidName;

  // Make sure we only make requests once this is open
  const isAuthenticated = useIsAuthenticated(!open);
  const userEntities = query.useUserEntities(isAuthenticated && open);
  const userName = query.useUserName(isAuthenticated && open);

  const entityOptions: DropdownItemProps[] = useMemo(
    () =>
      userEntities.result.length === 0
        ? []
        : userEntities.result.sort().map(entName => ({
            icon: (
              <Icon
                name={
                  entName === userName.result
                    ? 'user-profile-personal'
                    : 'users-team'
                }
                style={iconStyle}
              />
            ),
            value: entName,
            text: entName,
          })),
    [userEntities.result, userName.result]
  );

  const projectsNode = w.opEntityProjects({
    entity: w.opRootEntity({
      entityName: w.constString(entityName),
    }),
  });

  // Initialize the entity selector to first option (user entity)
  useEffect(() => {
    if (!userEntities.loading && entityOptions.length > 0) {
      if (userName.result != null) {
        for (const option of entityOptions) {
          if (option.value === userName.result) {
            setEntityName(userName.result);
            return;
          }
        }
      }
      setEntityName(entityOptions[0].value as string);
    }
  }, [entityOptions, userEntities.loading, userName.result]);

  const projectDataNode = w.opProjectName({project: projectsNode});
  const projectNamesValue = useNodeValue(projectDataNode, {
    skip: entityName === '',
  });
  const projectNames: string[] = projectNamesValue.result
    ? projectNamesValue.result.filter(
        (name: string) => name !== 'model-registry'
      )
    : [];

  projectNames.sort();
  const projectOptions = projectNames.map(name => ({
    icon: <Icon name="folder-project" style={iconStyle} />,
    value: name,
    text: name,
  }));

  // Initalize the project selector to "weave" project if available,
  // otherwise first project.
  useEffect(() => {
    if (!projectNamesValue.loading && projectNames.length > 0) {
      const defaultProjectName = projectNames.includes('weave')
        ? 'weave'
        : projectNames[0];
      setProjectName(defaultProjectName);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectNamesValue.loading]);

  const onPublish = async () => {
    takeAction(
      'publish_new',
      {
        entityName,
        projectName,
        name: boardName,
      },
      () => {
        onClose();
      }
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      closeOnDimmerClick={false}
      size="small">
      <Modal.Content>
        <M.Title>Publish board</M.Title>
        <M.Description>
          Name your board and select a destination entity and project in Weights
          & Biases.
        </M.Description>
        {isAuthenticated === false ? (
          <span>Please authenticate with W&B to publish boards</span>
        ) : (
          <>
            <Form>
              <Form.Field>
                <label>Name</label>
                <Input
                  value={boardName}
                  placeholder="Name"
                  onChange={e => setBoardName(e.target.value)}
                  error={showError}
                />
                {showError && (
                  <Error>Spaces and special characters are not allowed.</Error>
                )}
              </Form.Field>
              <Form.Field>
                <label>Entity</label>
                {userEntities.loading ? (
                  <Loader active inline size="tiny" />
                ) : (
                  <Dropdown
                    placeholder="Select entity"
                    fluid
                    selection
                    options={entityOptions}
                    value={entityName}
                    onChange={(e, data) => {
                      setEntityName(data.value as string);
                      setProjectName('');
                    }}
                  />
                )}
              </Form.Field>
              <Form.Field>
                <label>Project</label>
                {userEntities.loading || projectNamesValue.loading ? (
                  <Loader active inline size="tiny" />
                ) : projectOptions.length > 0 ? (
                  <Dropdown
                    placeholder="Select project"
                    fluid
                    selection
                    options={projectOptions}
                    value={projectName}
                    onChange={(e, data) => {
                      setProjectName(data.value as string);
                    }}
                  />
                ) : (
                  <span>Entity has no project</span>
                )}
              </Form.Field>
            </Form>
            <M.Buttons>
              <WBButton
                variant="confirm"
                loading={acting}
                disabled={!isValidName || !entityName || !projectName || acting}
                onClick={onPublish}>
                Publish board
              </WBButton>
              <WBButton variant="ghost" onClick={onClose}>
                Cancel
              </WBButton>
            </M.Buttons>
          </>
        )}
      </Modal.Content>
    </Modal>
  );
};
