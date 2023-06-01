import {typeToString} from '../language/js/print';
import {isAssignableTo} from '../model/helpers';
import {intersectionOf} from '../model/intersection';
import {LOG_DEBUG_MESSAGES} from '../util/constants';
import {OpDef, OpStore} from './types';
import {getOpDefsByDisplayName, opDisplayName} from './util';

function noIntersectingInputTypes(
  opStore: OpStore,
  newOpDef?: OpDef
): string[] {
  // Only need to check when new ops are added
  if (newOpDef == null) {
    return [];
  }

  // Verify disjoint first arg input types for ops that share a display name
  const displayName = opDisplayName(newOpDef, opStore);
  const opDefs = getOpDefsByDisplayName(displayName, opStore).filter(
    od => od.name !== newOpDef.name
  );

  if (opDefs.length === 0) {
    return [];
  }

  const result = [];

  for (const od of opDefs) {
    // Skip intersection check if render types are not the same, since they
    // are disjoint in the syntactical space
    if (od.renderInfo.type !== newOpDef.renderInfo.type) {
      continue;
    }

    const failReasons: string[] = [];
    const ourArgTypes = Object.entries(newOpDef.inputTypes);
    const theirArgTypes = Object.entries(od.inputTypes);

    for (
      let argNum = 0;
      argNum < Math.max(ourArgTypes.length, theirArgTypes.length);
      argNum++
    ) {
      const [ourKey, ourArgType] = ourArgTypes[argNum] ?? [];
      const [theirKey, theirArgType] = theirArgTypes[argNum] ?? [];

      if (ourKey == null || theirKey == null) {
        continue;
      }

      const intersection = intersectionOf(ourArgType, theirArgType);

      const usToThem = isAssignableTo(ourArgType, theirArgType);
      const themToUs = isAssignableTo(theirArgType, ourArgType);

      if (usToThem && themToUs) {
        failReasons.push(
          `${od.name}.${theirKey}:${typeToString(theirArgType)} AND ${
            newOpDef.name
          }.${ourKey}:${typeToString(ourArgType)} ARE EQUAL`
        );
      } else if (themToUs) {
        failReasons.push(
          `${od.name}.${theirKey}:${typeToString(
            theirArgType
          )} IS ASSIGNABLE TO ${newOpDef.name}.${ourKey}:${typeToString(
            ourArgType
          )}`
        );
      } else if (usToThem) {
        failReasons.push(
          `${newOpDef.name}.${ourKey}:${typeToString(
            ourArgType
          )} IS ASSIGNABLE TO ${od.name}.${theirKey}:${typeToString(
            theirArgType
          )}`
        );
      } else if (intersection !== 'invalid' && intersection !== 'none') {
        failReasons.push(`
          ${od.name}.${theirKey}:${typeToString(theirArgType)} AND ${
          newOpDef.name
        }.${ourKey}:${typeToString(ourArgType)} INTERSECT: ${typeToString(
          intersection,
          false
        )}`);
      }
    }

    if (failReasons.length > 0) {
      result.push(
        `${newOpDef.name} and ${od.name} share display name (${displayName}) but input signatures intersect!\n` +
          failReasons.map(m => `  ${m}`).join('\n')
      );
    }
  }
  return result;
}

export function validateOpStore(opStore: OpStore, newOpDef?: OpDef) {
  if (!LOG_DEBUG_MESSAGES) {
    return;
  }

  const VALIDATORS = [noIntersectingInputTypes];

  for (const validator of VALIDATORS) {
    const failures = validator(opStore, newOpDef);
    failures.forEach(failure => console.warn(failure));
  }
}
