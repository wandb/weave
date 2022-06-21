import * as globals from '@wandb/common/css/globals.styles';

import * as React from 'react';
import {useRef} from 'react';

import {Card, Button} from 'semantic-ui-react';
import makeComp from '@wandb/common/util/profiler';

import WaveSurfer from 'wavesurfer.js';

import {formatDurationWithColons} from '@wandb/common/util/time';
import LegacyWBIcon from '@wandb/common/components/elements/LegacyWBIcon';

interface AudioViewerProps {
  audioSrc?: string;
  caption?: string | null;
  height: number;
  mediaFailedToLoad?: boolean;
  headerElement?: React.ReactNode;
  failedLoadElement?: React.ReactNode;
  downloadFile: () => Promise<void>;
}

const controlBarHeight = 30;

const AudioViewer = makeComp(
  (props: AudioViewerProps) => {
    const {
      audioSrc,
      caption,
      height,
      mediaFailedToLoad,
      headerElement,
      failedLoadElement,
      downloadFile,
    } = props;
    const wavesurferRef = useRef<WaveSurfer>();
    const waveformDomRef = useRef<HTMLDivElement>(null);

    const [audioLoading, setAudioLoading] = React.useState(true);
    const [audioPlaying, setAudioPlaying] = React.useState(false);
    const [audioTotalTime, setAudioTotalTime] = React.useState<number>();
    const [audioCurrentTime, setAudioCurrentTime] = React.useState<number>();

    // initializes the wavesurfer.js div and object (used to display waveforms)
    React.useEffect(() => {
      if (audioSrc) {
        if (!waveformDomRef.current) {
          throw Error(
            'Unexpected dom state AudioCard render should always set the ref'
          );
        }

        const wavesurfer = WaveSurfer.create({
          backend: 'WebAudio',
          container: waveformDomRef.current,
          waveColor: globals.primary,
          progressColor: globals.darkBlue,
          cursorColor: globals.darkBlue,
          responsive: true,
          height: height - controlBarHeight,
        });

        wavesurferRef.current = wavesurfer;

        /* WAVESURFER EVENTS */
        wavesurfer.on('play', () => {
          setAudioPlaying(true);
        });
        wavesurfer.on('pause', () => {
          setAudioPlaying(false);
        });
        wavesurfer.on('ready', () => {
          const duration = wavesurfer!.getDuration();

          setAudioLoading(false);
          setAudioCurrentTime(undefined);
          setAudioTotalTime(duration || undefined);
        });
        // fires when you click a new location in the waveform
        wavesurfer.on('seek', () => {
          setAudioCurrentTime(wavesurfer!.getCurrentTime());
        });
        // fires continuously while audio is playing
        wavesurfer.on('audioprocess', () => {
          setAudioCurrentTime(wavesurfer!.getCurrentTime());
        });

        wavesurfer.load(audioSrc);
      }

      return () => {
        if (wavesurferRef.current) {
          wavesurferRef.current.destroy();
        }
      };
    }, [audioSrc, height]);

    return (
      <div
        className="media-card__wrapper"
        style={{
          width: '100%',
          height: '100%',
        }}>
        <Card
          className="audio-card content-card"
          style={{
            height: '100%',
            width: '100%',
          }}>
          {headerElement && (
            <Card.Content
              style={{
                border: 0,
                width: '100%',
                height: '100%',
                padding: '5px 0px',
                display: 'flex',
                alignItems: 'center',
              }}>
              {headerElement}
            </Card.Content>
          )}

          {/* container for wavesurfer.js waveform */}
          <div
            className="audio-card-waveform"
            style={{
              height: '100%',
              width: '100%',
              flex: '1 1 auto',
              display: mediaFailedToLoad ? 'none' : 'block',
            }}
            ref={waveformDomRef}
          />
          {mediaFailedToLoad ? (
            failedLoadElement
          ) : (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                whiteSpace: 'nowrap',
                width: '100%',
                height: `${controlBarHeight}px`,
              }}>
              <Button
                style={{
                  flex: '0 0 auto',
                  paddingTop: '0.5em',
                  paddingBottom: '0.5em',
                }}
                disabled={audioLoading}
                loading={audioLoading}
                icon={audioLoading ? '' : audioPlaying ? 'pause' : 'play'}
                onClick={() => {
                  if (wavesurferRef.current) {
                    wavesurferRef.current.playPause();
                  }
                }}
              />
              <div
                style={{flex: '1 1 auto', overflow: 'hidden'}}
                className="audio-card-time">
                {[audioCurrentTime, audioTotalTime]
                  .map(formatDurationWithColons)
                  .join('/')}
              </div>
              {caption && (
                <div
                  style={{
                    background: globals.white,
                    width: '100%',
                    overflow: 'hidden',
                    display: 'flex',
                    justifyContent: 'center',
                    flex: '1 1',
                  }}>
                  {
                    <div style={{flexGrow: 1}}>
                      <div
                        style={{
                          padding: '0 5px',
                          textOverflow: 'ellipsis',
                        }}>
                        {caption}
                      </div>
                    </div>
                  }
                </div>
              )}
              {audioSrc && (
                <Button
                  style={{
                    flex: '0 0 auto',
                    paddingTop: '0.5em',
                    paddingBottom: '0.5em',
                  }}
                  icon
                  onClick={downloadFile}>
                  <LegacyWBIcon name="download" />
                </Button>
              )}
            </div>
          )}
        </Card>
      </div>
    );
  },
  {id: 'AudioViewer'}
);

export default AudioViewer;
