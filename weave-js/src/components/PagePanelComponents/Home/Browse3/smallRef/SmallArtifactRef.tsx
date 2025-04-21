import {Box} from '@mui/material';
import * as Tooltip from '@radix-ui/react-tooltip';
import {useArtifactWeaveReference} from '@wandb/weave/common/hooks/useArtifactWeaveReference';
import {WandbArtifactRef} from '@wandb/weave/react';
import React, {FC} from 'react';

import {IconNames} from '../../../../Icon';
import {fetchArtifactRefPageUrl} from '../artifactRegistry';
import {Link} from '../pages/common/Links';
import {SmallRefBox} from './SmallRefBox';

export const SmallArtifactRef: FC<{
  objRef: WandbArtifactRef;
  iconOnly?: boolean;
}> = ({objRef}) => {
  const {loading, artInfo} = useArtifactWeaveReference({
    entityName: objRef.entityName,
    projectName: objRef.projectName,
    artifactName: objRef.artifactName + ':' + objRef.artifactVersion,
  });
  if (loading) {
    return (
      <Box
        sx={{
          width: '100%',
          height: '100%',
          minHeight: '38px',
          display: 'flex',
          alignItems: 'center',
        }}>
        <SmallRefBox iconName={IconNames.Loading} text="Loading..." />
      </Box>
    );
  }

  const artifactUrl = artInfo
    ? fetchArtifactRefPageUrl({
        entityName: objRef.entityName,
        projectName: objRef.projectName,
        artifactName: objRef.artifactName,
        artifactVersion: objRef.artifactVersion,
        artifactType: artInfo?.artifactType,
        orgName: artInfo?.orgName,
      })
    : null;

  const Content = (
    <Tooltip.Provider delayDuration={150} skipDelayDuration={50}>
      <Tooltip.Root>
        <Box
          sx={{
            width: '100%',
            height: '100%',
            minHeight: '38px',
            display: 'flex',
            alignItems: 'center',
            cursor: artifactUrl ? 'pointer' : 'not-allowed',
          }}>
          <Tooltip.Trigger asChild>
            <Box sx={{display: 'flex', alignItems: 'center'}}>
              <SmallRefBox
                iconName={IconNames.Registries}
                text={`${objRef.artifactName}:${objRef.artifactVersion}`}
              />
            </Box>
          </Tooltip.Trigger>
        </Box>
        <Tooltip.Portal>
          <Tooltip.Content
            side="top"
            sideOffset={8}
            className="rounded bg-moon-900 px-3 py-2 text-sm text-moon-200"
            style={{
              zIndex: 9999,
              position: 'relative',
              backgroundColor: '#1a1a1a',
              color: '#e0e0e0',
              padding: '8px 12px',
              borderRadius: '4px',
            }}>
            {artifactUrl
              ? objRef.artifactPath
              : 'No link detected for this wandb artifact reference: ' +
                objRef.artifactPath}
            <Tooltip.Arrow style={{fill: '#1a1a1a'}} />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );

  return artifactUrl ? (
    <Link
      $variant="secondary"
      style={{width: '100%', height: '100%'}}
      as="a"
      href={artifactUrl}>
      {Content}
    </Link>
  ) : (
    Content
  );
};
