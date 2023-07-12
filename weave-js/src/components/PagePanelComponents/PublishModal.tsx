import {
  Dropdown,
  DropdownItemProps,
  Form,
  Input,
  Modal,
} from 'semantic-ui-react';
import React from 'react';
import styled from 'styled-components';
import {
  MOON_800,
  MOON_850,
  RED_550,
} from '@wandb/weave/common/css/color.styles';
import {WBButton} from '@wandb/weave/common/components/elements/WBButtonNew';
import * as query from './Home/query';
import {useIsAuthenticated} from './util';
import {useEffect, useState} from 'react';
import * as w from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {Icon} from '../Icon';
import {TakeActionType} from './persistenceStateMachine';

const Title = styled.div`
  color: ${MOON_850};
  font-size: 24px;
  font-weight: 600;
  line-height: 40px;
`;
Title.displayName = 'S.Title';

const Description = styled.div`
  color: ${MOON_800};
  font-size: 16px;
  font-weight: 400;
  line-height: 140%;
  margin-bottom: 16px;
`;
Description.displayName = 'S.Description';

const Error = styled.div`
  font-size: 14px;
  color: ${RED_550};
`;
Error.displayName = 'S.Error';

const Buttons = styled.div`
  margin-top: 24px;
  display: flex;
  gap: 8px;
`;
Buttons.displayName = 'S.Buttons';

type PublishModalProps = {
  defaultName: string | null;
  open: boolean;
  acting: boolean;
  takeAction: TakeActionType;
  onClose: () => void;
};

const isValidBoardName = (name: string) => {
  return (
    0 < name.length && name.length <= 128 && /^[a-zA-Z0-9_.-]+$/.test(name)
  );
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

  const isAuthenticated = useIsAuthenticated();
  const userEntities = query.useUserEntities(isAuthenticated);
  const userName = query.useUserName(isAuthenticated);

  const iconStyle = {
    verticalAlign: 'middle',
    display: 'inline-block',
    marginRight: 8,
  };

  const entityOptions: DropdownItemProps[] =
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
        }));

  useEffect(() => {
    console.log('init entity');
    if (entityOptions.length > 0) {
      setEntityName(entityOptions[0].value as string);
    }
  }, [userEntities.loading]);

  const projectsNode = w.opEntityProjects({
    entity: w.opRootEntity({
      entityName: w.constString(entityName),
    }),
  });
  const projectDataNode = w.opMap({
    arr: projectsNode,
    mapFn: w.constFunction({row: 'project'}, ({row}) => {
      return w.opDict({
        name: w.opProjectName({project: row}),
      } as any);
    }),
  });

  useEffect(() => {
    if (!userEntities.loading && entityOptions.length > 0) {
      setEntityName(entityOptions[0].value as string);
    }
  }, [userEntities.loading]);

  const projectNamesValue = useNodeValue(projectDataNode, {
    skip: entityName === '',
  });
  const projectNames: string[] = projectNamesValue.result
    ? projectNamesValue.result
        .map((project: {name: string}) => project.name)
        .filter((name: string) => name !== 'model-registry')
    : [];

  projectNames.sort();
  const projectOptions = projectNames.map(name => ({
    icon: <Icon name="folder-project" style={iconStyle} />,
    value: name,
    text: name,
  }));

  useEffect(() => {
    // TODO: Should only suggest weave if publish new?
    if (!projectNamesValue.loading && projectNames.length > 0) {
      const defaultProjectName = projectNames.includes('weave')
        ? 'weave'
        : projectNames[0];
      setProjectName(defaultProjectName);
    }
  }, [projectNamesValue.loading]);

  const onPublish = async () => {
    console.log('onPublish');
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
        <Title>Publish board</Title>
        <Description>
          Name your board and select a destination entity and project in Weights
          & Biases.
        </Description>
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
          </Form.Field>
          <Form.Field>
            <label>Project</label>
            {projectOptions.length > 0 ? (
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
        <Buttons>
          <WBButton
            variant="confirm"
            disabled={!isValidName || !entityName || !projectName || acting}
            onClick={onPublish}>
            Publish board
          </WBButton>
          <WBButton variant="ghost" onClick={onClose}>
            Cancel
          </WBButton>
        </Buttons>
      </Modal.Content>
    </Modal>
  );
};
