import * as markdown from '@wandb/weave/common/util/markdown';
import {opDisplayName} from '@wandb/weave/core';
import React from 'react';

import {Button} from '../../components/Button';
import {useWeaveContext} from '../../context';
import * as S from './OpDoc.styles';

export interface OpDocProps {
  opName: string;
  className?: string;

  // For __getattr__ ops only
  attributeName?: string;

  onClose?: () => void;
}

const OpDoc: React.FC<OpDocProps> = ({
  opName,
  className,
  attributeName,
  onClose,
}) => {
  const {client} = useWeaveContext();
  const opDef = client.opStore.getOpDef(opName);

  // Special case for __getattr__
  const isGetAttr = opName.endsWith('__getattr__');

  // NOTE: this assumes we'll only be documenting binary, function, and chain ops
  // it'll need some tweaking if we decide to document "pick", for instance.
  const displayName = isGetAttr
    ? attributeName
    : opDisplayName({name: opName}, client.opStore);

  const description = markdown.sanitizeHTML(
    markdown.generateHTML(
      isGetAttr
        ? `Retrieve this object's **${attributeName}** attribute.`
        : opDef.description
    )
  );
  const argDescriptions = isGetAttr
    ? []
    : Object.entries(opDef.argDescriptions).map(([argName, argDescription]) => [
        argName,
        markdown.sanitizeHTML(markdown.generateHTML(argDescription)),
      ]);
  if (opDef.renderInfo.type === 'chain') {
    // the first argument to a chain operator is implicit -- it's the thing before the
    // dot -- it would be confusing to show it in the docs as an argument
    argDescriptions.shift();
  }

  const returnValueDescription = markdown.sanitizeHTML(
    markdown.generateHTML(
      isGetAttr
        ? `This object's **${attributeName}** attribute`
        : opDef.returnValueDescription
    )
  );
  return (
    <div
      data-test={`op-doc-${opDef.name}`}
      className={className}
      onMouseDown={ev => {
        // Prevent this element from taking focus
        // otherwise it disappears before the onClick
        // can register!
        ev.preventDefault();
      }}>
      <S.OpNameRow>
        <S.OpName>
          <S.Code>{displayName}</S.Code>
        </S.OpName>
        {onClose && (
          <S.OpClose data-mode="dark">
            <Button
              variant="ghost"
              size="small"
              icon="close"
              onClick={onClose}
            />
          </S.OpClose>
        )}
      </S.OpNameRow>
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
