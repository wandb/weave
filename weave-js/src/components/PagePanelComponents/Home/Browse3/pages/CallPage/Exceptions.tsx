import * as Colors from '@wandb/weave/common/css/color.styles';
import {Alert} from '@wandb/weave/components/Alert';
import React from 'react';
import styled from 'styled-components';

const AlertExceptionType = styled.span`
  font-weight: 600;
`;
AlertExceptionType.displayName = 'S.AlertExceptionType';

const Traceback = styled.div`
  font-family: monospace;
  white-space: nowrap;
  overflow: auto;
  font-size: 12px;
`;
Traceback.displayName = 'S.Traceback';

const FileInfo = styled.div`
  margin-left: 20px;
`;
FileInfo.displayName = 'S.FileInfo';

const Filename = styled.span`
  color: ${Colors.GOLD_600};
`;
Filename.displayName = 'S.Filename';

const LineNo = styled.span`
  color: ${Colors.PURPLE_600};
`;
LineNo.displayName = 'S.LineNo';

const FunctionName = styled.span`
  color: ${Colors.CACTUS_600};
`;
FunctionName.displayName = 'S.FunctionName';

const FrameText = styled.div`
  margin-left: 40px;
`;
FrameText.displayName = 'S.FrameText';

const ExceptionType = styled.span`
  color: ${Colors.RED_500};
`;
ExceptionType.displayName = 'S.ExceptionType';

type StackFrame = {
  filename: string;
  line_number: number | null;
  function_name: string;
  text: string | null;
};

type Exception = {
  type: string;
  message: string;
  traceback?: StackFrame[];
};

type NoException = {};
type ExceptionInfo = Exception | NoException;

export const getExceptionInfo = (
  exception: string | undefined
): ExceptionInfo => {
  if (!exception) {
    return {};
  }
  try {
    const parsed = JSON.parse(exception);
    if (typeof parsed === 'object') {
      return parsed;
    }
  } catch (err) {
    // ignore
  }
  return {
    type: 'Exception',
    message: exception,
  };
};

type ExceptionAlertProps = {
  exception: string;
};

export const ExceptionAlert = ({exception}: ExceptionAlertProps) => {
  const info = getExceptionInfo(exception);
  if (!('type' in info)) {
    return null;
  }
  const {type, message} = info;
  return (
    <Alert severity="error">
      <AlertExceptionType>{type}:</AlertExceptionType> {message}
    </Alert>
  );
};

type ExceptionDetailsProps = {
  exceptionInfo: Exception;
};

export const ExceptionDetails = ({exceptionInfo}: ExceptionDetailsProps) => {
  if (!exceptionInfo.traceback) {
    return null;
  }
  return (
    <Traceback>
      <div>Traceback (most recent call last):</div>
      {exceptionInfo.traceback.map((frame: StackFrame, i: number) => (
        <React.Fragment key={i}>
          <FileInfo>
            File "<Filename>{frame.filename}</Filename>", line{' '}
            <LineNo>{frame.line_number}</LineNo>, in{' '}
            <FunctionName>{frame.function_name}</FunctionName>
          </FileInfo>
          <FrameText>{frame.text}</FrameText>
        </React.Fragment>
      ))}
      <ExceptionType>{exceptionInfo.type}:</ExceptionType>{' '}
      {exceptionInfo.message}
    </Traceback>
  );
};
