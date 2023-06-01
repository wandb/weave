// tslint:disable-next-line
/// <reference path="./ops/primitives/projection.d.ts" />

import './ops';

import * as fs from 'fs/promises';
import {mapValues, sortBy, uniqBy} from 'lodash';

import {Client as TestClient} from './_external/backendProviders/serverApiTest';
import {isEditingOp} from './hl';
import {defaultLanguageBinding} from './language/default';
import {createLocalClient} from './main';
import {outputTypeIsType, Type} from './model';
import {isList, isUnion, list, TYPES_WITH_PAGES, varNode} from './model';
import type {OpDef} from './opStore';
import {StaticOpStore} from './opStore';
import {autosuggest} from './suggest';
import {urlSafeTypeId} from './util/docs';

type OpDefDoc = {
  name: string;
  description: string;
  argDescriptions: {
    [name: string]: {
      type: string;
      description: string;
    };
  };
  returnValueDescription: {
    type?: string;
    description: string;
  };
};

const client = createLocalClient(new TestClient());

function flattenType(t: Type): Type[] {
  if (!isUnion(t)) {
    return [t];
  }

  return t.members.flatMap(flattenType);
}

async function typeToOpDefDocs(
  t: Type
): Promise<{singular: OpDefDoc[]; list: OpDefDoc[]}> {
  const singularExpression = varNode(
    t,
    typeof t === 'string' ? t : t.type.split('-')[0]
  );
  const singularSuggestions = await autosuggest(
    client,
    singularExpression,
    singularExpression,
    []
  );

  const singularOps: OpDefDoc[] = [];

  for (const suggestion of singularSuggestions) {
    if (
      isEditingOp(suggestion.newNodeOrOp) ||
      suggestion.newNodeOrOp.nodeType !== 'output'
    ) {
      throw new Error(
        `Processing type ${t}: Expected an OutputNode suggestion, but received Op ${suggestion.newNodeOrOp}`
      );
    }

    const opDef = StaticOpStore.getInstance().getOpDef(
      suggestion.newNodeOrOp.fromOp.name
    );
    const firstArgType = Object.values(opDef.inputTypes)[0];
    if (flattenType(firstArgType).includes('any')) {
      // to keep docs pages clean, we exclude ops that can apply to anything
      continue;
    }

    singularOps.push(opDefToOpDefDoc(opDef));
  }

  const listExpression = varNode(
    list(t),
    typeof t === 'string' ? t : t.type.split('-')[0] + 'List'
  );
  const listSuggestions = await autosuggest(
    client,
    listExpression,
    listExpression,
    []
  );

  const listOps: OpDefDoc[] = [];

  for (const suggestion of listSuggestions) {
    if (
      isEditingOp(suggestion.newNodeOrOp) ||
      suggestion.newNodeOrOp.nodeType !== 'output'
    ) {
      throw new Error(
        `Processing type ${t}: Expected an OutputNode suggestion, but received Op ${suggestion.newNodeOrOp}`
      );
    }

    const opDef = StaticOpStore.getInstance().getOpDef(
      suggestion.newNodeOrOp.fromOp.name
    );
    const firstArgType = Object.values(opDef.inputTypes)[0];

    if (
      !!flattenType(firstArgType).find(
        possibleType =>
          possibleType === 'any' ||
          (isList(possibleType) && possibleType.objectType === 'any')
      )
    ) {
      // as above for `singularOps`
      continue;
    }

    listOps.push(opDefToOpDefDoc(opDef));
  }

  return {
    singular: singularOps,
    list: listOps,
  };
}

function opDefToOpDefDoc({
  name,
  description,
  argDescriptions,
  returnValueDescription,
  inputTypes,
  outputType,
}: OpDef): OpDefDoc {
  const argDescriptionsWithTypes = mapValues(
    argDescriptions,
    (argDescription, argName) => {
      return {
        type: defaultLanguageBinding.printType(inputTypes[argName]),
        description: argDescription,
      };
    }
  );

  const resolvedOutputType: Type | undefined = outputTypeIsType(outputType)
    ? outputType
    : undefined;

  return {
    name,
    description,
    argDescriptions: argDescriptionsWithTypes,
    returnValueDescription: {
      type: resolvedOutputType
        ? defaultLanguageBinding.printType(resolvedOutputType)
        : undefined,
      description: returnValueDescription,
    },
  } as OpDefDoc;
}

function renderOpDefDoc(doc: OpDefDoc) {
  const markdown = `<h3 id="${doc.name}"><code>${doc.name}</code></h3>

${doc.description}

| Argument |  |
| :--- | :--- |
${Object.entries(doc.argDescriptions)
  .map(([argName, argDescription]) => {
    return `| \`${argName}\` | ${argDescription.description
      .replace(/\n/g, ' ')
      .replace(/\|/g, '\\|')} |`;
  })
  .join('\n')}

#### Return Value
${
  doc.returnValueDescription.type ? `(${doc.returnValueDescription.type}) ` : ''
}${doc.returnValueDescription.description}`;

  return markdown;
}

async function writeTypeDocs() {
  const typeDocLinks: {[typeId: string]: string} = {};
  const typeDocDir = `${__dirname}/../../docs_gen`;

  await fs.mkdir(typeDocDir, {
    recursive: true,
  });
  const getId = (t: Type) => (typeof t === 'string' ? t : t.type);

  const uniqueSortedTypes = sortBy(uniqBy(TYPES_WITH_PAGES, getId), getId);

  await Promise.all(
    uniqueSortedTypes.map(async t => {
      const {singular, list: mapped} = await typeToOpDefDocs(t);

      const typeId = typeof t === 'string' ? t : t.type;
      const descriptionPath = `${__dirname}/../../docs/types/${typeId}.md`;
      let description: string | undefined;

      try {
        description = (await fs.readFile(descriptionPath)).toString();
      } catch (e: any) {
        if (e?.code !== 'ENOENT') {
          throw e;
        }
      }

      let markdown = `# ${typeId}
`;

      if (description) {
        markdown += `
${description}
`;
      }

      if (singular.length > 0) {
        markdown += `
## Chainable Ops
${singular.map(renderOpDefDoc).join('\n\n')}

`;
      }

      if (mapped.length > 0) {
        markdown += `
## List Ops
${mapped.map(renderOpDefDoc).join('\n\n')}

`;
      }

      if (singular.length > 0 || mapped.length > 0) {
        const docPath = `${typeDocDir}/${urlSafeTypeId(typeId)}.md`;
        // console.log(`writing ${docPath}`);
        await fs.writeFile(docPath, markdown);

        typeDocLinks[typeId] = `$typeDocDir/${urlSafeTypeId(typeId)}.md`;
      } else {
        console.log(`Skipping ${typeId} (no type-specific ops found)`);
      }
    })
  );

  const typeLinksMarkdown = sortBy(
    Object.entries(typeDocLinks),
    ([typeId]) => typeId
  )
    .map(
      ([typeId, typeDocPath]) =>
        `* [${typeId}](${typeDocPath.replace('$typeDocDir', '.')})`
    )
    .join('\n');

  const baseReadmeMarkdown = await fs.readFile(
    `${__dirname}/../../docs/README.md`,
    'utf8'
  );

  await fs.writeFile(
    `${typeDocDir}/README.md`,
    baseReadmeMarkdown.replace('{data types}', typeLinksMarkdown)
  );
}

writeTypeDocs()
  .then(() => {
    console.log('successfully wrote type docs');
    process.exit(0);
  })
  .catch(e => {
    console.error(`Error while writing type docs: ${e}`);
    process.exit(1);
  });
