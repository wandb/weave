// Handle serialization/deserialization of CG, for remote execution
import type {EditingNode} from './editing';

type SerializedRef = number;

interface BatchedGraphs {
  nodes: any[];
  targetNodes: SerializedRef[];
}

type Serializer = {
  nextID: SerializedRef;
  refByHash: Map<string, SerializedRef>;
  values: any[];
};

function createSerializer(): Serializer {
  return {
    nextID: 0,
    refByHash: new Map(),
    values: [],
  };
}

function hash(v: any): string {
  // When hashing an object, we must keep the keys in a consistent order.
  // Otherwise, identical objects may be hashed into different key orders.
  const isObject = v != null && typeof v === `object` && !Array.isArray(v);
  if (isObject) {
    // This does not properly stringify nested objects, but that's ok because
    // the object values should already be replaced with serialized refs.
    return JSON.stringify(v, Object.keys(v).sort());
  }

  return JSON.stringify(v);
}

// Array of CG -> Normalized Graph -> Serializable Graph + Roots -> Flat Serializable Graph
export function serialize2(graphs: EditingNode[]): BatchedGraphs {
  const serializer = createSerializer();

  const targetNodes = graphs.map(graph => serializeValue(serializer, graph));

  return {
    nodes: serializer.values,
    targetNodes,
  };
}

function serializeValue(serializer: Serializer, v: any): SerializedRef {
  if (v == null || typeof v !== 'object') {
    return valueToRef(serializer, v);
  }
  if (Array.isArray(v)) {
    return serializeArray(serializer, v);
  }
  return serializeObject(serializer, v);
}

function valueToRef(serializer: Serializer, v: any): SerializedRef {
  const h = hash(v);

  const existingRef = serializer.refByHash.get(h);
  if (existingRef != null) {
    return existingRef;
  }

  const ref = serializer.nextID++;
  serializer.refByHash.set(h, ref);
  serializer.values.push(v);
  return ref;
}

function serializeArray(serializer: Serializer, arr: any[]): SerializedRef {
  const withSerializedValues = arr.map(v => serializeValue(serializer, v));
  return valueToRef(serializer, withSerializedValues);
}

function serializeObject(
  serializer: Serializer,
  obj: {[key: string]: any}
): SerializedRef {
  const withSerializedValues = Object.fromEntries(
    Object.entries(obj).map(([k, v]) => [k, serializeValue(serializer, v)])
  );
  return valueToRef(serializer, withSerializedValues);
}

export function deserialize2({
  nodes,
  targetNodes,
}: BatchedGraphs): EditingNode[] {
  return targetNodes.map(targetNode => deserializeValue(nodes, targetNode));
}

function deserializeValue(nodes: any[], nodeIndex: number): any {
  const v = nodes[nodeIndex];
  if (v == null || typeof v !== 'object') {
    return v;
  }
  if (Array.isArray(v)) {
    return deserializeArray(nodes, v);
  }
  return deserializeObject(nodes, v);
}

function deserializeArray(nodes: any[], nodeIndices: number[]): any {
  return nodeIndices.map(nodeIndex => deserializeValue(nodes, nodeIndex));
}

function deserializeObject(
  nodes: any[],
  nodeIndices: {[key: string]: number}
): any {
  return Object.fromEntries(
    Object.entries(nodeIndices).map(([k, nodeIndex]) => [
      k,
      deserializeValue(nodes, nodeIndex),
    ])
  );
}
