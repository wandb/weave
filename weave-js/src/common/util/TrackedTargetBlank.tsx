import {useEntityProject} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {useOrgName} from '@wandb/weave/common/hooks/useOrganization';
import {useViewerUserInfo2} from '@wandb/weave/common/hooks/useViewerUserInfo';
import * as userEvents from '@wandb/weave/integrations/analytics/userEvents';
import React, {useCallback} from 'react';

import {FCWithRef} from './types';
import {TargetBlank} from './links';

export interface TrackedTargetBlankProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  trackedName: string;
  source: string;
  docType?: string;
  trackingType?: 'doc' | 'colab';
}

export const TrackedTargetBlank: FCWithRef<
  TrackedTargetBlankProps,
  HTMLAnchorElement
> = React.memo(
  React.forwardRef(({trackedName, source, docType, trackingType = 'doc', onClick: clientOnClick, children, ...passthroughProps}, ref) => {
    const {entity, project} = useEntityProject();
    const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
    const userInfoLoaded = !viewerLoading ? userInfo : null;
    const {orgName} = useOrgName({
      entityName: entity,
      skip: viewerLoading || !entity,
    });

    const onClick = useCallback(
      (event: React.MouseEvent<HTMLAnchorElement>) => {
        clientOnClick?.(event);
        
        if (!userInfoLoaded || !passthroughProps.href || !project || !entity) {
          return;
        }

        const baseEventData = {
          userId: userInfoLoaded.id,
          organizationName: orgName,
          entityName: entity,
          projectName: project,
          source,
        };

        if (trackingType === 'doc' && docType) {
          userEvents.docsLinkClicked({
            ...baseEventData,
            docType,
            url: passthroughProps.href,
          });
        } else if (trackingType === 'colab') {
          userEvents.colabButtonClicked({
            ...baseEventData,
            url: passthroughProps.href,
          });
        }
      },
      [entity, project, trackedName, clientOnClick, userInfoLoaded, orgName, source, docType, trackingType, passthroughProps.href]
    );

    return (
      <TargetBlank
        {...passthroughProps}
        onClick={onClick}
        ref={ref}>
        {children}
      </TargetBlank>
    );
  })
);