// Handle serialization/deserialization of CG, for remote execution

// Compared to serialize.ts, which only converts nodes to references,
// this version replaces every single value with a reference.
// Values which are identical (including arrays and objects)
// are always deduplicated when serialized.

// Unserialized:
// {
//   num: 1,
//   str: "asdf",
//   arr: [1, "asdf"],
//   obj: {
//     a: 1,
//     b: "asdf"
//   }
// }

// Serialized:
// {
//   nodes: [
//     1,
//     "asdf",
//     [0, 1],
//     {a: 0, b: 1},
//     {
//       num: 0,
//       str: 1,
//       arr: 2,
//       obj: 3
//     }
//   ],
//   targetNodes: [4]
// }

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
  // When hashing an object/map/set, we must keep the keys in a consistent order.
  // Otherwise, identical objects/maps/sets may be hashed into different key orders.
  // While maps and sets retain insertion order and are therefore unique based on their
  // key orders, we do not care about that. We only care about which key/values are present.
  const isSet = v instanceof Set;
  if (isSet) {
    const sortedValues = [...v].sort();
    return `__WEAVE_SERIALIZER_SET(${JSON.stringify(sortedValues)})`;
  }
  const isMap = v instanceof Map;
  if (isMap) {
    const sortedEntries = [...v.entries()].sort();
    return `__WEAVE_SERIALIZER_MAP(${JSON.stringify(sortedEntries)})`;
  }
  const isObject = v != null && typeof v === `object` && !Array.isArray(v);
  if (isObject) {
    // This does not properly stringify nested objects, but that's ok because
    // the object values should already be replaced with serialized refs.
    return JSON.stringify(v, Object.keys(v).sort());
  }

  return JSON.stringify(v);
}

// Array of CG -> Normalized Graph -> Serializable Graph + Roots -> Flat Serializable Graph
export function serializeAllValues(graphs: EditingNode[]): BatchedGraphs {
  const serializer = createSerializer();

  const targetNodes = graphs.map(graph => serializeValue(serializer, graph));

  return {
    nodes: serializer.values,
    targetNodes,
  };
}

// TODO: Handle `Map`s and `Set`s.
// Note that `JSON.stringify`ing any map/set does not work and will always result in `'{}'`.
// If we actually want to suport maps/sets, we'll need to serialize them into a custom format.
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

export function deserializeAllValues({
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
