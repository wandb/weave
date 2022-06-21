import * as markdown from '@wandb/common/util/markdown';
import React from 'react';
import * as Graph from '@wandb/cg/browser/graph';
import * as HL from '@wandb/cg/browser/hl';

import * as S from './OpDoc.styles';

export interface OpDocProps {
  opName: string;
  className?: string;
}

const OpDoc: React.FC<OpDocProps> = ({opName, className}) => {
  const opDef = Graph.getOpDef(opName);

  // NOTE: this assumes we'll only be documenting binary, function, and chain ops
  // it'll need some tweaking if we decide to document "pick", for instance.
  const displayName = HL.opDisplayName({name: opName});

  const description = markdown.sanitizeHTML(
    markdown.generateHTML(opDef.description)
  );
  const argDescriptions = Object.entries(opDef.argDescriptions).map(
    ([argName, argDescription]) => [
      argName,
      markdown.sanitizeHTML(markdown.generateHTML(argDescription)),
    ]
  );
  if (opDef.renderInfo.type === 'chain') {
    // the first argument to a chain operator is implicit -- it's the thing before the
    // dot -- it would be confusing to show it in the docs as an argument
    argDescriptions.shift();
  }

  const returnValueDescription = markdown.sanitizeHTML(
    markdown.generateHTML(opDef.returnValueDescription)
  );
  return (
    <div data-test={`op-doc-${opDef.name}`} className={className}>
      <S.OpName>
        <code>{displayName}</code>
      </S.OpName>
      <S.Section>
        <S.Markdown dangerouslySetInnerHTML={{__html: description}} />
      </S.Section>
      {argDescriptions.length > 0 && (
        <S.Section>
          <S.Subheader>Arguments:</S.Subheader>
          <S.ArgList>
            {argDescriptions.map(([argName, argDescription], index) => (
              <li key={argName}>
                <S.ArgName>{argName}</S.ArgName>
                <S.Markdown
                  dangerouslySetInnerHTML={{__html: argDescription}}
                />
              </li>
            ))}
          </S.ArgList>
        </S.Section>
      )}
      <S.Section>
        <S.Subheader>Returns:</S.Subheader>
        <S.Markdown
          dangerouslySetInnerHTML={{__html: returnValueDescription}}
        />
      </S.Section>
    </div>
  );
};
export default OpDoc;
