import React from 'react';

import {Alert} from '../../../../../../Alert';
import {AccountPlanType} from '../../../inference/types';
import {useInferenceContext} from '../../../inference/util';
import {differenceInCalendarDaysUTC, isAfter} from './date';

const TODAY = new Date();

export const InferenceBanner = () => {
  const inferenceContext = useInferenceContext();
  const {billing} = inferenceContext;
  if (!billing) return null;
  let {
    accountPlanType,
    usage,
    inferenceSafetyLimit,
    billingPeriodStart,
    billingPeriodEnd,
    formatAsDollar,
    getFormattedBillingDate,
  } = billing;

  let exceededLimitBoldStatusMsg: string | undefined;
  let exceededLimitStatusMsg: string | undefined;

  switch (accountPlanType) {
    case AccountPlanType.Free:
    case AccountPlanType.ThirtyDayTrial:
      if (usage >= inferenceSafetyLimit) {
        exceededLimitBoldStatusMsg = 'Out of W&B Inference credits.';
        exceededLimitStatusMsg =
          'To continue using Inference, please upgrade your plan.';
      }
      break;
    case AccountPlanType.Teams:
    case AccountPlanType.Pro:
      if (usage >= inferenceSafetyLimit) {
        exceededLimitBoldStatusMsg = `You've hit your ${formatAsDollar(
          inferenceSafetyLimit / 100
        )} monthly W&B Inference spend limit.`;
        exceededLimitStatusMsg = `Want a higher cap? Talk to support or wait for your limit to reset on ${getFormattedBillingDate(
          billingPeriodEnd
        )}`;
      }
      break;
    case AccountPlanType.Enterprise:
      if (
        inferenceSafetyLimit === 0 ||
        isAfter(TODAY, billingPeriodEnd) ||
        isAfter(billingPeriodStart, TODAY)
      ) {
        break; // no banner if outside the billing period or no limit set
      } else if (usage >= inferenceSafetyLimit) {
        exceededLimitBoldStatusMsg = `You've hit your ${formatAsDollar(
          inferenceSafetyLimit / 100
        )} W&B Inference spend limit.`;
        exceededLimitStatusMsg = 'Want a higher cap? Talk to support.';
      } else if (differenceInCalendarDaysUTC(billingPeriodEnd, TODAY) <= 30) {
        exceededLimitBoldStatusMsg = `You have ${differenceInCalendarDaysUTC(
          billingPeriodEnd,
          TODAY
        )} days remaining in your W&B Inference trial.`;
        exceededLimitStatusMsg =
          'Once your trial expires access to W&B Inference will be restricted.';
      } else if (usage >= inferenceSafetyLimit * 0.9) {
        exceededLimitBoldStatusMsg = 'Almost out of W&B Inference credits.';
        exceededLimitStatusMsg =
          'To continue using W&B Inference without disruption, talk to sales.';
      }
      break;
  }

  if (!exceededLimitStatusMsg) return null;

  return (
    <div className="mb-16 mt-12 w-[800px]">
      <Alert severity="warning">
        <b>{exceededLimitBoldStatusMsg} </b>
        <span>{exceededLimitStatusMsg}</span>
      </Alert>
    </div>
  );
};
