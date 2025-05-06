import {Box} from '@mui/material';
import {useOrgName} from '@wandb/weave/common/hooks/useOrganization';
import {useViewerUserInfo2} from '@wandb/weave/common/hooks/useViewerUserInfo';
import React, {useEffect,useState} from 'react';
import {useParams} from 'react-router-dom';

import {TargetBlank} from '../../../../../../common/util/links';
import * as userEvents from '../../../../../../integrations/analytics/userEvents';
import * as viewEvents from '../../../../../../integrations/analytics/viewEvents';
import {Button} from '../../../../../Button';
import {CreateDatasetDrawer} from '../../datasets/CreateDatasetDrawer';
import {useDatasetSaving} from '../../datasets/useDatasetSaving';
import {EmptyProps} from './Empty';
import {Link} from './Links';

const NewDatasetButton: React.FC = () => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const {entity, project} = useParams<{entity: string; project: string}>();
  const {isCreatingDataset, handleSaveDataset} = useDatasetSaving({
    entity,
    project,
    onSaveComplete: () => setIsDrawerOpen(false),
  });

  return (
    <>
      <Button
        variant="primary"
        icon="add-new"
        onClick={() => setIsDrawerOpen(true)}
        data-testid="create-dataset-button">
        New dataset
      </Button>
      <CreateDatasetDrawer
        open={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onSaveDataset={handleSaveDataset}
        isCreating={isCreatingDataset}
        data-testid="create-dataset-drawer"
      />
    </>
  );
};

export const EMPTY_PROPS_TRACES: EmptyProps = {
  icon: 'layout-tabs' as const,
  heading: 'Create your first trace',
  description:
    'Use traces to track all inputs & outputs of functions within your application. Debug, monitor or drill-down into tricky examples.',
  moreInformation: () => {
    const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
    const userInfoLoaded = !viewerLoading ? userInfo : null;
    const {entity: entityName, project: projectName} = useParams<{entity: string; project: string}>();
    const {orgName} = useOrgName({
      entityName,
      skip: viewerLoading || !entityName,
    });

    // Log empty state view event for analytics
    useEffect(() => {
      if (!userInfoLoaded || !entityName || !projectName) {
        return;
      }
      viewEvents.emptyStateViewed({
        userId: userInfoLoaded.id,
        organizationName: orgName,
        entityName,
        projectName,
        emptyStateType: 'traces',
      });
    }, [userInfoLoaded, orgName, entityName, projectName]);

    const fireAnalyticsForEmpty = (type: 'doc' | 'colab', docType?: string, url?: string) => () => {
      if (!userInfoLoaded || !url || !projectName || !entityName) {
        return;
      }
      const baseEventData = {
        userId: userInfoLoaded.id,
        organizationName: orgName,
        entityName,
        projectName,
        source: 'traces_empty_state',
      };

      if (type === 'doc' && docType) {
        userEvents.docsLinkClicked({
          ...baseEventData,
          docType,
          url,
        });
      } else if (type === 'colab') {
        userEvents.colabButtonClicked({
          ...baseEventData,
          url,
        });
      }
    };

    const COLAB_URL = 'https://colab.research.google.com/github/wandb/weave/blob/master/docs/notebooks/Intro_to_Weave_Hello_Trace.ipynb';

    return (
      <>
        Learn{' '}
        <TargetBlank 
          href="http://wandb.me/weave_traces"
          onClick={fireAnalyticsForEmpty('doc', 'empty_state_tracing_basics', 'http://wandb.me/weave_traces')}>
          tracing basics
        </TargetBlank>{' '}
        or see traces in action by{' '}
        <TargetBlank 
          href="http://wandb.me/weave_quickstart"
          onClick={fireAnalyticsForEmpty('doc', 'empty_state_quickstart_guide', 'http://wandb.me/weave_quickstart')}>
          following our quickstart guide
        </TargetBlank>
        .
        <Box sx={{mt: 2}}>
          <TargetBlank 
            href={COLAB_URL}
            onClick={fireAnalyticsForEmpty('colab', undefined, COLAB_URL)}>
            <Button variant="secondary" icon="logo-colab">
              Get started with Colab
            </Button>
          </TargetBlank>
        </Box>
      </>
    );
  },
};

