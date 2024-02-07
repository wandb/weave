import WandbLoader from '@wandb/weave/common/components/WandbLoader';
import {
  RepresentationType,
  RepresentationTypeValues,
} from '@wandb/weave/common/types/libs/nglviewer';
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {AutoSizer} from 'react-virtualized';
import {Icon, Placeholder, PlaceholderImage} from 'semantic-ui-react';

import {onNextExitFullscreen} from '../../common/util/fullscreen';
import * as ConfigPanel from './ConfigPanel';
import * as Panel2 from './panel';
import * as S from './PanelObject3D.styles';
import {useAssetURLFromArtifact} from './useAssetFromArtifact';

const inputType = {type: 'molecule-file' as const};

type MoleculeConfig = {
  representationType?: RepresentationType;
};
type PanelMoleculeProps = Panel2.PanelProps<typeof inputType, MoleculeConfig>;

const PanelMolecule: React.FC<PanelMoleculeProps> = props => {
  const inputNode = props.input;
  const assetResult = useAssetURLFromArtifact(inputNode);
  const isMolecule =
    !assetResult.loading && assetResult.asset.path.endsWith('.pdb');

  return (
    <div style={{height: '100%', width: '100%', overflow: 'hidden'}}>
      {assetResult.loading ? (
        <WandbLoader name="panel-molecule" />
      ) : isMolecule ? (
        <AutoSizer>
          {({width, height}) => {
            return (
              <div
                style={{
                  height: `${height}px`,
                  width: `${width}px`,
                  overflow: 'hidden',
                }}>
                <Molecule
                  {...props}
                  width={width}
                  height={height}
                  directUrl={assetResult.directUrl as string}
                  representationType={
                    props.config?.representationType ?? 'default'
                  }
                  extension="pdb"
                />
              </div>
            );
          }}
        </AutoSizer>
      ) : (
        <p>
          Tried to render{' '}
          {assetResult.asset.path ? (
            <code>{assetResult.asset.path}</code>
          ) : (
            'this object'
          )}
          , but only .pdb files are currently supported.
        </p>
      )}
    </div>
  );
};

interface MediaMoleculeProps {
  width: number;
  height: number;
  directUrl: string;
  representationType: RepresentationType;
  extension: string;
}

