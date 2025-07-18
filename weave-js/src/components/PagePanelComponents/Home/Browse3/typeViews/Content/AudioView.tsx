import {MOON_350, TEAL_500} from '@wandb/weave/common/css/color.styles';
import {formatDurationWithColons} from '@wandb/weave/common/util/time';
import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/customWeaveType.types';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useEffect, useMemo, useRef, useState} from 'react';
import WaveSurfer from 'wavesurfer.js';

import {downloadFromUrl} from './Shared';
import {ContentViewMetadataLoadedProps} from './types';

export const AudioContent = (props: ContentViewMetadataLoadedProps) => {
  const {entity, project, content, metadata} = props;
  const {useFileContent} = useWFHooks();
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  // Memoize the params to prevent unnecessary re-queries
  const fileContentParams = useMemo(
    () => ({
      entity,
      project,
      digest: content,
    }),
    [entity, project, content]
  );

  const audioBinary = useFileContent(fileContentParams);

  useMemo(() => {
    if (audioBinary.result) {
      setAudioUrl(URL.createObjectURL(new Blob([audioBinary.result])));
    }
  }, [audioBinary.result]);

  if (audioBinary.loading) {
    return <LoadingDots />;
  } else if (audioBinary.result == null || audioUrl == null) {
    return <span></span>;
  }

  const downloadFile = () => {
    if (!audioUrl) {
      console.error('Audio URL is not available');
      return;
    }
    downloadFromUrl(audioUrl, metadata.filename);
  };

  return (
    <MiniAudioViewer
      audioSrc={audioUrl}
      height={24}
      downloadFile={downloadFile}
    />
  );
};

export const AudioPlayer: FC<{
  entity: string;
  project: string;
  data: CustomWeaveTypePayload;
}> = ({entity, project, data}) => {
  const {useFileContent} = useWFHooks();
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioFileName, setAudioFileName] = useState<string | null>(null);

  // Find the first audio file in the files object
  const audioFile = Object.keys(data.files).find(fileName =>
    fileName.startsWith('audio.')
  );

  // Memoize the params to prevent unnecessary re-queries
  const fileContentParams = useMemo(
    () => ({
      entity,
      project,
      digest: audioFile ? data.files[audioFile] : '',
    }),
    [entity, project, audioFile, data.files]
  );

  const audioBinary = useFileContent(fileContentParams);

  useMemo(() => {
    if (audioFile) {
      setAudioFileName(audioFile);
    }
  }, [audioFile]);

  useMemo(() => {
    if (audioBinary.result) {
      setAudioUrl(URL.createObjectURL(new Blob([audioBinary.result])));
    }
  }, [audioBinary.result]);

  if (audioBinary.loading) {
    return <LoadingDots />;
  } else if (audioBinary.result == null || audioUrl == null) {
    return <span></span>;
  }

  const downloadFile = () => {
    if (!audioUrl || !audioFileName) {
      console.error('Audio URL or filename is not available');
      return;
    }
    downloadFromUrl(audioUrl, audioFileName);
  };

  return (
    <MiniAudioViewer
      audioSrc={audioUrl}
      height={24}
      downloadFile={downloadFile}
    />
  );
};

const SLIDER_WIDTH_THRESHOLD = 180;
const MINI_WIDTH_THRESHOLD = 80;

enum ShowMode {
  Controls = 'controls',
  Slider = 'slider',
  Mini = 'mini',
}

const MiniAudioViewer: FC<{
  audioSrc: string;
  height: number;
  downloadFile?: () => void;
}> = ({audioSrc, height, downloadFile}) => {
  /* 
  Heavily inspired by code in weave-js/src/components/Panel2/AudioViewer.tsx 
  
  This component has 3 modes, based on the width of the container. Component
  is responsive to width changes. Modes:
  - controls: show play/pause, time. ex:                ([>] 0:00/0:05)
  - slider: show all. ex:                               ([>] 0:01/0:05 --|-----------  [v])
  - mini: show play/pause ex:                           ([>])
  */
  const measureDivRef = useRef<HTMLDivElement>(null);
  const [showMode, setShowMode] = useState<ShowMode>(ShowMode.Controls);

  const wavesurferRef = useRef<WaveSurfer>();
  const waveformDomRef = useRef<HTMLDivElement>(null);
  const [audioLoading, setAudioLoading] = React.useState(true);
  const [audioPlaying, setAudioPlaying] = React.useState(false);
  const [audioTotalTime, setAudioTotalTime] = React.useState<number>();
  const [audioCurrentTime, setAudioCurrentTime] = React.useState<number>();

  // initializes the wavesurfer.js div and object (used to display waveforms)
  React.useEffect(() => {
    if (audioSrc && waveformDomRef.current && measureDivRef.current) {
      const wavesurfer = WaveSurfer.create({
        backend: 'WebAudio',
        container: waveformDomRef.current,
        waveColor: MOON_350,
        progressColor: TEAL_500,
        cursorColor: MOON_350,
        responsive: true,
        height,
        barHeight: 1.3, // slightly exaggerated
        hideScrollbar: true,
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
  }, [audioSrc, height, measureDivRef.current?.offsetWidth]);

  const audioCurrentTimeStr = [audioCurrentTime, audioTotalTime]
    .map(formatDurationWithColons)
    .map(x => (x.slice(0, 1) === '0' ? x.slice(1) : x))
    .join('/');

  useEffect(() => {
    if (measureDivRef.current) {
      if (measureDivRef.current.offsetWidth > SLIDER_WIDTH_THRESHOLD) {
        setShowMode(ShowMode.Slider);
      } else if (measureDivRef.current.offsetWidth < MINI_WIDTH_THRESHOLD) {
        setShowMode(ShowMode.Mini);
      } else {
        setShowMode(ShowMode.Controls);
      }
    }
  }, [measureDivRef.current?.offsetWidth]);

  return (
    <Tailwind>
      <div ref={measureDivRef} className="w-full">
        <div
          className={`rounded-2xl bg-moon-150 ${
            showMode === ShowMode.Slider ? 'w-full' : 'w-fit'
          }`}>
          <div className="flex w-full items-center">
            <Button
              className={`pl-1 pr-1 ${
                showMode === ShowMode.Mini ? 'ml-0' : 'ml-6'
              }`}
              disabled={audioLoading}
              icon={audioPlaying ? 'pause' : 'play'}
              onClick={() => {
                if (wavesurferRef.current) {
                  wavesurferRef.current.playPause();
                }
              }}
              size={showMode === ShowMode.Mini ? 'medium' : 'small'}
              variant="ghost"
            />
            {showMode !== ShowMode.Mini && (
              <div
                className={`text-s pl-4 ${
                  showMode === ShowMode.Slider ? 'pr-4' : 'pr-10'
                }`}>
                {audioCurrentTimeStr}
              </div>
            )}
            {/* Waveform should always be mounted, but hidden when not in slider mode */}
            <div
              ref={waveformDomRef}
              className={`w-full overflow-hidden ${
                showMode === ShowMode.Slider ? 'block' : 'hidden'
              }`}
            />
            <div>
              {showMode === ShowMode.Slider && downloadFile && (
                <Button
                  icon="download"
                  onClick={downloadFile}
                  size="small"
                  variant="ghost"
                  className="mr-6"
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </Tailwind>
  );
};
