import * as OpKinds from '../opKinds';
import {typedDict} from "@wandb/weave/core";

const artifactTagArgTypes = {
  artifactTag: typedDict({
    id: 'string',
    name: 'string',
    tagCategoryName: 'string',
    attributes: 'string',
  })
};

export const opArtifactTagName = OpKinds.makeStandardOp({
  hidden: true,
  name: 'artifactTag-name',
  argTypes: artifactTagArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({artifactTag}) => artifactTag.name,
});
