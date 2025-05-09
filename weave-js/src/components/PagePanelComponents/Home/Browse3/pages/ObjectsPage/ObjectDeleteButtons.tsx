import {Button} from '@wandb/weave/components/Button';
import {
  maybePluralize,
  maybePluralizeWord,
} from '@wandb/weave/core/util/string';
import React, {useContext, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {
  useClosePeek,
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {DeleteModal} from '../common/DeleteModal';
import {useWFHooks} from '../wfReactInterface/context';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';

export const DeleteObjectButtonWithModal: React.FC<{
  objVersionSchema: ObjectVersionSchema;
  overrideDisplayStr?: string;
}> = ({objVersionSchema, overrideDisplayStr}) => {
  const {useObjectDeleteFunc} = useWFHooks();
  const closePeek = useClosePeek();
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const routerContext = useWeaveflowCurrentRouteContext();
  const history = useHistory();
  const {objectVersionsDelete} = useObjectDeleteFunc();
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const deleteStr =
    overrideDisplayStr ??
    `${objVersionSchema.objectId}:v${objVersionSchema.versionIndex}`;

  const onSuccess = () => {
    if (isPeeking) {
      closePeek();
    } else {
      history.push(
        routerContext.objectVersionsUIUrl(
          objVersionSchema.entity,
          objVersionSchema.project,
          {
            objectName: objVersionSchema.objectId,
          }
        )
      );
    }
  };

  return (
    <>
      <Button
        icon="delete"
        variant="ghost"
        onClick={() => setDeleteModalOpen(true)}
      />
      <DeleteModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        deleteTitleStr={deleteStr}
        onDelete={() =>
          objectVersionsDelete({
            entity: objVersionSchema.entity,
            project: objVersionSchema.project,
            objectId: objVersionSchema.objectId,
            digests: [objVersionSchema.versionHash],
          })
        }
        onSuccess={onSuccess}
      />
    </>
  );
};

export const DeleteObjectVersionsButtonWithModal: React.FC<{
  entity: string;
  project: string;
  objectName: string;
  objectVersions: string[];
  disabled?: boolean;
  onSuccess: () => void;
}> = ({entity, project, objectName, objectVersions, disabled, onSuccess}) => {
  const {useObjectDeleteFunc} = useWFHooks();
  const {objectVersionsDelete} = useObjectDeleteFunc();
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const numObjects = objectVersions.length;
  const versionsStr = maybePluralizeWord(numObjects, 'version', 's');
  const objectDigests = objectVersions.map(v => v.split(':')[1]);
  const deleteTitleStr = `${numObjects} ${objectName} ${versionsStr}`;

  return (
    <>
      <Button
        icon="delete"
        variant="ghost"
        onClick={() => setDeleteModalOpen(true)}
        disabled={disabled}
      />
      <DeleteModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        deleteTitleStr={deleteTitleStr}
        deleteBodyStrs={objectVersions}
        onDelete={() =>
          objectVersionsDelete({
            entity,
            project,
            objectId: objectName,
            digests: objectDigests,
          })
        }
        onSuccess={onSuccess}
      />
    </>
  );
};

// Dialog confirming the deletion of all versions of one or more objects.
export const DeleteObjectsButtonWithModal: React.FC<{
  entity: string;
  project: string;
  objectIds: string[];
  disabled?: boolean;
  onSuccess: () => void;
}> = ({entity, project, objectIds, disabled, onSuccess}) => {
  const {useObjectDeleteFunc} = useWFHooks();
  const {objectDeleteAllVersions} = useObjectDeleteFunc();
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const numObjects = objectIds.length;
  const deleteTitleStr = maybePluralize(numObjects, 'object', 's');
  const deleteBodyStrs = objectIds.map(
    objectId => `${objectId} - all versions`
  );

  const onDelete = () => {
    return Promise.all(
      objectIds.map(objectId =>
        objectDeleteAllVersions({
          key: {
            entity,
            project,
            objectId,
            weaveKind: 'object',
            scheme: 'weave',
            versionHash: '',
            path: '',
          },
        })
      )
    );
  };

  return (
    <>
      <Button
        icon="delete"
        variant="ghost"
        onClick={() => setDeleteModalOpen(true)}
        disabled={disabled}
      />
      <DeleteModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        deleteTitleStr={deleteTitleStr}
        deleteBodyStrs={deleteBodyStrs}
        onDelete={onDelete}
        onSuccess={onSuccess}
      />
    </>
  );
};
