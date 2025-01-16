import {Box} from '@material-ui/core';
import {CopyableText} from '@wandb/weave/components/CopyableText';
import {isValidVarName} from '@wandb/weave/core/util/var';
import {abbreviateRef} from '@wandb/weave/util/refs';
import React from 'react';

import {DocLink} from '../../common/Links';
import {TabUseBanner} from '../../common/TabUseBanner';
import {AnnotationSpec} from '../../wfReactInterface/generatedBuiltinObjectClasses.zod';

type TabUseAnnotationSpecProps = {
  name: string;
  uri: string;
  projectName: string;
  data?: AnnotationSpec;
};

export const TabUseAnnotationSpec = ({
  name,
  uri,
  projectName,
  data,
}: TabUseAnnotationSpecProps) => {
  const fullSpecName = `wandb.annotation.${name}`;
  const pythonName = isValidVarName(name) ? name : 'annotation_spec';
  const payloadValue = makeAnnotationPayloadFromSpec(data?.field_schema);
  const abbreviatedAnnotationCode = makeAnnotateCallCode(
    abbreviateRef(uri),
    payloadValue,
    fullSpecName,
    projectName
  );
  const fullAnnotationCode = makeAnnotateCallCode(
    uri,
    payloadValue,
    fullSpecName,
    projectName
  );

  return (
    <Box className="text-sm">
      <TabUseBanner>
        See{' '}
        <DocLink
          path="guides/tracking/feedback#add-human-annotations"
          text="Weave docs on annotations"
        />{' '}
        for more information.
      </TabUseBanner>

      <Box mt={2}>
        The ref for this annotation is:
        <CopyableText text={uri} />
      </Box>
      <Box mt={2}>
        Use the following code to retrieve this annotation spec:
        <CopyableText
          language="python"
          text={`${pythonName} = weave.ref("${abbreviateRef(uri)}").get()`}
          copyText={`${pythonName} = weave.ref("${uri}").get()`}
          tooltipText="Click to copy unabridged string"
        />
      </Box>
      <Box mt={2}>
        Use the following code to annotate calls with this annotation spec:
        <CopyableText
          language="python"
          text={abbreviatedAnnotationCode}
          copyText={fullAnnotationCode}
          tooltipText="Click to copy unabridged string"
        />
      </Box>
    </Box>
  );
};

const makeAnnotateCallCode = (
  uri: string,
  payloadValue: string,
  fullSpecName: string,
  projectName: string
) => `client = weave.init('${projectName}')

call = client.get_calls()[0]
call.feedback.add(
  feedback_type='${fullSpecName}',
  payload={"value": ${payloadValue}},
  annotation_ref='${uri}'
)`;

const makeAnnotationPayloadFromSpec = (
  spec?: AnnotationSpec['field_schema']
): string => {
  if (spec?.type === 'string') {
    if (spec.enum) {
      return `"${spec.enum[0] ?? 'Yes'}"`;
    }
    const strMsg = 'A great call!';
    if (
      !spec.max_length ||
      (spec.max_length && spec.max_length >= strMsg.length)
    ) {
      return `"${strMsg}"`;
    }
    return '"Nice!"';
  }
  if (spec?.type === 'number' || spec?.type === 'integer') {
    return `${spec.maximum ?? spec.minimum ?? 10}`;
  }
  if (spec?.type === 'boolean') {
    return 'True';
  }
  return '"Nice!"';
};
