import {union} from './helpers';
import {intersectionOf} from './intersection';

describe('intersectionOf', () => {
  it('number|string ⋂ string|bool == string', () => {
    expect(
      intersectionOf(union(['number', 'string']), union(['string', 'boolean']))
    ).toEqual('string');
  });

  it('number|string|boolean ⋂ string|bool|date == string|boolean', () => {
    expect(
      intersectionOf(
        union(['number', 'string', 'boolean']),
        union(['string', 'boolean', 'date'])
      )
    ).toEqual(union(['string', 'boolean']));
  });

  it('number|string ⋂ bool|date == invalid', () => {
    expect(
      intersectionOf(union(['number', 'string']), union(['boolean', 'date']))
    ).toEqual('invalid');
  });
});
