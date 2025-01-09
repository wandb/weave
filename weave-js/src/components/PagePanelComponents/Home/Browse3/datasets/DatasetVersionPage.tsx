import Box from '@mui/material/Box';
import React, {useMemo} from 'react';

import {Icon} from '../../../../Icon';
import {LoadingDots} from '../../../../LoadingDots';
import {Tailwind} from '../../../../Tailwind';
import {WeaveCHTableSourceRefContext} from '../pages/CallPage/DataTableView';
import {ObjectViewerSection} from '../pages/CallPage/ObjectViewerSection';
import {objectVersionText} from '../pages/common/Links';
import {ObjectVersionsLink} from '../pages/common/Links';
import {CenteredAnimatedLoader} from '../pages/common/Loader';
import {
  ScrollableTabContent,
  SimplePageLayoutWithHeader,
} from '../pages/common/SimplePageLayout';
import {DeleteObjectButtonWithModal} from '../pages/ObjectVersionPage';
import {TabUseDataset} from '../pages/TabUseDataset';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {objectVersionKeyToRefUri} from '../pages/wfReactInterface/utilities';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {CustomWeaveTypeProjectContext} from '../typeViews/CustomWeaveTypeDispatcher';

export const DatasetVersionPage: React.FC<{
  objectVersion: ObjectVersionSchema;
  showDeleteButton?: boolean;
}> = ({objectVersion, showDeleteButton}) => {
  const {useRootObjectVersions, useRefsData} = useWFHooks();
  const entityName = objectVersion.entity;
  const projectName = objectVersion.project;
  const objectName = objectVersion.objectId;
  const objectVersionIndex = objectVersion.versionIndex;

  const objectVersions = useRootObjectVersions(
    entityName,
    projectName,
    {
      objectIds: [objectName],
    },
    undefined,
    true
  );
  const objectVersionCount = (objectVersions.result ?? []).length;
  const refUri = objectVersionKeyToRefUri(objectVersion);

  const data = useRefsData([refUri]);
  const viewerData = useMemo(() => {
    if (data.loading) {
      return {};
    }
    return data.result?.[0] ?? {};
  }, [data.loading, data.result]);

  const viewerDataAsObject = useMemo(() => {
    const dataIsPrimitive =
      typeof viewerData !== 'object' ||
      viewerData === null ||
      Array.isArray(viewerData);
    if (dataIsPrimitive) {
      return {_result: viewerData};
    }
    return viewerData;
  }, [viewerData]);

  return (
    <SimplePageLayoutWithHeader
      title={
        <Tailwind>
          <div className="flex items-center gap-8">
            <div className="flex h-22 w-22 items-center justify-center rounded-full bg-moon-300/[0.48] text-moon-600">
              <Icon width={14} height={14} name="table" />
            </div>
            {objectVersionText(objectName, objectVersionIndex)}
          </div>
        </Tailwind>
      }
      headerContent={
        <Tailwind>
          <div className="grid w-full grid-flow-col grid-cols-[auto_auto_1fr] gap-[16px] text-[14px]">
            <div className="block">
              <p className="text-moon-500">Name</p>
              <ObjectVersionsLink
                entity={entityName}
                project={projectName}
                filter={{objectName}}
                versionCount={objectVersionCount}
                neverPeek
                variant="secondary">
                <div className="group flex items-center font-semibold">
                  <span>{objectName}</span>
                  {objectVersions.loading ? (
                    <LoadingDots />
                  ) : (
                    <span className="ml-[4px]">
                      ({objectVersionCount} version
                      {objectVersionCount !== 1 ? 's' : ''})
                    </span>
                  )}
                  <Icon
                    name="forward-next"
                    width={16}
                    height={16}
                    className="ml-[2px] opacity-0 group-hover:opacity-100"
                  />
                </div>
              </ObjectVersionsLink>
            </div>
            <div className="block">
              <p className="text-moon-500">Version</p>
              <p>{objectVersionIndex}</p>
            </div>
            {showDeleteButton && (
              <div className="ml-auto mr-0">
                <DeleteObjectButtonWithModal objVersionSchema={objectVersion} />
              </div>
            )}
          </div>
        </Tailwind>
      }
      tabs={[
        {
          label: 'Rows',
          content: (
            <ScrollableTabContent sx={{p: 0}}>
              <Box
                sx={{
                  flex: '0 0 auto',
                  height: '100%',
                }}>
                {data.loading ? (
                  <CenteredAnimatedLoader />
                ) : (
                  <WeaveCHTableSourceRefContext.Provider value={refUri}>
                    <CustomWeaveTypeProjectContext.Provider
                      value={{entity: entityName, project: projectName}}>
                      <ObjectViewerSection
                        title=""
                        data={viewerDataAsObject}
                        noHide
                        isExpanded
                      />
                    </CustomWeaveTypeProjectContext.Provider>
                  </WeaveCHTableSourceRefContext.Provider>
                )}
              </Box>
            </ScrollableTabContent>
          ),
        },
        {
          label: 'Use',
          content: (
            <ScrollableTabContent>
              <Tailwind>
                <TabUseDataset
                  name={objectName}
                  uri={refUri}
                  versionIndex={objectVersionIndex}
                />
              </Tailwind>
            </ScrollableTabContent>
          ),
        },
      ]}
    />
  );
};
