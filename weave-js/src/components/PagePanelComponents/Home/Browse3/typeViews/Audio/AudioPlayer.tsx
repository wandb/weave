import {MOON_900, TEAL_600} from '@wandb/weave/common/css/color.styles';
import {formatDurationWithColons} from '@wandb/weave/common/util/time';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useEffect, useRef, useState} from 'react';
import WaveSurfer from 'wavesurfer.js';

import {LoadingDots} from '../../../../../LoadingDots';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';

type AudioPlayerTypePayload = CustomWeaveTypePayload<
  'openai._legacy_response.HttpxBinaryResponseContent',
  {'audio.wav': string}
>;

export const AudioPlayer: FC<{
  entity: string;
  project: string;
  data: AudioPlayerTypePayload;
}> = ({entity, project, data}) => {
  const {useFileContent} = useWFHooks();
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const audioBinary = useFileContent(entity, project, data.files['audio.wav']);

  useEffect(() => {
    if (audioBinary.result) {
      setAudioUrl(URL.createObjectURL(new Blob([audioBinary.result])));
    }
  }, [audioBinary.result]);

  if (audioBinary.loading) {
    return <LoadingDots />;
  } else if (audioBinary.result == null || audioUrl == null) {
    return <span></span>;
  }

  return <MiniAudioViewer audioSrc={audioUrl} height={20} noWaveform={true} />;
};

const MiniAudioViewer: FC<{
  audioSrc: string;
  height: number;
  noWaveform?: boolean;
  downloadFile?: () => void;
}> = ({audioSrc, height, noWaveform, downloadFile}) => {
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
        waveColor: TEAL_600,
        progressColor: TEAL_600,
        cursorColor: MOON_900,
        responsive: true,
        height: height,
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
    <Tailwind>
      <div>
        {/* container for wavesurfer.js waveform */}
        <div
          className="audio-card-waveform"
          style={{
            height: '100%',
            width: '100%',
            flex: '1 1 auto',
            display: noWaveform ? 'none' : 'block',
          }}
          ref={waveformDomRef}
        />
        <div className="flex w-full items-center gap-4 whitespace-nowrap">
          <Button
            className="mr-2 pl-1 pr-1"
            disabled={audioLoading}
            icon={audioPlaying ? 'pause' : 'play'}
            onClick={() => {
              if (wavesurferRef.current) {
                wavesurferRef.current.playPause();
              }
            }}
            size="small"
          />
          <div
            style={{flex: '1 1 auto', overflow: 'hidden'}}
            className="audio-card-time">
            {[audioCurrentTime, audioTotalTime]
              .map(formatDurationWithColons)
              .join('/')}
          </div>
          <Button
            className="flex-0-0-auto"
            icon="download"
            onClick={downloadFile}
            size="small"
            variant="quiet"
          />
        </div>
      </div>
    </Tailwind>
  );
};