export const EMPTY_PROPS_EVALUATIONS: EmptyProps = {
  icon: 'type-boolean' as const,
  heading: 'Create your first evaluation',
  description: 'Use evaluations to track the performance of your application.',
  moreInformation: () => {
    const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
    const userInfoLoaded = !viewerLoading ? userInfo : null;
    const {entity: entityName, project: projectName} = useParams<{entity: string; project: string}>();
    const {orgName} = useOrgName({
      entityName,
      skip: viewerLoading || !entityName,
    });

    // Log empty state view event for analytics
    useEffect(() => {
      if (!userInfoLoaded || !entityName || !projectName) {
        return;
      }
      viewEvents.emptyStateViewed({
        userId: userInfoLoaded.id,
        organizationName: orgName,
        entityName,
        projectName,
        emptyStateType: 'evaluations',
      });
    }, [userInfoLoaded, orgName, entityName, projectName]);

    const fireAnalyticsForEmpty = (type: 'doc' | 'colab', docType?: string, url?: string) => () => {
      if (!userInfoLoaded || !url || !projectName || !entityName) {
        return;
      }
      const baseEventData = {
        userId: userInfoLoaded.id,
        organizationName: orgName,
        entityName,
        projectName,
        source: 'evaluations_empty_state',
      };

      if (type === 'doc' && docType) {
        userEvents.docsLinkClicked({
          ...baseEventData,
          docType,
          url,
        });
      } else if (type === 'colab') {
        userEvents.colabButtonClicked({
          ...baseEventData,
          url,
        });
      }
    };

    const COLAB_URL = 'https://colab.research.google.com/github/wandb/weave/blob/master/docs/notebooks/Intro_to_Weave_Hello_Eval.ipynb';

    return (
      <>
        Learn{' '}
        <TargetBlank 
          href="https://wandb.me/weave_evals"
          onClick={fireAnalyticsForEmpty('doc', 'empty_state_evaluation_basics', 'https://wandb.me/weave_evals')}>
          evaluation basics
        </TargetBlank>{' '}
        or follow our tutorial to{' '}
        <TargetBlank 
          href="http://wandb.me/weave_eval_tut"
          onClick={fireAnalyticsForEmpty('doc', 'empty_state_evaluation_tutorial', 'http://wandb.me/weave_eval_tut')}>
          set up an evaluation pipeline
        </TargetBlank>
        .
        <Box sx={{mt: 2}}>
          <TargetBlank 
            href={COLAB_URL}
            onClick={fireAnalyticsForEmpty('colab', undefined, COLAB_URL)}>
            <Button variant="secondary" icon="logo-colab">
              Get started with Colab
            </Button>
          </TargetBlank>
        </Box>
      </>
    );
  },
};

export const EMPTY_PROPS_LEADERBOARD: EmptyProps = {
  icon: 'benchmark-square' as const,
  heading: 'No leaderboard submissions found.',
  description: 'Create leaderboard submissions by running evaluations.',
  moreInformation: (
    <>
      Learn{' '}
      <TargetBlank href="https://wandb.me/weave_evals">
        evaluation basics
      </TargetBlank>{' '}
      or follow our tutorial to{' '}
      <TargetBlank href="http://wandb.me/weave_eval_tut">
        set up an evaluation pipeline
      </TargetBlank>
      .
    </>
  ),
};

export const EMPTY_PROPS_LEADERBOARDS: EmptyProps = {
  icon: 'benchmark-square' as const,
  heading: 'No leaderboards yet',
  description:
    'Use leaderboards to summarize and compare the performance of your models.',
  moreInformation: (
    <>
      Follow the{' '}
      <TargetBlank href="https://weave-docs.wandb.ai/reference/gen_notebooks/leaderboard_quickstart">
        leaderboard quickstart
      </TargetBlank>{' '}
      to create leaderboards for your evaluations.
    </>
  ),
};

export const EMPTY_PROPS_PROMPTS: EmptyProps = {
  icon: 'forum-chat-bubble' as const,
  heading: 'No prompts yet',
  description:
    'You can use prompts to try different instructions for your LLM, tracking edits and their impact on performance.',
  moreInformation: (
    <>
      Learn{' '}
      <TargetBlank href="http://wandb.me/weave_prompts">
        prompt basics
      </TargetBlank>
      .
    </>
  ),
};

export const EMPTY_PROPS_MODEL: EmptyProps = {
  icon: 'model' as const,
  heading: 'No models yet',
  description:
    "You can use models to collect details of your app that you'd like to evaluate, like the prompts or the LLM settings that you're using.",
  moreInformation: (
    <>
      Learn{' '}
      <TargetBlank href="http://wandb.me/weave_models">
        model basics
      </TargetBlank>{' '}
      or see how you can{' '}
      <TargetBlank href="http://wandb.me/weave_eval_tut">
        use models within an evaluation pipeline
      </TargetBlank>
      .
    </>
  ),
};

export const EMPTY_PROPS_DATASETS: EmptyProps = {
  icon: 'table' as const,
  heading: 'Create your first dataset',
  description:
    'Use datasets to collect difficult examples to use within evaluations of your app.',
  moreInformation: (
    <>
      Learn{' '}
      <TargetBlank href="http://wandb.me/weave_datasets">
        dataset basics
      </TargetBlank>{' '}
      or see how you can{' '}
      <TargetBlank href="http://wandb.me/weave_eval_tut">
        use datasets within an evaluation pipeline
      </TargetBlank>{' '}
      .
      <Box sx={{mt: 2}}>
        <NewDatasetButton />
      </Box>
    </>
  ),
};

