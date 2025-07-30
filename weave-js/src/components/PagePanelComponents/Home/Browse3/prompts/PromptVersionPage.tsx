import {UserLink} from '@wandb/weave/components/UserLink';
import {maybePluralize} from '@wandb/weave/core/util/string';
import React, {useCallback, useMemo, useState} from 'react';

import {StorageSizeResult} from '../../../../../common/hooks/useStorageSizeCalculation';
import {Button} from '../../../../Button';
import {Icon} from '../../../../Icon';
import {LoadingDots} from '../../../../LoadingDots';
import {Tailwind} from '../../../../Tailwind';
import {Timestamp} from '../../../../Timestamp';
import {Messages} from '../pages/ChatView/types';
import {ObjectVersionsLink, objectVersionText} from '../pages/common/Links';
import {
  ScrollableTabContent,
  SimplePageLayoutWithHeader,
} from '../pages/common/SimplePageLayout';
import {StorageSizeSection} from '../pages/common/StorageSizeSection';
import {DeleteObjectButtonWithModal} from '../pages/ObjectsPage/ObjectDeleteButtons';
import {TabPrompt} from '../pages/ObjectsPage/Tabs/TabPrompt';
import {TabUsePrompt} from '../pages/OpsPage/Tabs/TabUsePrompt';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';
import {projectIdFromParts} from '../pages/wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '../pages/wfReactInterface/utilities';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';

type Data = Record<string, any>;

const getMessages = (data: Data): Messages => {
  if (data._class_name === 'EasyPrompt') {
    return data.data;
  }
  if (data._class_name === 'MessagesPrompt') {
    return data.messages;
  }
  if (data._class_name === 'StringPrompt') {
    return [{role: 'user', content: data.content}];
  }
  throw new Error('Unhandled prompt type');
};

export const PromptVersionPage: React.FC<{
  objectVersion: ObjectVersionSchema;
  storageSizeResult: StorageSizeResult;
  showDeleteButton?: boolean;
}> = ({objectVersion, storageSizeResult, showDeleteButton}) => {
  const {useRootObjectVersions} = useWFHooks();
  const getTsClient = useGetTraceServerClientContext();
  const tsClient = getTsClient();

  const [isEditing, setIsEditing] = useState(false);
  const {
    entity: entityName,
    project: projectName,
    objectId: objectName,
    versionIndex: objectVersionIndex,
    createdAtMs
  } = objectVersion;

  // Get information about other versions of this object
  const objectVersions = useRootObjectVersions({
    entity: entityName,
    project: projectName,
    filter: {objectIds: [objectName]},
    includeStorageSize: false,
  });
  const objectVersionCount = (objectVersions.result ?? []).length;
  const refUri = objectVersionKeyToRefUri(objectVersion);

  const initialMessages = useMemo(
    () => getMessages(objectVersion.val),
    [objectVersion.val]
  );
  const [messages, setMessages] = useState<Messages>(initialMessages);
  const updateMessages = useCallback(
    (newMessages: Messages) => {
      setMessages(newMessages);
    },
    [setMessages]
  );

  const handleEditClick = useCallback(() => setIsEditing(true), []);
  const handleCancelClick = useCallback(() => {
    updateMessages(initialMessages);
    setIsEditing(false);
  }, [initialMessages, updateMessages]);

  const handlePublish = useCallback(async () => {
    setIsEditing(false);

    tsClient.objCreate({
      obj: {
        project_id: projectIdFromParts({
          entity: entityName,
          project: projectName,
        }),
        object_id: objectName,
        val: {
          name: objectName,
          description: null,
          _type: 'MessagesPrompt',
          _class_name: 'MessagesPrompt',
          _bases: ['Prompt', 'Object', 'BaseModel'],
          messages,
        },
      },
    });
  }, [tsClient, entityName, projectName, objectName, messages]);

  const renderEditingControls = () => {
    return (
      <div className="flex gap-8">
        <Button
          title="Cancel"
          tooltip="Cancel"
          variant="secondary"
          size="medium"
          onClick={handleCancelClick}>
          Cancel
        </Button>

        <Button
          title="Publish"
          tooltip="Publish"
          size="medium"
          variant="primary"
          icon="checkmark"
          onClick={handlePublish}
          disabled={messages.length === 0}>
          Publish
        </Button>
      </div>
    );
  };

  return (
    <SimplePageLayoutWithHeader
      title={
        <Tailwind>
          <div className="flex items-center gap-8">
            <div className="flex h-22 w-22 items-center justify-center rounded-full bg-moon-300/[0.48] text-moon-600">
              <Icon width={14} height={14} name="forum-chat-bubble" />
            </div>
            <span data-testid="prompt-version-page-name">
              {objectVersionText(objectName, objectVersionIndex)}
            </span>
          </div>
        </Tailwind>
      }
      headerContent={
        <Tailwind>
          <div className="flex justify-between">
            <div className="grid auto-cols-max grid-flow-col gap-[16px] overflow-x-auto text-[14px]">
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
                        ({maybePluralize(objectVersionCount, 'version')})
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
                <p className="text-moon-500">Last updated</p>
                <p>
                  <Timestamp value={createdAtMs / 1000} format="relative" />
                </p>
              </div>
              {objectVersion.userId && (
                <div className="block">
                  <p className="text-moon-500">Last updated by</p>
                  <UserLink userId={objectVersion.userId} includeName />
                </div>
              )}
              <StorageSizeSection
                currentVersionBytes={storageSizeResult.currentVersionSizeBytes}
                allVersionsSizeBytes={storageSizeResult.allVersionsSizeBytes}
                isLoading={storageSizeResult.isLoading}
                shouldShowAllVersions={storageSizeResult.shouldShowAllVersions}
              />
            </div>

            <div className="ml-auto flex-shrink-0">
              {isEditing ? (
                renderEditingControls()
              ) : (
                <Button
                  title="Edit prompt"
                  tooltip="Edit prompt"
                  variant="ghost"
                  size="medium"
                  icon="pencil-edit"
                  onClick={handleEditClick}
                />
              )}
              {showDeleteButton && !isEditing && (
                <DeleteObjectButtonWithModal
                  objVersionSchema={objectVersion}
                  tooltip="Delete this version of this prompt"
                />
              )}
            </div>
          </div>
        </Tailwind>
      }
      tabs={
        !isEditing
          ? [
              {
                label: 'Prompt',
                content: (
                  <ScrollableTabContent>
                    <TabPrompt
                      messages={messages}
                      setMessages={updateMessages}
                      isEditing={false}
                    />
                  </ScrollableTabContent>
                ),
              },
              {
                label: 'Use',
                content: (
                  <ScrollableTabContent>
                    <Tailwind>
                      <TabUsePrompt
                        entityName={entityName}
                        projectName={projectName}
                        name={objectName}
                        uri={refUri}
                        data={objectVersion.val}
                        versionIndex={objectVersionIndex}
                      />
                    </Tailwind>
                  </ScrollableTabContent>
                ),
              },
            ]
          : [
              {
                label: 'Editing',
                content: (
                  <ScrollableTabContent>
                    <TabPrompt
                      messages={messages}
                      setMessages={updateMessages}
                      isEditing={true}
                    />
                  </ScrollableTabContent>
                ),
              },
            ]
      }
    />
  );
};
