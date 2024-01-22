import PanelError from '@wandb/weave/common/components/elements/PanelError';
import React, {
  ReactNode,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import {Card, Placeholder} from 'semantic-ui-react';

interface VideoViewerProps {
  videoSrc: string;
  width: number;
  height: number;
  videoFilename?: string;
  headerElement?: ReactNode;
  footerElement?: ReactNode;
  failedLoadElement?: ReactNode;
  refreshTimestamp?: number;
  mediaFailedToLoad?: boolean;
  single?: boolean;
  setDomLoadFailed?: React.Dispatch<React.SetStateAction<boolean | undefined>>;
  autoPlay?: boolean;
  muted?: boolean;
}

// a single image card
const VideoViewer = (props: VideoViewerProps) => {
  const {
    videoFilename,
    videoSrc,
    refreshTimestamp,
    headerElement,
    footerElement,
    failedLoadElement,
    mediaFailedToLoad,
    setDomLoadFailed,
    autoPlay,
    muted,
  } = props;

  const videoRef = useRef<HTMLVideoElement>(null);

  const [videoWidth, setVideoWidth] = useState<number>();
  const [videoHeight, setVideoHeight] = useState<number>();
  const [isPlayButtonVisible, setPlayButtonVisibility] = useState(false);
  const [videoLoaded, setVideoLoaded] = useState(false);
  const [containerHeight, setContainerHeight] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const [error, setError] = useState<ReactNode | null>(null);
  useLayoutEffect(() => {
    return () => setError(null);
  }, [videoSrc]);
  const onError = useCallback(() => {
    setDomLoadFailed?.(true);

    const err = videoRef.current?.error;
    if (err != null) {
      setError(getMediaErrorMessage(err));
    }
  }, [setDomLoadFailed]);

  const videoFile = videoFilename || videoSrc;
  const width = videoWidth || props.width;
  const height = videoHeight || props.height;

  // This section handles impartial data, streaming,
  // and errors in network requests

  // Create a refresh handler to refresh the dom node
  const videoRefresh = React.useCallback(() => {
    if (videoRef.current == null) {
      return;
    }
    const currentTime = videoRef.current.currentTime;
    videoRef.current.src = videoSrc;
    videoRef.current.currentTime = currentTime;
  }, [videoSrc]);

  useEffect(() => {
    videoRefresh();
  }, [videoRefresh, refreshTimestamp]);

  // Upon mount, unmute video if defaultUnmute is true
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.muted = muted ?? true;
      if (autoPlay && videoRef.current.paused) {
        videoRef.current.play().catch(() => {
          // Browsers have their own implementations of how to handle auto-play and
          // many disallow it, for example: https://goo.gl/xX8pDD
        });
      }
    }
  }, [muted, autoPlay]);

  // the exhaustive-deps rule will complain here that it "can't verify" the dependencies,
  // but the intent is for this to run on _every_ render, so I needed to disable it
  useLayoutEffect(
    () => {
      if (containerRef.current) {
        // this won't trigger a re-render if the height hasn't actually changed
        setContainerHeight(containerRef.current.getBoundingClientRect().height);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    undefined
  );
  // Check the dom element and the loading spinner
  // In situations with no failures the dom will load first

  const onLoaded = (
    e: React.SyntheticEvent<HTMLVideoElement | HTMLImageElement, Event>
  ) => {
    const t = e.target;
    let w;
    let h;
    if ((t as HTMLVideoElement).videoWidth) {
      const v = t as HTMLVideoElement;
      w = v.videoWidth;
      h = v.videoHeight;
    } else {
      const i = t as HTMLImageElement;
      w = i.naturalWidth;
      h = i.naturalHeight;
    }
    setVideoWidth(w);
    setVideoHeight(h);
    setVideoLoaded(true);
  };

  let cardSize;
  if (!videoLoaded || mediaFailedToLoad) {
    cardSize = {maxWidth: 0, maxHeight: 0};
  }

  const cardStyles = {
    width: '100%',
    height: '100%',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'stretch',
    alignItems: 'stretch',
    boxShadow: 'none',
  };

  const mediaStyles = {
    ...{cursor: 'pointer', overflow: 'hidden'},
    ...cardSize,
    objectFit: 'contain' as const,
    width: '100%',
    height: '100%',
  };

  const content = (
    <>
      {!videoLoaded && (
        <Placeholder style={{width, height}}>
          <Placeholder.Image />
        </Placeholder>
      )}

      {!mediaFailedToLoad ? (
        <>
          {videoFile.match(/.gif$/) ? (
            <img
              src={videoSrc}
              alt={videoFile}
              style={mediaStyles}
              onLoad={onLoaded}
              onError={onError}
            />
          ) : (
            <div
              className="video-container"
              ref={containerRef}
              style={mediaStyles}>
              {containerHeight > 0 && (
                <div
                  className={`video-card__play-btn__${
                    isPlayButtonVisible ? 'visible' : 'hidden'
                  }`}
                  style={{
                    margin: containerHeight * 0.03,
                    width: containerHeight * 0.2,
                    height: containerHeight * 0.2,
                  }}>
                  <i
                    className="play icon"
                    style={{
                      fontSize: containerHeight * 0.1,
                      paddingLeft: containerHeight * 0.02,
                    }}></i>
                </div>
              )}
              <video
                autoPlay={autoPlay ?? false}
                ref={videoRef}
                loop
                muted
                onClick={e => {
                  const v = e.target as HTMLVideoElement;
                  if (v.paused) {
                    v.play()
                      .catch(() => {
                        // Browsers have their own implementations of how to handle auto-play and
                        // many disallow it, for example: https://goo.gl/xX8pDD
                      })
                      .then(() => {
                        setPlayButtonVisibility(false);
                      });
                  } else {
                    v.pause();
                    setPlayButtonVisibility(true);
                  }
                }}
                onLoadedData={onLoaded}
                onError={onError}
                src={videoSrc}
              />
            </div>
          )}
        </>
      ) : (
        failedLoadElement
      )}
    </>
  );
  return (
    <Card className="video-card content-card" style={cardStyles}>
      {headerElement}
      {error != null ? (
        <PanelError message={<div style={{width, height}}>{error}</div>} />
      ) : (
        content
      )}
      {footerElement}
    </Card>
  );
};

export default VideoViewer;

function getMediaErrorMessage({code, message}: MediaError): string {
  if (code === MediaError.MEDIA_ERR_ABORTED) {
    return `Fetching video was aborted: ${message}`;
  }
  if (code === MediaError.MEDIA_ERR_NETWORK) {
    return `Error fetching video over the network: ${message}`;
  }
  if (code === MediaError.MEDIA_ERR_DECODE) {
    return `Error decoding video: ${message}`;
  }
  if (code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED) {
    return `This video's codec is not supported by your browser. Please try another browser to view your logged video, or log it using a different codec.`;
  }
  return `Error displaying video: ${message}`;
}
