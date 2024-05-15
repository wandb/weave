export type WFHighLevelCallFilter = {
  traceRootsOnly?: boolean;
  opVersionRefs?: string[];
  inputObjectVersionRefs?: string[];
  outputObjectVersionRefs?: string[];
  parentId?: string | null;
  // This really doesn't belong here. We are using it to indicate that the
  // filter is frozen and should not be updated by the user. However, this
  // control should really be managed outside of the filter itself.
  frozen?: boolean;
};

/**
 * Given a frozen filter and an active filter, return the effective filter. The
 * effective filter is the combination of the two filters, with the frozen
 * filter taking precedence over the active filter. The effective filter is
 * guaranteed to be a valid filter with `traceRootsOnly` set correctly.
 */
export const getEffectiveFilter = (
  activeFilter: WFHighLevelCallFilter,
  frozenFilter?: WFHighLevelCallFilter
) => {
  const effectiveFilter = {
    ...activeFilter,
    ...(frozenFilter ?? {}),
  };

  // TraceRootsOnly is now only a calculated field
  effectiveFilter.traceRootsOnly =
    filterShouldUseTraceRootsOnly(effectiveFilter);

  validateFilterUICompatibility(effectiveFilter);
  return effectiveFilter;
};
/**
 * Given a filter, validate that it is a valid filter. If the filter is invalid,
 * an error will be thrown. Technically the backend can handle any combination
 * of filters, but the UI components are not setup to handle such cases. In the future
 * we should update the UI components to handle more complex filters and remove this.
 */
const validateFilterUICompatibility = (filter: WFHighLevelCallFilter) => {
  if ((filter.opVersionRefs?.length ?? 0) > 1) {
    throw new Error('Multiple op versions not yet supported');
  }

  if ((filter.inputObjectVersionRefs?.length ?? 0) > 1) {
    throw new Error('Multiple input object versions not yet supported');
  }

  if ((filter.outputObjectVersionRefs?.length ?? 0) > 1) {
    throw new Error('Multiple output object versions not yet supported');
  }
};
/**
 * Given a filter, return whether the filter should use trace roots only. A
 * filter should use trace roots only if the filter does not specify any
 * other fields.
 */
export const filterShouldUseTraceRootsOnly = (
  filter: WFHighLevelCallFilter
) => {
  const opVersionRefsSet = (filter.opVersionRefs?.length ?? 0) > 0;
  const inputObjectVersionRefsSet =
    (filter.inputObjectVersionRefs?.length ?? 0) > 0;
  const outputObjectVersionRefsSet =
    (filter.outputObjectVersionRefs?.length ?? 0) > 0;
  const parentIdSet = filter.parentId != null;
  return (
    !opVersionRefsSet &&
    !inputObjectVersionRefsSet &&
    !outputObjectVersionRefsSet &&
    !parentIdSet
  );
};
