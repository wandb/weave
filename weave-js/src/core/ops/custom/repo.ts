import {unwrapTaggedValues} from '../../model';
import {MAX_DATE_MS} from '../../util/constants';
import * as OpKinds from '../opKinds';

// this function should be refactored to be more generic and use pure weave instead of
// moving most of the work to the resolver / ts. an attempt to do this yielded
// slower performance than this function so we are leaving this as is for now.
export const opMaybeNormalizeUserCounts = OpKinds.makeBasicOp({
  hidden: true,
  name: `normalizeUserCounts`,
  argTypes: {
    arr: 'any',
    normalize: 'boolean',
  },
  description:
    "Normalizes a list of user counts if the 'normalize' argument is true",
  argDescriptions: {
    arr: `The list of user counts to normalize.`,
    normalize: `Whether to normalize the list.`,
  },
  returnValueDescription: `The potentially normalized list of user counts.`,
  returnType: ({arr, normalize}) => arr,
  resolver: async ({arr, normalize}) => {
    if (arr.length === 0) {
      return arr;
    }

    if (!normalize) {
      return arr;
    }

    const arr2: Array<{created_week: Date; user_count: number}> = [];
    let minDate = new Date(MAX_DATE_MS);
    for (const item of arr) {
      if (item.created_week == null || item.user_count == null) {
        return arr;
      }
      const {created_week} = item;
      if (created_week < minDate) {
        minDate = created_week;
      }

      arr2.push(item);
    }

    const filteredToMinDate = arr2.filter(
      x => x.created_week.getTime() === minDate.getTime()
    );

    const normFactor = filteredToMinDate.reduce(
      (a, b) => a + unwrapTaggedValues(b.user_count),
      0
    );

    return arr2.map(row => ({
      ...row,
      user_count: unwrapTaggedValues(row.user_count) / normFactor,
    }));
  },
});
