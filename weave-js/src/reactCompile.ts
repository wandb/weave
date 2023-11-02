import {
  constString,
  isConstNode,
  isOutputNode,
  isVoidNode,
  Node,
  NodeOrVoidNode,
  opFilesystemArtifactUri,
  opGet,
  voidNode,
} from '@wandb/weave/core';
import _ from 'lodash';
import {
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  useWeaveContext,
} from './context';


const uriWithoutPath = (uri: string) => {
  const parts = uri.split(':');
  const finalPart = parts[parts.length - 1];
  const finalParts = finalPart.split('/');
  return parts.slice(0, -1).concat(finalParts[0]).join(':');
};

const findLatestGetUris = (node: NodeOrVoidNode<any>): string[] => {
    const uris = [];
    if (isOutputNode(node)) {
    if (node.fromOp.name === 'get') {
      const uriNode = node.fromOp.inputs.uri;
      if (isConstNode(uriNode)) {
        const uriVal = uriNode.val;
        if (typeof uriVal === 'string') {
          if (uriVal.includes(':latest')) {
            return [uriWithoutPath(uriVal)];
          }
        }
      }
    }
    for (const input of Object.values(node.fromOp.inputs)) {
      uris.push(...findLatestGetUris(input));
    }
  }
  return uris;
};

const replaceLatestGetUris = (
  node: NodeOrVoidNode<any>,
  uriMapping: Record<string, string>
): NodeOrVoidNode<any> => {
  if (isVoidNode(node)) {
    return node;
  }
  if (isOutputNode(node)) {
    if (node.fromOp.name === 'get') {
      const uriNode = node.fromOp.inputs.uri;
      if (isConstNode(uriNode)) {
        const uriVal = uriNode.val;
        if (typeof uriVal === 'string') {
          if (uriVal.includes(':latest')) {
            const lookupUri = uriWithoutPath(uriVal);
            console.log({lookupUri, uriMapping});
            const replaceUri = uriMapping[lookupUri];
            if (replaceUri != null) {
              return opGet({
                uri: constString(uriVal.replace(lookupUri, replaceUri)),
              });
            }
          }
        }
      }
    }
    const newInputs: Record<string, Node<any>> = {};
    for (const [inputName, input] of Object.entries(node.fromOp.inputs)) {
      newInputs[inputName] = replaceLatestGetUris(input, uriMapping) as any;
    }
    return {
      ...node,
      fromOp: {
        ...node.fromOp,
        inputs: newInputs,
      },
    };
  }
  return node;
};

export const useCompileGetLatestNodes = (node: NodeOrVoidNode) => {
    // console.log({node})
  // 1. Create a mapping from latest URIs to a list of get ops that use that URI.
  // 2. Resolve each URI to the digest of the uri
  // 3. Replace the URIs with the digests
  const weave = useWeaveContext();
  const latestURIs = useMemo(() => {
    return findLatestGetUris(node);
  }, [node]);
  const needsCompile = latestURIs.length > 0;
//   const [loading, setLoading] = useState(needsCompile);
  const [compiledNode, setCompiledNode] = useState(voidNode());
  useEffect(() => {
    if (!needsCompile) {
        setCompiledNode(node as any);
    } else {
      const digests = latestURIs.map(uri => {
        // trim off everything after the first slash after the last colon
        // this is the artifact path
        const parts = uri.split(':');
        parts[parts.length - 1] = parts[parts.length - 1].split('/')[0];
        uri = parts.join(':');
        const getNode = opGet({uri: constString(uri)});
        // return weave.client.query(getNode);
        return weave.client.query(
          opFilesystemArtifactUri({
            artifact: getNode as any,
          })
        );
      });
      Promise.all(digests).then(results => {
        console.log({latestURIs, results})
        const newNode = replaceLatestGetUris(
          node,
          _.zipObject(latestURIs as string[], results as string[])
        );
        console.log(newNode);
        setCompiledNode(newNode as any);
      });
    }
  }, [latestURIs, needsCompile, node, weave.client]);

  return compiledNode
};
