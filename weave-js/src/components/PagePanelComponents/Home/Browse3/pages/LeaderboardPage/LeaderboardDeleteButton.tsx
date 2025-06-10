import {Button} from '@wandb/weave/components/Button';
import React, {useContext, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {
  useClosePeek,
  useWeaveflowRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {DeleteModal} from '../common/DeleteModal';
import {useWFHooks} from '../wfReactInterface/context';

export const DeleteLeaderboardButton: React.FC<{
  entity: string;
  project: string;
  leaderboardName: string;
  variant?: 'full' | 'icon';
}> = ({entity, project, leaderboardName, variant = 'full'}) => {
  const {useObjectDeleteFunc} = useWFHooks();
  const closePeek = useClosePeek();
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const {baseRouter} = useWeaveflowRouteContext();
  const history = useHistory();
  const {objectDeleteAllVersions} = useObjectDeleteFunc();
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const onSuccess = () => {
    if (isPeeking) {
      closePeek();
    } else {
      history.push(baseRouter.leaderboardsUIUrl(entity, project));
    }
  };

  const onDelete = () => {
    return objectDeleteAllVersions({
      key: {
        entity,
        project,
        objectId: leaderboardName,
        weaveKind: 'object',
        scheme: 'weave',
        versionHash: '',
        path: '',
      },
    });
  };

  return (
    <>
      <Button
        icon="delete"
        variant="ghost"
        onClick={() => setDeleteModalOpen(true)}
        tooltip="Delete leaderboard"
      />
      <DeleteModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        deleteTitleStr={`leaderboard ${leaderboardName}`}
        onDelete={onDelete}
        onSuccess={onSuccess}
      />
    </>
  );
};