/**
 * Utility for parsing Weave and Registry ref URIs.
 *
 * Supports parsing different types of refs with either weave:/// or registry:/// prefix:
 * - Table refs: weave:///entity/project/table/digest
 * - Object refs: weave:///entity/project/object/name:digest
 * - Op refs: weave:///entity/project/op/name:digest
 * - Call refs: weave:///entity/project/call/id
 * - Registry refs: registry:///entity/project/object/name:digest
 */

export type ParsedWeaveUri =
  | {
      type: 'table';
      entity: string;
      project: string;
      digest: string;
    }
  | {
      type: 'object';
      entity: string;
      project: string;
      name: string;
      digest: string;
    }
  | {
      type: 'op';
      entity: string;
      project: string;
      name: string;
      digest: string;
    }
  | {
      type: 'call';
      entity: string;
      project: string;
      id: string;
    };

/**
 * Parse a Weave or Registry URI into its components.
 *
 * Accepts both `weave:///` and `registry:///` prefixes.
 *
 * @param uri - A weave:/// or registry:/// URI string to parse
 * @returns Parsed URI components or null if invalid
 *
 * @example
 * ```typescript
 * const parsed = parseWeaveUri('weave:///wandb/project/object/my-prompt:abc123');
 * const parsed2 = parseWeaveUri('registry:///wandb/project/object/my-prompt:v0');
 * ```
 */
export function parseWeaveUri(uri: string): ParsedWeaveUri | null {
  const match = uri.match(/^(?:weave|registry):\/\/\/([^/]+)\/([^/]+)\/([^/]+)\/(.+)$/);

  if (!match) {
    return null;
  }

  const [, entity, project, type, rest] = match;

  if (type === 'table') {
    // weave:///entity/project/table/digest
    return {
      type: 'table',
      entity,
      project,
      digest: rest,
    };
  } else if (type === 'object' || type === 'op') {
    // weave:///entity/project/object/name:digest
    // weave:///entity/project/op/name:digest
    const [nameVersion] = rest.split('/');
    const [name, digest = 'latest'] = nameVersion.split(':');

    return {
      type: type as 'object' | 'op',
      entity,
      project,
      name,
      digest,
    };
  } else if (type === 'call') {
    // weave:///entity/project/call/id
    const [id] = rest.split('/');
    return {
      type: 'call',
      entity,
      project,
      id,
    };
  }

  return null;
}

/**
 * Parse a table ref URI specifically.
 * Throws an error if the URI is not a valid table ref.
 *
 * @param uri - The weave:/// URI string to parse
 * @returns Parsed table ref components
 * @throws Error if URI is not a valid table ref
 */
export function parseTableRefUri(uri: string): {
  entity: string;
  project: string;
  projectId: string;
  digest: string;
} {
  const parsed = parseWeaveUri(uri);

  if (!parsed || parsed.type !== 'table') {
    throw new Error(`Invalid table ref URI: ${uri}`);
  }

  return {
    entity: parsed.entity,
    project: parsed.project,
    projectId: `${parsed.entity}/${parsed.project}`,
    digest: parsed.digest,
  };
}