export const EMPTY_PROPS_OPERATIONS: EmptyProps = {
  icon: 'job-program-code' as const,
  heading: 'No operations yet',
  description:
    'You can use operations to track all inputs & outputs of functions within your application and to view how data flows through them.',
  moreInformation: (
    <>
      Learn{' '}
      <TargetBlank href="https://wandb.github.io/weave/guides/tracking/ops">
        operations basics
      </TargetBlank>{' '}
      or see how to{' '}
      <TargetBlank href="http://wandb.me/weave_quickstart">
        use them within our quickstart
      </TargetBlank>
      .
    </>
  ),
};

export const EMPTY_PROPS_OBJECTS: EmptyProps = {
  icon: 'cube-container' as const,
  heading: 'No objects yet',
  description:
    'Use this to keep track of how you use models, evaluation datasets or any other asset within your application.',
  moreInformation: (
    <>
      Learn{' '}
      <TargetBlank href="http://wandb.me/weave_objects">
        object basics
      </TargetBlank>
      .
    </>
  ),
};

export const EMPTY_PROPS_OBJECT_VERSIONS: EmptyProps = {
  icon: 'cube-container' as const,
  heading: 'No object versions',
  description:
    'The requested object does not exist or all versions of it have been deleted.',
  moreInformation: (
    <>
      Learn{' '}
      <TargetBlank href="http://wandb.me/weave_objects">
        object basics
      </TargetBlank>
      .
    </>
  ),
};
export const EMPTY_NO_TRACE_SERVER: EmptyProps = {
  icon: 'weave' as const,
  heading: 'Weave coming soon!',
  description:
    'Weave is a lightweight toolkit for tracking and evaluating LLM applications.',
  moreInformation: (
    <>
      Learn about{' '}
      <TargetBlank href="https://wandb.me/weave">Weave features</TargetBlank> or
      return to <Link to="..">your project homepage</Link>.
    </>
  ),
};

export const EMPTY_PROPS_PROGRAMMATIC_SCORERS: EmptyProps = {
  icon: 'type-number-alt' as const,
  heading: 'No programmatic scorers yet',
  description: 'Create programmatic scorers in Python.',
  moreInformation: (
    <>
      Learn more about{' '}
      <TargetBlank href="https://weave-docs.wandb.ai/guides/evaluation/scorers#class-based-scorers">
        creating and using scorers
      </TargetBlank>{' '}
      in evaluations.
    </>
  ),
};

export const EMPTY_PROPS_ACTION_SPECS: EmptyProps = {
  icon: 'automation-robot-arm' as const,
  heading: 'No Actions yet',
  description:
    'Use Actions to define workloads to be executed by Weave servers (for example: LLM Judges) ',
  moreInformation: <></>,
};

export const EMPTY_PROPS_ANNOTATIONS: EmptyProps = {
  icon: 'forum-chat-bubble' as const,
  heading: 'No annotations yet',
  description: 'Create annotations in the UI or python.',
  moreInformation: (
    <>
      More information about creating and using annotation specifications for
      human labeling can be found in the{' '}
      <TargetBlank href="https://weave-docs.wandb.ai/guides/tracking/feedback#add-human-annotations">
        documentation
      </TargetBlank>
      .
    </>
  ),
};

export const EMPTY_PROPS_NO_LLM_PROVIDERS_ADMIN: EmptyProps = {
  icon: 'forum-chat-bubble' as const,
  heading: 'Get started with the LLM playground',
  description: 'Configure an LLM provider to start using the playground',
  moreInformation: () => {
    const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
    const userInfoLoaded = !viewerLoading ? userInfo : null;
    const {entity: entityName, project: projectName} = useParams<{entity: string; project: string}>();
    const {orgName} = useOrgName({
      entityName,
      skip: viewerLoading || !entityName,
    });

    // Log empty state view event for analytics
    useEffect(() => {
      if (!userInfoLoaded || !entityName || !projectName) {
        return;
      }
      viewEvents.emptyStateViewed({
        userId: userInfoLoaded.id,
        organizationName: orgName,
        entityName,
        projectName,
        emptyStateType: 'llm_playground_admin',
      });
    }, [userInfoLoaded, orgName, entityName, projectName]);

    return <></>;
  },
};

export const EMPTY_PROPS_NO_LLM_PROVIDERS: EmptyProps = {
  ...EMPTY_PROPS_NO_LLM_PROVIDERS_ADMIN,
  description: 'Contact a team admin to configure an LLM provider to start using the playground',
  moreInformation: () => {
    const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
    const userInfoLoaded = !viewerLoading ? userInfo : null;
    const {entity: entityName, project: projectName} = useParams<{entity: string; project: string}>();
    const {orgName} = useOrgName({
      entityName,
      skip: viewerLoading || !entityName,
    });

    // Log empty state view event for analytics
    useEffect(() => {
      if (!userInfoLoaded || !entityName || !projectName) {
        return;
      }
      viewEvents.emptyStateViewed({
        userId: userInfoLoaded.id,
        organizationName: orgName,
        entityName,
        projectName,
        emptyStateType: 'llm_playground_non_admin',
      });
    }, [userInfoLoaded, orgName, entityName, projectName]);

    return <></>;
  },
};