const Molecule: React.FC<MediaMoleculeProps> = props => {
  const {width, height, directUrl, representationType, extension} = props;
  type NGLLib = typeof import('@wandb/weave/common/util/nglviewerRender');
  const [nglLib, setNglLib] = useState<NGLLib>();
  useEffect(() => {
    import('@wandb/weave/common/util/nglviewerRender').then(setNglLib);
  }, []);

  const moleculeRef = useRef<HTMLDivElement>(null);
  const [dataFile, setDataFile] = useState<File>();
  const [screenshotURL, setScreenshotURL] = useState<string>();
  const [isInteractive, setIsInteractive] = useState<boolean>(false);
  const [stage, setStage] = useState<any>(null);
  const [mouseOver, setMouseOver] = useState<boolean>(false);

  const disableInteractivity = useCallback(() => {
    if (stage != null) {
      try {
        stage.dispose();
      } catch (e) {
        // pass
      }
    }
    if (moleculeRef.current != null) {
      moleculeRef.current.innerHTML = '';
    }
    setStage(null);
    setIsInteractive(false);
  }, [stage, setStage, setIsInteractive, moleculeRef]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(disableInteractivity, [representationType]);
  useEffect(() => {
    if (nglLib != null) {
      const fetchedUrl = directUrl;
      setScreenshotURL(undefined);
      fetch(fetchedUrl)
        .then(resp => resp.blob())
        .then(data => {
          if (fetchedUrl === directUrl) {
            const file = new File([data], 'molecule.' + extension);
            setDataFile(file);
            nglLib
              .moleculeScreenshot(
                file,
                {width, height},
                {representation: representationType},
                extension
              )
              .then(imageBlob => {
                if (fetchedUrl === directUrl) {
                  const url = window.URL.createObjectURL(imageBlob);
                  setScreenshotURL(url);
                }
              });
          }
        });
    }
  }, [directUrl, nglLib, width, height, representationType, extension]);

  const onMouseEnter = useCallback(() => {
    setMouseOver(true);
    if (
      !isInteractive &&
      nglLib != null &&
      moleculeRef.current != null &&
      dataFile != null &&
      screenshotURL != null
    ) {
      const newStage = nglLib.moleculeStage(
        moleculeRef.current,
        dataFile,
        {width, height},
        {representation: representationType},
        extension
      );
      setIsInteractive(true);
      setStage(newStage);
      moleculeRef.current
        .getElementsByTagName('canvas')[0]
        .addEventListener('webglcontextlost', disableInteractivity);
    }
  }, [
    dataFile,
    moleculeRef,
    nglLib,
    width,
    height,
    representationType,
    extension,
    setStage,
    isInteractive,
    setIsInteractive,
    disableInteractivity,
    setMouseOver,
    screenshotURL,
  ]);

  const onMouseLeave = useCallback(() => {
    setMouseOver(false);
  }, [setMouseOver]);

  const onFullscreen = useCallback(() => {
    if (nglLib != null && moleculeRef.current != null && dataFile != null) {
      disableInteractivity();
      const screenW = window.screen.width;
      const screenH = window.screen.height;
      const newStage = nglLib.moleculeStage(
        moleculeRef.current,
        dataFile,
        {width: screenW, height: screenH},
        {representation: representationType},
        extension
      );
      onNextExitFullscreen(() => {
        if (newStage != null) {
          newStage.dispose();
        }
        disableInteractivity();
      });

      try {
        moleculeRef.current?.requestFullscreen?.();
      } catch (e) {
        throw new Error('Fullscreen request invalid: ' + e);
      }
    }
  }, [
    dataFile,
    moleculeRef,
    nglLib,
    representationType,
    extension,
    disableInteractivity,
  ]);

  return (
    <S.FlexContainer>
      <div
        className="media-card"
        style={{
          height: `${height}px`,
          width: `${width}px`,
          backgroundImage: `url(${screenshotURL})`,
          backgroundRepeat: 'no-repeat',
          backgroundSize: '100% 100%',
        }}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}>
        {mouseOver && isInteractive && (
          <div
            style={{
              position: 'absolute',
              top: '0px',
              right: '0px',
              padding: '10px',
              color: '#EEE',
              zIndex: 1,
            }}
            onClick={onFullscreen}>
            <Icon size="large" link name="expand arrows alternate" />
          </div>
        )}
        <div className="object3D-card-babylon" ref={moleculeRef} />
        {!isInteractive && screenshotURL == null && (
          <Placeholder
            style={{
              height: `${height}px`,
              width: `${width}px`,
            }}>
            <PlaceholderImage square />
          </Placeholder>
        )}
      </div>
    </S.FlexContainer>
  );
};

const PanelMoleculeConfig: React.FC<PanelMoleculeProps> = props => {
  const {config, updateConfig} = props;
  const updateRepresentationType = useCallback(
    (newRepresentationType: RepresentationType) => {
      updateConfig({
        ...config,
        representationType: newRepresentationType,
      });
    },
    [updateConfig, config]
  );

  return (
    <ConfigPanel.ConfigOption label={'Field Type'}>
      <ConfigPanel.ModifiedDropdownConfigField
        selection
        options={RepresentationTypeValues.map(item => {
          return {
            text: '' + item,
            value: '' + item,
          };
        })}
        value={config?.representationType ?? 'default'}
        onChange={(e, {value}) =>
          updateRepresentationType(value as RepresentationType)
        }
      />
    </ConfigPanel.ConfigOption>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'molecule-file',
  Component: PanelMolecule,
  ConfigComponent: PanelMoleculeConfig,
  inputType,
  displayName: '3D Object',
  defaultFixedSize: {
    width: 242,
    height: 242,
  },
};
