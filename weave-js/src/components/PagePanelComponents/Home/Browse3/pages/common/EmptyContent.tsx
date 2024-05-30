import React from 'react';

import {TargetBlank} from '../../../../../../common/util/links';
import {EmptyProps} from './Empty';
import {Link} from './Links';

export const EMPTY_PROPS_TRACES: EmptyProps = {
  icon: 'layout-tabs' as const,
  heading: 'No traces yet',
  description:
    'Use traces to track all inputs & outputs of functions within your application. Debug, monitor or drill-down into tricky examples.',
  moreInformation: (
    <>
      Learn{' '}
      <TargetBlank href="http://wandb.me/weave_traces">
        tracing basics
      </TargetBlank>{' '}
      or see traces in action by{' '}
      <TargetBlank href="http://wandb.me/weave_quickstart">
        following our quickstart guide
      </TargetBlank>
      .
    </>
  ),
};

export const EMPTY_PROPS_EVALUATIONS: EmptyProps = {
  icon: 'type-boolean' as const,
  heading: 'No evaluations yet',
  description: 'Use evaluations to track the performance of your application.',
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
  heading: 'No datasets yet',
  description:
    'You can use datasets to collect difficult examples to use within evaluations of your app.',
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
