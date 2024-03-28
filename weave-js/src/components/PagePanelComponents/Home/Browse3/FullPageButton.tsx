import React from 'react';
import {Link} from 'react-router-dom';

import {Button} from '../../../Button';

type FullPageButtonProps = {
  query: Record<string, any>;
  generalBase: string;
  targetBase: string;
};

export const FullPageButton = ({
  query,
  generalBase,
  targetBase,
}: FullPageButtonProps) => {
  if (!query.peekPath) {
    return null;
  }
  const [pathname, search] = query.peekPath.split('?');
  const params = new URLSearchParams(search);
  const paramsStr = params.toString();
  let to = pathname.replace(generalBase, targetBase);
  if (paramsStr) {
    to += `?${paramsStr}`;
  }
  return (
    <Link to={to}>
      <Button
        tooltip="Open full page for this object"
        icon="full-screen-mode-expand"
        variant="ghost"
        className="ml-4"
      />
    </Link>
  );
};
