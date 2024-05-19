import {
  IconDelete,
  IconInfo,
  IconOpenNewTab,
} from '@wandb/weave/components/Icon';
import {constString, opGet} from '@wandb/weave/core';
import {setDocumentTitle} from '@wandb/weave/util/document';
import moment from 'moment';
import React, {useEffect, useMemo, useState} from 'react';
import {useHistory, useParams} from 'react-router-dom';

import {urlLocalAssetPreview} from '../../../urls';
import {NavigateToExpressionType, SetPreviewNodeType} from './common';
import {HomeParams} from './Home';
import {CenterBrowser, CenterBrowserActionType} from './HomeCenterBrowser';
import {HomeBoardPreview} from './HomePreviewSidebar';
import * as query from './query';

type CenterLocalBrowserPropsType = {
  setPreviewNode: SetPreviewNodeType;
  navigateToExpression: NavigateToExpressionType;
};

const rowToExpression = (row: any) => {
  const uri = `local-artifact:///${row.name}:${row['latest version id']}/obj`;
  return opGet({uri: constString(uri)});
};

// Just doing local boards for now!
export const CenterLocalBrowser: React.FC<
  CenterLocalBrowserPropsType
> = props => {
  const [deletingId, setDeletingId] = useState<string | undefined>();
  const [isModalActing, setIsModalActing] = useState(false);
  const history = useHistory();
  const params = useParams<HomeParams>();

  useEffect(() => {
    setDocumentTitle('Local Boards');
  }, []);

  const localDashboards = query.useLocalDashboards();

  const browserData = useMemo(() => {
    return localDashboards.result
      .sort(a => -a.createdAt)
      .map(b => ({
        _id: b.name,
        name: b.name,
        'latest version id': b.version,
        // Note: even though this is `createdAt`, it is interpreted by the user
        // as `updatedAt` since it is the `created at` date for the latest
        // version.
        // TODO: Why is this date not utc??? Seems like a bug in the artifact writing code?
        'updated at': moment(b.createdAt).calendar(),
      }));
  }, [localDashboards]);

  const {setPreviewNode, navigateToExpression} = props;
  useEffect(() => {
    if (localDashboards.loading) {
      return;
    }
    if (params.preview) {
      const row = browserData.find(b => b._id === params.preview);
      if (row) {
        setDocumentTitle(params.preview);
        const expr = rowToExpression(row);
        const node = (
          <HomeBoardPreview
            expr={expr}
            name={params.preview}
            setPreviewNode={setPreviewNode}
            navigateToExpression={navigateToExpression}
          />
        );
        setPreviewNode(node);
      } else {
        setPreviewNode(undefined);
      }
    } else {
      setPreviewNode(undefined);
    }
  }, [
    params.preview,
    setPreviewNode,
    navigateToExpression,
    browserData,
    localDashboards.loading,
  ]);

  const browserActions: Array<
    CenterBrowserActionType<(typeof browserData)[number]>
  > = useMemo(() => {
    return [
      [
        {
          icon: IconInfo,
          label: 'Board details',
          onClick: row => {
            history.push(urlLocalAssetPreview(row._id));
          },
        },
      ],
      [
        {
          icon: IconOpenNewTab,
          label: 'Open Board',
          onClick: row => {
            navigateToExpression(rowToExpression(row));
          },
        },
      ],
      [
        {
          icon: IconDelete,
          label: 'Delete board',
          onClick: row => {
            const uri = `local-artifact:///${row._id}:latest/obj`;
            setDeletingId(uri);
          },
        },
      ],
    ];
  }, [navigateToExpression, history]);

  return (
    <CenterBrowser
      allowSearch
      title={'Local Boards'}
      selectedRowId={params.preview}
      // setSelectedRowId={setSelectedRowId}
      setPreviewNode={props.setPreviewNode}
      noDataCTA={`No Local Weave boards found.`}
      loading={localDashboards.loading}
      columns={['name', 'latest version id', 'updated at']}
      data={browserData}
      actions={browserActions}
      deletingId={deletingId}
      setDeletingId={setDeletingId}
      isModalActing={isModalActing}
      setIsModalActing={setIsModalActing}
    />
  );
};
