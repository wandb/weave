import {typeToString} from '../language/js/print';
import {isUnion, union} from './helpers';
import {Type} from './types';

export function intersectionOf(t1: Type, t2: Type): Type {
  const t1Members = membersOf(t1);
  const t2Members = membersOf(t2);
  const result: Type[] = [];
  for (const t1m of t1Members) {
    if (
      t2Members.some(
        t2m => typeToString(t2m, false) === typeToString(t1m, false)
      )
    ) {
      result.push(t1m);
    }
  }

  if (result.length === 0) {
    return 'invalid';
  } else if (result.length === 1) {
    return result[0];
  }

  return union(result);
}

function membersOf(t: Type): Type[] {
  if (!isUnion(t)) {
    return [t];
  }

  return t.members.flatMap(membersOf);
}
