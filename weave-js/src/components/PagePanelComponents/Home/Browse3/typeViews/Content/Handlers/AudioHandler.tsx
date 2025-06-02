import {Button} from '@wandb/weave/components/Button';
import React from 'react';

import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {MiniAudioViewer} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Views';
import {HandlerProps, HandlerReturnType} from './Shared';

const DownloadButton = ({
  isDownloading,
  doSave,
}: {
  isDownloading: boolean;
  doSave: () => void;
}) => {
  return (
    <Button
      icon={isDownloading ? 'loading' : 'download'}
      variant="ghost"
      size="small"
      onClick={isDownloading ? undefined : doSave}
    />
  );
};

export const handleAudioMimetype = ({
  iconStart,
  filename,
  showPreview,
  contentResult,
  setShowPreview,
  setIsDownloading,
  doSave,
  isDownloading,
}: HandlerProps): HandlerReturnType => {
  const onTextClick = () => {
    setShowPreview(true);
    if (!contentResult) {
      setIsDownloading(true);
    }
  };

  const iconAndText = (
    <>
      {!showPreview && (
        <CustomLink
          variant="secondary"
          icon={iconStart}
          onClick={onTextClick}
          text={filename}
        />
      )}
      {showPreview && contentResult && (
        <MiniAudioViewer
          audioSrc={contentResult}
          autoplay={true}
          height={24}
          downloadFile={doSave}
        />
      )}
    </>
  );

  const body = (
    <TailwindContents>
      {showPreview && iconAndText}
      {!showPreview && (
        <div className="group flex items-center gap-4">
          {iconAndText}
          {!showPreview && (
            <div className="opacity-0 group-hover:opacity-100">
              <DownloadButton isDownloading={isDownloading} doSave={doSave} />
            </div>
          )}
        </div>
      )}
    </TailwindContents>
  );

  return {
    body,
    tooltipHint: 'Click icon or filename to preview, button to download',
  };
};
