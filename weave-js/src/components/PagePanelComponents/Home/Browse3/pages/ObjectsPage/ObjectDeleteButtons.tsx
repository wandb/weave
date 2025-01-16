import {Button} from '@wandb/weave/components/Button';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import React, {useState} from 'react';

import {useClosePeek} from '../../context';
import {DeleteModal} from '../common/DeleteModal';
import {useWFHooks} from '../wfReactInterface/context';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';

export const DeleteObjectButtonWithModal: React.FC<{
  objVersionSchema: ObjectVersionSchema;
  overrideDisplayStr?: string;
}> = ({objVersionSchema, overrideDisplayStr}) => {
  const {useObjectDeleteFunc} = useWFHooks();
  const closePeek = useClosePeek();
  const {objectVersionsDelete} = useObjectDeleteFunc();
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const deleteStr =
    overrideDisplayStr ??
    `${objVersionSchema.objectId}:v${objVersionSchema.versionIndex}`;

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
          objectVersionsDelete(
            objVersionSchema.entity,
            objVersionSchema.project,
            objVersionSchema.objectId,
            [objVersionSchema.versionHash]
          )
        }
        onSuccess={closePeek}
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
          objectVersionsDelete(entity, project, objectName, objectDigests)
        }
        onSuccess={onSuccess}
      />
    </>
  );
};
