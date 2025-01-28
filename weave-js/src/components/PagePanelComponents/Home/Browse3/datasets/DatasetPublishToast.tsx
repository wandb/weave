import React from 'react';
import {Link} from 'react-router-dom';

import {Icon} from '../../../../Icon';

export const DatasetPublishToast = ({
  url,
  objectId,
}: {
  url: string;
  objectId: string;
}) => (
  <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
    <Icon name="checkmark" width={20} height={20} />
    Published{' '}
    <Link to={url} style={PUBLISHED_LINK_STYLES}>
      {objectId}
    </Link>
  </div>
);

const PUBLISHED_LINK_STYLES = {
  color: '#2B66D8',
  textDecoration: 'none',
  fontWeight: 600,
} as const;
