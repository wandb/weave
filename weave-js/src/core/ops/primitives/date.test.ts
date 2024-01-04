import moment from 'moment';

import {constNone, constTimestamp} from '../../model';
import {testClient} from '../../testUtil';
import {opTimestampMax, opTimestampRelativeStringAutoFormat} from './date';
import {opArray} from './literals';

describe('date ops', () => {
  describe('relativeStringAutoFormat', () => {
    it('handles single unit pos', async () => {
      const client = await testClient();
      const now = moment();
      const timestamp1 = moment(now);
      const timestamp2 = moment(now).add(moment.duration(1, 'days'));
      const expr = opTimestampRelativeStringAutoFormat({
        lhs: constTimestamp(timestamp2.valueOf()),
        rhs: constTimestamp(timestamp1.valueOf()),
      });
      expect(await client.query(expr)).toEqual('1 day');
    });

    it('handles single unit neg', async () => {
      const client = await testClient();
      const now = moment();
      const timestamp1 = moment(now);
      const timestamp2 = moment(now).add(moment.duration(1, 'days'));
      const expr = opTimestampRelativeStringAutoFormat({
        lhs: constTimestamp(timestamp1.valueOf()),
        rhs: constTimestamp(timestamp2.valueOf()),
      });
      expect(await client.query(expr)).toEqual('-1 day');
    });

    it('handles year unit pos', async () => {
      const client = await testClient();
      const now = moment();
      const timestamp1 = moment(now);
      const timestamp2 = moment(now).add(moment.duration(400, 'days'));
      const expr = opTimestampRelativeStringAutoFormat({
        lhs: constTimestamp(timestamp2.valueOf()),
        rhs: constTimestamp(timestamp1.valueOf()),
      });
      expect(await client.query(expr)).toEqual('1.1 years');
    });

    it('handles year unit neg', async () => {
      const client = await testClient();
      const now = moment();
      const timestamp1 = moment(now);
      const timestamp2 = moment(now).add(moment.duration(400, 'days'));
      const expr = opTimestampRelativeStringAutoFormat({
        lhs: constTimestamp(timestamp1.valueOf()),
        rhs: constTimestamp(timestamp2.valueOf()),
      });
      expect(await client.query(expr)).toEqual('-1.1 years');
    });

    it('handles month unit expect tenth rounding', async () => {
      const client = await testClient();
      const now = moment();
      const timestamp1 = moment(now);
      const timestamp2 = moment(now).add(moment.duration(305, 'days'));
      const expr = opTimestampRelativeStringAutoFormat({
        lhs: constTimestamp(timestamp2.valueOf()),
        rhs: constTimestamp(timestamp1.valueOf()),
      });
      expect(await client.query(expr)).toEqual('10.2 months');
    });

    it('handles no diff', async () => {
      const client = await testClient();
      const now = moment();
      const timestamp1 = moment(now);
      const timestamp2 = moment(now);
      const expr = opTimestampRelativeStringAutoFormat({
        lhs: constTimestamp(timestamp2.valueOf()),
        rhs: constTimestamp(timestamp1.valueOf()),
      });
      expect(await client.query(expr)).toEqual('less than 1 ms');
    });

    it('minutes check pos and round', async () => {
      const client = await testClient();
      const now = moment();
      const timestamp1 = moment(now);
      const timestamp2 = moment(now).add(moment.duration(20.5, 'minutes'));
      const expr = opTimestampRelativeStringAutoFormat({
        lhs: constTimestamp(timestamp2.valueOf()),
        rhs: constTimestamp(timestamp1.valueOf()),
      });
      expect(await client.query(expr)).toEqual('21 minutes');
    });

    it('hours check neg and round', async () => {
      const client = await testClient();
      const now = moment();
      const timestamp1 = moment(now);
      const timestamp2 = moment(now).add(moment.duration(20.5, 'hours'));
      const expr = opTimestampRelativeStringAutoFormat({
        lhs: constTimestamp(timestamp1.valueOf()),
        rhs: constTimestamp(timestamp2.valueOf()),
      });
      expect(await client.query(expr)).toEqual('-21 hours');
    });
  });
});

describe('date ops', () => {
  describe('timestamp-max', () => {
    it('handles getting max timestamp and None', async () => {
      const client = await testClient();
      const timestamp1 = moment().valueOf();
      const timestamp2 = moment().add(moment.duration(1, 'days')).valueOf();
      const expr = opTimestampMax({
        timestamps: opArray({
          0: constTimestamp(timestamp1),
          1: constTimestamp(timestamp2),
          3: constNone(),
        } as any),
      });
      expect(await client.query(expr)).toEqual(timestamp2);
    });
  });
});
