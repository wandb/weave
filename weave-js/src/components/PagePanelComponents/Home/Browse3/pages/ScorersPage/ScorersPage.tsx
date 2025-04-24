import {Button} from '@wandb/weave/components/Button';
import {IconNames} from '@wandb/weave/components/Icon';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Box} from '@mui/material';
import React, {useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {AnnotationsTab} from './AnnotationsTab';
import {ProgrammaticScorersTab} from './CoreScorersTab';
import {CreateAnnotationFieldDrawer} from './CreateAnnotationFieldDrawer';
import {
  HUMAN_ANNOTATION_VALUE,
  NewScorerDrawer,
  ScorerType,
  scorerTypeRecord,
} from './NewScorerDrawer';

const HumanAnnotationsPage: React.FC<{
  entity: string;
  project: string;
  onCreateAnnotation: () => void;
}> = ({entity, project, onCreateAnnotation}) => {
  return (
    <SimplePageLayoutWithHeader
      title="Annotations"
      headerContent={null}
      hideTabsIfSingle
      tabs={[
        {
          label: 'main',
          content: <AnnotationsTab entity={entity} project={project} />
        }
      ]}
      headerExtra={
        <Button
          icon={IconNames.AddNew}
          onClick={onCreateAnnotation}
          variant="ghost">
          Create annotation
        </Button>
      }
    />
  );
};

const ProgrammaticScorersPage: React.FC<{
  entity: string;
  project: string;
  onCreateScorer: () => void;
}> = ({entity, project, onCreateScorer}) => {
  return (
    <SimplePageLayoutWithHeader
      title="Scorers"
      headerContent={null}
      hideTabsIfSingle
      tabs={[
        {
          label: 'main',
          content: <ProgrammaticScorersTab entity={entity} project={project} />
        }
      ]}
      headerExtra={
        <Button
          icon={IconNames.AddNew}
          onClick={onCreateScorer}
          variant="ghost">
          Create scorer
        </Button>
      }
    />
  );
};

export const ScorersPage: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isAnnotationDrawerOpen, setIsAnnotationDrawerOpen] = useState(false);
  const [selectedTab, setSelectedTab] = useState<ScorerType>(
    scorerTypeRecord.ANNOTATION.value
  );

  return (
    <>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflow: 'hidden',
        }}>
        {/* Top Navigation */}
        <Box sx={{
          paddingLeft: "16px",
          paddingRight: "16px",
          marginTop: "4px",
          marginBottom: "4px",
          // borderBottom: '1px solid',
          // borderColor: 'divider',
        }}>
          <Tabs.Root
            value={selectedTab}
            onValueChange={value => {
              setSelectedTab(value as ScorerType);
            }}>
            <Tabs.List className="border-b-0">
              <Tabs.Trigger value={scorerTypeRecord.ANNOTATION.value}>
                Annotations
              </Tabs.Trigger>
              <Tabs.Trigger value={scorerTypeRecord.PROGRAMMATIC.value}>
                Scorers
              </Tabs.Trigger>
            </Tabs.List>
          </Tabs.Root>
        </Box>

        {/* Page Content */}
        <Box sx={{flex: 1, overflow: 'hidden'}}>
          {selectedTab === scorerTypeRecord.ANNOTATION.value ? (
            <HumanAnnotationsPage 
              entity={entity} 
              project={project} 
              onCreateAnnotation={() => setIsAnnotationDrawerOpen(true)}
            />
          ) : (
            <ProgrammaticScorersPage 
              entity={entity} 
              project={project}
              onCreateScorer={() => setIsModalOpen(true)}
            />
          )}
        </Box>
      </Box>

      <CreateAnnotationFieldDrawer
        entity={entity}
        project={project}
        open={isAnnotationDrawerOpen}
        onClose={() => setIsAnnotationDrawerOpen(false)}
      />

      <NewScorerDrawer
        entity={entity}
        project={project}
        open={isModalOpen}
        initialScorerType={selectedTab}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  );
};
