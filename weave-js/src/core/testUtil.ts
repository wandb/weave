import './ops';

import _ from 'lodash';

import {Client as TestClient} from './_external/backendProviders/serverApiTest';
import {Client} from './client/types';
import * as HL from './hl';
import {createLocalClient, createRemoteClient} from './main';
import {emptyStack, NodeOrVoidNode, pushFrame, Type} from './model';
import {makeEcosystemMixedOpStore} from './opStore/mixedOpStore';
import {loadRemoteOpStore} from './opStore/remoteOpStore';
import {StaticOpStore} from './opStore/static';

const _remoteClient: {[url: string]: Client} = {};

export function getTestRemoteURL(): string | undefined {
  /* eslint-disable node/no-process-env */
  return process?.env?.WEAVE_BACKEND_CLIENT_URL;
  /* eslint-enable node/no-process-env */
}

export async function testClient() {
  const remoteURL: string | undefined = getTestRemoteURL();
  if (remoteURL != null) {
    if (_remoteClient[remoteURL] == null) {
      const {remoteOpStore} = await loadRemoteOpStore(remoteURL + '/ops');
      _remoteClient[remoteURL] = createRemoteClient(
        remoteURL + '/execute',
        async () => undefined,
        false,
        makeEcosystemMixedOpStore(StaticOpStore.getInstance(), remoteOpStore)
      );
    }
    return _remoteClient[remoteURL];
  }
  return createLocalClient(new TestClient());
}

// This is required for comparisons to work properly (maybe
// we should just use assignability?)
export function normalizeType(type: Type): Type {
  const typeCopy = _.cloneDeep(type) as any;
  for (const key in typeCopy) {
    if (_.isArray(typeCopy[key])) {
      typeCopy[key] = typeCopy[key].map(normalizeType).sort();
    } else if (_.isObject(typeCopy[key])) {
      typeCopy[key] = normalizeType(typeCopy[key]);
    }
  }
  return typeCopy;
}

export async function testNode(
  node: NodeOrVoidNode,
  expectations: Partial<{
    type: Type;
    resolvedType: Type;
    value: any;
  }>,
  frame: any = {}
) {
  const client = await testClient();
  const expectedType =
    expectations.type != null
      ? normalizeType(expectations.type)
      : expectations.type;
  const expectedResolvedType =
    expectations.resolvedType != null
      ? normalizeType(expectations.resolvedType)
      : expectedType != null
      ? expectedType
      : expectations.resolvedType;
  const expectedValue = expectations.value;

  if (expectedType !== undefined) {
    expect(normalizeType(node.type)).toEqual(expectedType);
  }

  if (expectedResolvedType !== undefined) {
    if (node.nodeType !== 'void') {
      const nodeWithResolved = await HL.refineNode(
        client,
        node,
        pushFrame(emptyStack(), frame)
      );
      expect(normalizeType(nodeWithResolved.type)).toEqual(
        expectedResolvedType
      );
    } else {
      expect(normalizeType(node.type)).toEqual(expectedResolvedType);
    }
  }

  if (expectedValue !== undefined) {
    if (node.nodeType !== 'void') {
      expect(await client.query(node)).toEqual(expectedValue);
    } else {
      expect(undefined).toEqual(expectedValue);
    }
  }
}
