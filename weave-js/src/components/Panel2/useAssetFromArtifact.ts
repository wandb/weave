import {
  constNumber,
  constString,
  MediaType,
  MemoizedHasher,
  Node,
  opArtifactVersionFile,
  opAssetArtifactVersion,
  opFileContents,
  opFileDirectUrlAsOf,
  OutputNode,
  TableType,
  Type,
  VoidNode,
  voidNode,
  WBTraceTreeType,
} from '@wandb/weave/core';
import {useEffect, useMemo, useRef, useState} from 'react';

import * as CGReact from '../../react';

export const useAssetURLFromArtifact = <
  InputNodeInternalType extends Exclude<MediaType, TableType | WBTraceTreeType>
>(
  inputNode: Node<InputNodeInternalType>,
  ignoreExpiration?: boolean
) => {
  const nodeValueQuery = CGReact.useNodeValue(inputNode);
  const fileNode = useMemo(() => {
    if (!nodeValueQuery.loading && nodeValueQuery.result != null) {
      return opArtifactVersionFile({
        artifactVersion: opAssetArtifactVersion({asset: inputNode}),
        path: constString(nodeValueQuery.result.path),
      });
    } else {
      return voidNode();
    }
  }, [inputNode, nodeValueQuery]);

  const {signedUrl: fileSignedURL} = useSignedUrlWithExpiration(
    fileNode as any,
    ignoreExpiration ? 24 * 60 * 60 * 1000 : 60 * 1000
  );

  return {
    loading: nodeValueQuery.loading || fileSignedURL == null,
    asset: nodeValueQuery.result,
    directUrl: fileSignedURL,
  };
};

export const useAssetContentFromArtifact = <
  InputNodeInternalType extends Exclude<MediaType, TableType | WBTraceTreeType>
>(
  inputNode: Node<InputNodeInternalType>
) => {
  const nodeValueQuery = CGReact.useNodeValue(inputNode);
  const artifactNode = useMemo(
    () => opAssetArtifactVersion({asset: inputNode}),
    [inputNode]
  );
  const contentNode = useMemo(() => {
    if (!nodeValueQuery.loading) {
      return opFileContents({
        file: opArtifactVersionFile({
          artifactVersion: artifactNode,
          path: constString(nodeValueQuery.result.path),
        }) as any,
      });
    } else {
      return voidNode();
    }
  }, [artifactNode, nodeValueQuery]);
  const contentQuery = CGReact.useNodeValue(contentNode);

  return {
    loading: nodeValueQuery.loading || contentQuery.loading,
    asset: nodeValueQuery.result,
    contents: contentQuery.result,
  };
};

// Helper function to return a direct URL node that is guaranteed
// to not be expired. This works by leveraging a custom op which
// accepts an `asOf` argument. The Weave system caches ops based on
// the input values, so getting a node with the current timestamp
// will always fetch a new URL. To protect from requesting new nodes
// too often, we guard subsequent calls with a time to live (ttl).
const useDirectUrlNodeWithExpiration = (
  fileNode:
    | Node<{
        type: 'file';
        extension?: string;
      }>
    | VoidNode,
  ttl: number
) => {
  const fileNodeRef = useRef<
    Node<{
      type: 'file';
      extension?: string;
    }>
  >();
  const resultRef = useRef<OutputNode<Type> | VoidNode>();
  const asOfRef = useRef<number>();
  return useMemo(() => {
    const hasher = new MemoizedHasher();
    const currentTime = Date.now();
    const isSameNode =
      fileNodeRef.current === fileNode ||
      (fileNode.nodeType !== 'void' &&
        fileNodeRef.current != null &&
        hasher.typedNodeId(fileNode) ===
          hasher.typedNodeId(fileNodeRef.current));
    if (
      !isSameNode ||
      resultRef.current == null ||
      asOfRef.current == null ||
      currentTime - asOfRef.current > ttl
    ) {
      if (fileNode.nodeType !== 'void') {
        fileNodeRef.current = fileNode;
        asOfRef.current = currentTime;
        resultRef.current = opFileDirectUrlAsOf({
          file: fileNode,
          asOf: constNumber(currentTime),
        });
      } else {
        resultRef.current = voidNode();
      }
    }
    return resultRef.current;
  }, [fileNode, ttl, fileNodeRef, resultRef, asOfRef]);
};

export const useSignedUrlWithExpiration = (
  fileNode:
    | Node<{
        type: 'file';
        extension?: string;
      }>
    | VoidNode,
  ttl: number
) => {
  const [signedUrl, setSignedUrl] = useState<string | null>(null);
  const directUrlNode = useDirectUrlNodeWithExpiration(fileNode, ttl);
  const directUrl = CGReact.useNodeValue(directUrlNode);
  useEffect(() => {
    const resolveSignedUrl = async () => {
      if (directUrl.result != null) {
        // in some environments (local) directUrl can already be the signed URL
        if (!(directUrl.result as string).includes('/artifactsV2/')) {
          setSignedUrl(directUrl.result as string);
          return;
        }

        // eslint-disable-next-line wandb/no-unprefixed-urls
        const response = await fetch(
          directUrl.result + '?redirect=false&content-disposition=inline',
          {
            credentials: 'include',
            method: 'GET',
            mode: 'cors',
            // TODO(np): This can and should be sent via cookie, but it's not
            // being correctly set, breaking this code in devprod and integration tests.
            headers: {
              'use-admin-privileges': 'true',
            },
          }
        );
        const json = await response.json();
        if (json.url != null) {
          setSignedUrl(json.url);
        } else {
          throw new Error('Failed to get signed URL');
        }
      }
    };
    resolveSignedUrl();
  }, [directUrl.result]);

  return {signedUrl, loading: directUrl.loading};
};
