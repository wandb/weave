import {typedDict} from '../../model';
import {docType} from '../../util/docs';
import {makeStandardOp} from '../opKinds';
import {connectionToNodes} from './util';

const makeUserOp = makeStandardOp;

const userArgType = {
  user: 'user' as const,
};

const userArgDescription = `A ${docType('user')}`;

// None of these are correct yet, they need to handle nulls / mapped / tags
export const opUserId = makeUserOp({
  hidden: true,
  name: 'user-id',
  argTypes: userArgType,
  description: `Returns the internal id of the ${docType('user')}`,
  argDescriptions: {user: userArgDescription},
  returnValueDescription: `The internal id of the ${docType('user')}`,
  returnType: inputTypes => 'string',
  resolver: ({user}) => user.id,
});

export const opUserUsername = makeUserOp({
  name: 'user-username',
  argTypes: userArgType,
  description: `Returns the username of the ${docType('user')}`,
  argDescriptions: {user: userArgDescription},
  returnValueDescription: `The username of the ${docType('user')}`,
  returnType: inputTypes => 'string',
  resolver: ({user}) => user.username,
});

export const opUserName = makeUserOp({
  hidden: true,
  name: 'user-name',
  argTypes: userArgType,
  description: `Returns the name of the ${docType('user')}`,
  argDescriptions: {user: userArgDescription},
  returnValueDescription: `The name of the ${docType('user')}`,
  returnType: inputTypes => 'string',
  resolver: ({user}) => user.name,
});

export const opUserEmail = makeUserOp({
  hidden: true,
  name: 'user-email',
  argTypes: userArgType,
  description: `Returns the email of the ${docType('user')}`,
  argDescriptions: {user: userArgDescription},
  returnValueDescription: `The email of the ${docType('user')}`,
  returnType: inputTypes => 'string',
  resolver: ({user}) => user.email,
});

export const opUserUserInfo = makeUserOp({
  hidden: true,
  name: 'user-userInfo',
  argTypes: userArgType,
  description: `Returns the userInfo of the ${docType('user')}`,
  argDescriptions: {user: userArgDescription},
  returnValueDescription: `The userInfo of the ${docType('user')}`,
  returnType: inputTypes => typedDict({}),
  resolver: ({user}) => user.userInfo,
});

export const opUserLink = makeUserOp({
  hidden: true,
  name: 'user-link',
  argTypes: userArgType,
  description: `Returns the link to the ${docType('user')}`,
  argDescriptions: {user: userArgDescription},
  returnValueDescription: `The link to the ${docType('user')}`,
  returnType: inputTypes => 'link',
  resolver: ({user}) => ({
    name: user.name,
    url: `/${user.username}`,
  }),
});

export const opUserRuns = makeUserOp({
  hidden: true,
  name: 'user-runs',
  argTypes: userArgType,
  description: `Returns the ${docType('list')} of ${docType('run', {
    plural: true,
  })} for the ${docType('user')}`,
  argDescriptions: {user: userArgDescription},
  returnValueDescription: `The ${docType('list')} of ${docType('run', {
    plural: true,
  })} for the ${docType('user')}`,
  returnType: inputTypes => ({type: 'list', objectType: 'run'}),
  resolver: ({user}) => connectionToNodes(user.runs),
});

export const opUserEntities = makeUserOp({
  hidden: true,
  name: 'user-entities',
  argTypes: userArgType,
  description: `Returns the ${docType('list')} of ${docType('entity', {
    plural: true,
  })} for the ${docType('user')}`,
  argDescriptions: {user: userArgDescription},
  returnValueDescription: `The ${docType('list')} of ${docType('entity', {
    plural: true,
  })} for the ${docType('user')}`,
  returnType: inputTypes => ({type: 'list', objectType: 'entity'}),
  resolver: ({user}) => connectionToNodes(user.teams),
});
