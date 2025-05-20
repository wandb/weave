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
  const {isModified, isSaving, onSaveView, onResetView, baseView} =
    savedViewsInfo;
  const {created_at} = baseView;
  return (
    <div className="flex items-center gap-8">
      {isModified ? (
        <Tooltip
          content="Reset view to last saved state"
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
      {!isReadonly && (
        <>
          <DropdownViewActions savedViewsInfo={savedViewsInfo} />
          <Button
            disabled={!isModified || isSaving}
            onClick={() => onSaveView()}>
            Save view
          </Button>
        </>
      )}
    </div>
  );
};
