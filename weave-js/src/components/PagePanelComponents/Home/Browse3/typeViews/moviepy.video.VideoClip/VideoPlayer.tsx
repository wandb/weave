import React, {useEffect, useState} from 'react';
import {AutoSizer} from 'react-virtualized';
import {LoadingDots} from '../../../../../LoadingDots';
import {useContext} from 'react';
import {NotApplicable} from '../../NotApplicable';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';
import {CustomWeaveTypeProjectContext} from '../CustomWeaveTypeDispatcher';
import {CustomLink} from '../../pages/common/Links';
import VideoViewer from '../../../../../../components/Panel2/VideoViewer'
import * as Dialog from '../../../../../../components/Dialog/Dialog';

type VideoClipTypePayload = CustomWeaveTypePayload<
  'moviepy.video.VideoClip.VideoClip',
  {'video.gif': string} | {'video.mp4': string} | {'video.webm': string}
>;

type VideoPlayerProps = {
  entity: string;
  project: string;
  mode?: string;
  data: VideoClipTypePayload;
};

export const VideoPlayer = (props: VideoPlayerProps) => (
  <AutoSizer style={{height: '100%', width: '100%'}}>
    {({width, height}) => {
      if (width === 0 || height === 0) {
        return null;
      }
      return (
        <VideoPlayerWithSize
          {...props}
          mode={props.mode}
          containerWidth={width}
          containerHeight={height}
        />
      );
    }}
  </AutoSizer>
);

type VideoPlayerWithSizeProps = VideoPlayerProps & {
  containerWidth: number;
  containerHeight: number;
};

const VideoPlayerWithSize = ({
  entity,
  project,
  data,
  containerWidth,
  containerHeight,
  ...props
}: VideoPlayerWithSizeProps) => {
  const [showPopup, setShowPopup] = useState(false);
  const {useFileContent} = useWFHooks();
  const videoTypes = {
    'video.gif': 'gif',
    'video.mp4': 'mp4',
    'video.webm': 'webm',
  } as const;

  const videoKey = Object.keys(data.files).find(key => key in videoTypes) as
    | keyof VideoClipTypePayload['files']
    | undefined;
  const videoBinary = useFileContent(
    entity,
    project,
    videoKey ? data.files[videoKey] : '',
    {skip: !videoKey}
  );

  const context = useContext(CustomWeaveTypeProjectContext);
  const mode = props.mode ?? context?.mode;

  if (!videoKey) {
    return <NotApplicable />;
  }

  const fileExt = videoTypes[videoKey as keyof typeof videoTypes];
  if (!mode || mode != 'object_viewer') {
    const videoText = `${fileExt.toUpperCase()} Video`
    return (
      <>
        <div style={{ display: 'flex', justifyContent: 'flex-start', width: '100%', margin: 'auto', padding: '6px' }}>
          <CustomLink text={videoText} onClick={() => setShowPopup(true)}/>
        </div>

        {showPopup && videoBinary.result && (
          <Dialog.Root open={showPopup} onOpenChange={setShowPopup}>
            <Dialog.Portal>
              <Dialog.Overlay />
              <Dialog.Content className="w-[60vw] h-[60vh] p-0"> 
                <VideoPlayerWithData
                  fileExt={fileExt}
                  buffer={videoBinary.result}
                  containerWidth={containerWidth}
                  containerHeight={containerHeight}
                  title={data.custom_name || entity.split('-')[0]}
                />
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        )}
      </>
    )
  }

  if (videoBinary.loading) {
    return <LoadingDots />;
  } else if (videoBinary.result == null) {
    return <span></span>;
  }

  return (
    <VideoPlayerWithData
      fileExt={fileExt}
      buffer={videoBinary.result}
      containerWidth={containerWidth}
      containerHeight={containerHeight}
      title={data.custom_name || entity.split('-')[0]} // Using first part of entity as title if no custom name
    />
  );
};

type VideoPlayerWithDataProps = {
  fileExt: 'gif' | 'mp4' | 'webm';
  buffer: ArrayBuffer;
  previewImageUrl?: string;
  containerWidth: number;
  containerHeight: number;
  title: string;
};

const VideoPlayerWithData = ({
  fileExt,
  buffer,
  previewImageUrl,
  containerWidth,
  containerHeight,
  title,
}: VideoPlayerWithDataProps) => {
  const [url, setUrl] = useState<string>('');

  useEffect(() => {
    let mimeType: string;
    switch (fileExt) {
      case 'gif':
        mimeType = 'image/gif';
        break;
      case 'mp4':
        mimeType = 'video/mp4';
        break;
      case 'webm':
        mimeType = 'video/webm';
        break;
      default:
        mimeType = 'video/mp4';
    }

    const blob = new Blob([buffer], {
      type: mimeType,
    });
    const objectUrl = URL.createObjectURL(blob);
    setUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [buffer, fileExt]);

  if (!url) {
    return <LoadingDots />;
  }

  return (
    <VideoPlayerLoaded
      url={url}
      fileExt={fileExt}
      previewImageUrl={previewImageUrl}
      containerWidth={containerWidth}
      containerHeight={containerHeight}
      title={title}
    />
  );
};

type VideoPlayerLoadedProps = {
  url: string;
  fileExt: 'gif' | 'mp4' | 'webm';
  previewImageUrl?: string;
  containerWidth: number;
  containerHeight: number;
  title: string;
};

const VideoPlayerLoaded = (props: VideoPlayerLoadedProps) => {
  if (props.containerHeight >= 1) {
    return (
      <VideoViewer videoSrc={props.url} width={props.containerWidth} height={props.containerHeight}/>
    )
  } else return null
};
