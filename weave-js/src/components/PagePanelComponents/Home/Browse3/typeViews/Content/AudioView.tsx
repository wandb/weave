import {MOON_350, TEAL_500} from '@wandb/weave/common/css/color.styles';
import {formatDurationWithColons} from '@wandb/weave/common/util/time';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {
  FC,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import WaveSurfer from 'wavesurfer.js';

const SLIDER_WIDTH_THRESHOLD = 180;
const MINI_WIDTH_THRESHOLD = 80;

enum ShowMode {
  Controls = 'controls',
  Slider = 'slider',
  Mini = 'mini',
}

export const MiniAudioViewer: FC<{
  audioSrc: string | Blob;
  height: number;
  downloadFile?: () => void;
  autoplay?: boolean;
}> = ({audioSrc, height, downloadFile, autoplay = false}) => {
  const measureDivRef = useRef<HTMLDivElement>(null);
  const waveformDomRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | undefined>();

  const [showMode, setShowMode] = useState<ShowMode>(ShowMode.Controls);
  const [audioLoading, setAudioLoading] = useState(true);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [audioTotalTime, setAudioTotalTime] = useState<number | undefined>();
  const [audioCurrentTime, setAudioCurrentTime] = useState<number | undefined>(
    0
  );
  const [pressedPause, setPressedPause] = useState(false);

  const autoplayAttemptedForCurrentSrcRef = useRef(false);

  // Effect for WaveSurfer initialization and core event handling
  useEffect(() => {
    if (!audioSrc || !waveformDomRef.current) {
      return;
    }

    setAudioLoading(true);
    // Reset current time when source changes, before WaveSurfer is ready
    setAudioCurrentTime(0);

    const wavesurfer = WaveSurfer.create({
      backend: 'WebAudio',
      container: waveformDomRef.current,
      waveColor: MOON_350,
      progressColor: TEAL_500,
      cursorColor: MOON_350,
      responsive: true, // Key for handling resize without full re-initialization
      height,
      barHeight: 1.3,
      hideScrollbar: true,
    });
    wavesurferRef.current = wavesurfer;

    const onPlay = () => {
      setAudioPlaying(true);
      setPressedPause(false); // If audio plays, it overrides any "pressed pause" state
    };
    const onPause = () => {
      setAudioPlaying(false);
      // Do NOT set pressedPause(true) here. Only user click should do that.
    };
    const onReady = () => {
      setAudioLoading(false);
      const duration = wavesurfer.getDuration();
      setAudioTotalTime(duration || undefined);
      setAudioCurrentTime(0); // Reset current time when ready
    };
    const onSeek = () => {
      setAudioCurrentTime(wavesurfer.getCurrentTime());
    };
    const onAudioProcess = () => {
      setAudioCurrentTime(wavesurfer.getCurrentTime());
    };
    const onFinish = () => {
      setAudioPlaying(false);
      // Optionally reset to beginning:
      // wavesurfer.seekTo(0);
      // setAudioCurrentTime(0);
    };

    wavesurfer.on('play', onPlay);
    wavesurfer.on('pause', onPause);
    wavesurfer.on('ready', onReady);
    wavesurfer.on('seek', onSeek);
    wavesurfer.on('audioprocess', onAudioProcess);
    wavesurfer.on('finish', onFinish);

    if (typeof audioSrc === 'string') {
      wavesurfer.load(audioSrc);
    } else {
      wavesurfer.loadBlob(audioSrc);
    }

    return () => {
      wavesurfer.un('play', onPlay);
      wavesurfer.un('pause', onPause);
      wavesurfer.un('ready', onReady);
      wavesurfer.un('seek', onSeek);
      wavesurfer.un('audioprocess', onAudioProcess);
      wavesurfer.un('finish', onFinish);
      wavesurfer.destroy();
      wavesurferRef.current = undefined;
    };
  }, [audioSrc, height]); // Only re-init WaveSurfer if src or height changes

  // Effect to reset autoplay attempt flag when audioSrc changes
  useEffect(() => {
    autoplayAttemptedForCurrentSrcRef.current = false;
  }, [audioSrc]);

  // Effect for autoplay logic
  useEffect(() => {
    const wavesurfer = wavesurferRef.current;
    if (
      wavesurfer &&
      !audioLoading && // WaveSurfer is ready
      autoplay && // Autoplay prop is true
      !pressedPause && // User hasn't manually paused
      !autoplayAttemptedForCurrentSrcRef.current && // Haven't tried for this src yet
      (audioCurrentTime === undefined || audioCurrentTime === 0) // Only if at the beginning
    ) {
      wavesurfer.play();
      autoplayAttemptedForCurrentSrcRef.current = true;
    }
  }, [
    audioSrc, // Needed to associate attempt with specific source via autoplayAttemptedForCurrentSrcRef reset
    audioLoading,
    autoplay,
    pressedPause,
    audioCurrentTime,
    // wavesurferRef.current itself is not a reactive dependency here in the same way,
    // but its availability (checked by `wavesurfer &&`) is key.
    // The effect will re-run if other dependencies change, and check wavesurferRef.current then.
  ]);

  // Effect for responsive UI (ShowMode) using ResizeObserver
  useEffect(() => {
    const div = measureDivRef.current;

    // If there's no div to observe, do nothing and no cleanup is needed.
    if (!div) {
      return; // Explicitly return undefined (or simply do nothing)
    }

    // At this point, 'div' is guaranteed to be available.
    const updateMode = () => {
      const currentWidth = div.offsetWidth; // 'div' is safely captured from the outer scope here
      if (currentWidth > SLIDER_WIDTH_THRESHOLD) {
        setShowMode(ShowMode.Slider);
      } else if (currentWidth < MINI_WIDTH_THRESHOLD) {
        setShowMode(ShowMode.Mini);
      } else {
        setShowMode(ShowMode.Controls);
      }
    };

    updateMode(); // Initial check

    const resizeObserver = new ResizeObserver(updateMode);
    resizeObserver.observe(div);

    // Return the cleanup function
    return () => {
      resizeObserver.unobserve(div);
      resizeObserver.disconnect(); // Important for cleanup
    };
  }, []); // Empty dependency array is correct here as measureDivRef itself is stable,
  // and setShowMode, SLIDER_WIDTH_THRESHOLD, MINI_WIDTH_THRESHOLD are constants/stable.

  const handlePlayPauseClick = useCallback(
    () => {
      const wavesurfer = wavesurferRef.current;
      if (wavesurfer) {
        if (wavesurfer.isPlaying()) {
          setPressedPause(true); // User is intending to pause
        } else {
          setPressedPause(false); // User is intending to play
        }
        wavesurfer.playPause();
      }
    },
    [
      /* wavesurferRef is stable, setPressedPause is stable */
    ]
  );

  const audioTimeDisplay = useMemo(() => {
    return [audioCurrentTime, audioTotalTime]
      .map(formatDurationWithColons)
      .map(x => (x.slice(0, 1) === '0' ? x.slice(1) : x))
      .join('/');
  }, [audioCurrentTime, audioTotalTime]);

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
              onClick={handlePlayPauseClick}
              size={showMode === ShowMode.Mini ? 'medium' : 'small'}
              variant="ghost"
            />
            {showMode !== ShowMode.Mini && (
              <div
                className={`text-s pl-4 ${
                  showMode === ShowMode.Slider ? 'pr-4' : 'pr-10'
                }`}>
                {!audioLoading && audioTotalTime != null && audioTimeDisplay}
                {audioLoading && 'Loading...'}
              </div>
            )}
            <div
              ref={waveformDomRef}
              className={`flex-grow overflow-hidden ${
                // Use flex-grow for better space utilization
                showMode === ShowMode.Slider ? 'block' : 'hidden'
              }`}
              style={{minWidth: showMode === ShowMode.Slider ? '50px' : '0'}} // Ensure some min width for waveform
            />
            <div>
              {showMode === ShowMode.Slider && downloadFile && (
                <Button
                  icon="download"
                  onClick={downloadFile}
                  size="small"
                  variant="ghost"
                  className="mr-6"
                  disabled={audioLoading}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </Tailwind>
  );
};
