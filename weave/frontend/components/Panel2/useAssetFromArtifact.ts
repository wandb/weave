import {useMemo, useRef} from 'react';
import * as CGReact from '@wandb/common/cgreact';
import * as Op from '@wandb/cg/browser/ops';
import * as CG from '@wandb/cg/browser/graph';
import * as Types from '@wandb/cg/browser/model/types';
import {MemoizedHasher} from '@wandb/cg/browser/hash';

export const useAssetURLFromArtifact = <
  InputNodeInternalType extends Exclude<Types.MediaType, Types.TableType>
>(
  inputNode: Types.Node<InputNodeInternalType>,
  ignoreExpiration?: boolean
) => {
  const nodeValueQuery = CGReact.useNodeValue(inputNode);
  const fileNode = useMemo(() => {
    if (!nodeValueQuery.loading) {
      return Op.opArtifactVersionFile({
        artifactVersion: Op.opAssetArtifactVersion({asset: inputNode}),
        path: Op.constString(nodeValueQuery.result.path),
      });
    } else {
      return CG.voidNode();
    }
  }, [inputNode, nodeValueQuery]);

  const fileURLNode = useDirectUrlNodeWithExpiration(
    fileNode as any,
    ignoreExpiration ? 24 * 60 * 60 * 1000 : 60 * 1000
  );
  const directUrlQuery = CGReact.useNodeValue(fileURLNode);

  return {
    loading: nodeValueQuery.loading || directUrlQuery.loading,
    asset: nodeValueQuery.result,
    directUrl: directUrlQuery.result,
  };
};

export const useAssetContentFromArtifact = <
  InputNodeInternalType extends Exclude<Types.MediaType, Types.TableType>
>(
  inputNode: Types.Node<InputNodeInternalType>
) => {
  const nodeValueQuery = CGReact.useNodeValue(inputNode);
  const artifactNode = useMemo(
    () => Op.opAssetArtifactVersion({asset: inputNode}),
    [inputNode]
  );
  const contentNode = useMemo(() => {
    if (!nodeValueQuery.loading) {
      return Op.opFileContents({
        file: Op.opArtifactVersionFile({
          artifactVersion: artifactNode,
          path: Op.constString(nodeValueQuery.result.path),
        }) as any,
      });
    } else {
      return CG.voidNode();
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
export const useDirectUrlNodeWithExpiration = (
  fileNode:
    | Types.Node<{
        type: 'file';
        extension: string;
      }>
    | Types.VoidNode,
  ttl: number
) => {
  const fileNodeRef = useRef<
    Types.Node<{
      type: 'file';
      extension: string;
    }>
  >();
  const resultRef = useRef<Types.OutputNode<Types.Type> | Types.VoidNode>();
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
        resultRef.current = Op.opFileDirectUrlAsOf({
          file: fileNode,
          asOf: Op.constNumber(currentTime),
        });
      } else {
        resultRef.current = CG.voidNode();
      }
    }
    return resultRef.current;
  }, [fileNode, ttl, fileNodeRef, resultRef, asOfRef]);
};
