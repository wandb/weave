import {ApolloError} from '@apollo/client';
import {extractStatusCodeFromApolloError} from '@wandb/weave/errors';
import React from 'react';
import {Alert} from '../../Alert';

const ReportQueryErrorAlert = ({error}: {error: ApolloError}) => {
  const statusCode = extractStatusCodeFromApolloError(error);
  return (
    <Alert severity="error" icon="warning">
      <span className="font-semibold">
        We were unable to fetch this report.
      </span>
      {statusCode === 404 && ' It may have been deleted recently.'}
    </Alert>
  );
};

const UpsertReportErrorAlert = ({
  error,
  isNewReport,
}: {
  error: ApolloError;
  isNewReport: boolean;
}) => {
  const statusCode = extractStatusCodeFromApolloError(error);
  return (
    <Alert severity="error" icon="warning">
      <span className="font-semibold">
        {isNewReport
          ? 'We were unable to create a new report.'
          : 'We were unable to add panel to this report.'}
      </span>
      {statusCode === 404 &&
        (isNewReport
          ? ' The project you selected may have been deleted recently.'
          : ' It may have been deleted recently.')}
    </Alert>
  );
};

export const ErrorAlerts = {
  ReportQuery: ReportQueryErrorAlert,
  UpsertReport: UpsertReportErrorAlert,
};
