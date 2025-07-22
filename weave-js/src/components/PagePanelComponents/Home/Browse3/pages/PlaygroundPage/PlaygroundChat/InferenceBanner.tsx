import React from 'react';

import {Alert} from '../../../../../../Alert';
import {AccountPlanType} from '../../../inference/types';
import {useInferenceContext} from '../../../inference/util';
import {InferenceBannerAdvertise} from './InferenceBannerAdvertise';

export const InferenceBanner = () => {
  const inferenceContext = useInferenceContext();
  const {isInferenceEnabled, billing} = inferenceContext;
  if (!isInferenceEnabled || !billing) {
    return null;
  }

  let {
    accountPlanType,
    usage,
    inferenceFreeLimit,
    inferenceSafetyLimit,
    billingPeriodEnd,
    getFormattedBillingDate,
  } = billing;

  // This is constant for all cases at the moment but leaving as a variable since unclear if that will hold.
  const exceededLimitBoldStatusMsg = 'Almost out of W&B Inference credits.';
  let exceededLimitStatusMsg: string | undefined;

  switch (accountPlanType) {
    case AccountPlanType.Personal:
      // Personal accounts don't have Inference service.
      // The isInferenceEnabled check above should handle this case but handling it explicitly.
      return null;
    case AccountPlanType.Free:
      if (inferenceSafetyLimit * 0.9 <= usage && usage < inferenceSafetyLimit) {
        exceededLimitStatusMsg = 'Upgrade your plan to keep going.';
      }
      break;
    case AccountPlanType.ThirtyDayTrial:
      if (inferenceSafetyLimit * 0.9 <= usage && usage < inferenceSafetyLimit) {
        exceededLimitStatusMsg = 'To avoid interruption, upgrade your plan.';
      }
      break;
    case AccountPlanType.Pro:
      if (inferenceSafetyLimit * 0.9 <= usage && usage < inferenceSafetyLimit) {
        exceededLimitStatusMsg = `You'll receive more credits on ${getFormattedBillingDate(
          billingPeriodEnd
        )}. Once you're out, usage will switch to pay-as-you-go pricing.`;
      }
      break;
    case AccountPlanType.Academic:
      if (inferenceSafetyLimit * 0.9 <= usage && usage < inferenceSafetyLimit) {
        exceededLimitStatusMsg = `Credits refresh on ${getFormattedBillingDate(
          billingPeriodEnd
        )}. W&B Inference will pause after the credit limit is reached.`;
      }
      break;
  }

  if (exceededLimitStatusMsg) {
    return (
      <div className="mb-16 mt-12 w-[800px]">
        <Alert severity="warning">
          <b>{exceededLimitBoldStatusMsg} </b>
          <span>{exceededLimitStatusMsg}</span>
        </Alert>
      </div>
    );
  }

  // Don't need to warn user about anything. If they have free credits, advertise them.
  if (inferenceFreeLimit != null && inferenceFreeLimit > 0) {
    return <InferenceBannerAdvertise inferenceFreeLimit={inferenceFreeLimit} />;
  }
  return null;
};
