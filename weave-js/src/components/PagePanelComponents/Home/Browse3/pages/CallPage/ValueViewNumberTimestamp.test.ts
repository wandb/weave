import {likelyTimestampName} from './ValueViewNumberTimestamp';

describe('likelyTimestampName', () => {
  it('returns false for undefined', () => {
    expect(likelyTimestampName('')).toEqual(false);
  });

  it('returns false for empty string', () => {
    expect(likelyTimestampName('')).toEqual(false);
  });

  it('matches basic timestamp fields', () => {
    expect(likelyTimestampName('created')).toEqual(true);
    expect(likelyTimestampName('started')).toEqual(true);
    expect(likelyTimestampName('ended')).toEqual(true);
    expect(likelyTimestampName('updated')).toEqual(true);
    expect(likelyTimestampName('finished')).toEqual(true);
    expect(likelyTimestampName('duration')).toEqual(true);
    expect(likelyTimestampName('time')).toEqual(true);
    expect(likelyTimestampName('timestamp')).toEqual(true);
  });

  it('matches _at suffixed fields', () => {
    expect(likelyTimestampName('created_at')).toEqual(true);
    expect(likelyTimestampName('started_at')).toEqual(true);
    expect(likelyTimestampName('updated_at')).toEqual(true);
  });

  it('matches _ms suffixed fields', () => {
    expect(likelyTimestampName('duration_ms')).toEqual(true);
    expect(likelyTimestampName('time_ms')).toEqual(true);
  });

  it('matches prefixed timestamp fields', () => {
    expect(likelyTimestampName('user_created')).toEqual(true);
    expect(likelyTimestampName('task_started_at')).toEqual(true);
    expect(likelyTimestampName('request_finished')).toEqual(true);
  });

  it('is case insensitive', () => {
    expect(likelyTimestampName('CREATED')).toEqual(true);
    expect(likelyTimestampName('Started_At')).toEqual(true);
    expect(likelyTimestampName('TIME_MS')).toEqual(true);
  });

  it('rejects non-timestamp fields', () => {
    expect(likelyTimestampName('count')).toEqual(false);
    expect(likelyTimestampName('name')).toEqual(false);
    expect(likelyTimestampName('id')).toEqual(false);
    expect(likelyTimestampName('status')).toEqual(false);
  });

  it('rejects false positives with timestamp substrings', () => {
    expect(likelyTimestampName('timestamps_count')).toEqual(false);
    expect(likelyTimestampName('created_by_user')).toEqual(false);
    expect(likelyTimestampName('time_zone')).toEqual(false);
    expect(likelyTimestampName('updating_status')).toEqual(false);
  });
});
