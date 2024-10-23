import React from 'react';

import {Button} from '../../../../../Button';
import {Tooltip} from '../../../../../Tooltip';
import {A} from '../common/Links';
import {DropdownViewActions} from './DropdownViewActions';
import {SavedViewSuffixTimestamp} from './SavedViewSuffixTimestamp';
import {SavedViewsInfo} from './savedViewUtil';

type SavedViewSuffixProps = {
  savedViewsInfo: SavedViewsInfo;
  isReadonly: boolean;
};

export const SavedViewSuffix = ({
  savedViewsInfo,
  isReadonly,
}: SavedViewSuffixProps) => {
  const {isModified, onResetView, baseView} = savedViewsInfo;
  const {created_at} = baseView;
  return (
    <div className="flex items-center gap-8">
      {isModified ? (
        <Tooltip
          content="Clears column actions, filters, and sorting"
          trigger={
            <A $variant="primary" onClick={onResetView}>
              Reset view
            </A>
          }
        />
      ) : created_at ? (
        <div className="mr-8 text-moon-500">
          Saved on  <SavedViewSuffixTimestamp createdAt={created_at} />
        </div>
      ) : null}
      {/* <div className="mr-8 text-moon-500">Saved on Jul 25 at 5:22pm</div> */}
      {!isReadonly && (
        <>
          <DropdownViewActions savedViewsInfo={savedViewsInfo} />
          <Button
            disabled={!savedViewsInfo.isModified}
            onClick={() => savedViewsInfo.onSaveView()}>
            Save view
          </Button>
        </>
      )}
    </div>
  );
};
