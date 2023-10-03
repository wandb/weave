/* --- Artifacts --- */

export function artifact(r: {
  entityName: string;
  projectName: string;
  artifactTypeName: string;
  artifactSequenceName: string;
  artifactCommitHash: string;
}) {
  return `/${r.entityName}/${r.projectName}/artifacts/${encodeURIComponent(
    r.artifactTypeName
  )}/${encodeURIComponent(r.artifactSequenceName)}/${r.artifactCommitHash}`;
}

export function artifactCollection(r: {
  entityName: string;
  projectName: string;
  artifactTypeName: string;
  artifactCollectionName: string;
}) {
  return `/${r.entityName}/${r.projectName}/artifacts/${encodeURIComponent(
    r.artifactTypeName
  )}/${encodeURIComponent(r.artifactCollectionName)}`;
}

/* --- Projects --- */

export function project(projectValue: Record<'entityName' | 'name', string>) {
  return `/${projectValue.entityName}/${projectValue.name}`;
}

/* --- Runs --- */

export function run(r: {
  entityName: string;
  projectName: string;
  name: string;
}) {
  return `/${r.entityName}/${r.projectName}/runs/${r.name}`;
}

/* --- Reports --- */

export type ReportParams = {
  entityName: string;
  projectName: string;
  reportID: string;
  reportName?: string;
};

export function reportEdit(r: ReportParams, queryString?: string) {
  const extra = queryString || '';
  return `${reportViewWithoutPublished(r)}/edit${extra}`;
}

export function reportView(r: ReportParams): string {
  return `/${r.entityName}/${r.projectName}/reports/${makeNameAndID(
    r.reportID,
    r.reportName
  )}`;
}

// Taken from url.ts
export function makeNameAndID(id: string, name?: string): string {
  // Note we strip base64 = padding to make this pretty. It's added back
  // in parseNameAndID above.
  id = id.replace(/=/g, '');
  if (name != null) {
    // Replace all non word characters with dashes, eliminate repeating dashes
    name = name.replace(/\W/g, '-').replace(/-+/g, '-');
  }
  return name != null ? `${encodeURIComponent(name)}--${id}` : id;
}

export function reportViewWithoutPublished(r: ReportParams) {
  return `/${r.entityName}/${r.projectName}/reports/${makeNameAndID(
    r.reportID,
    r.reportName
  )}`;
}
