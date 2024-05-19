import {formatNumber} from './number';

const NUM_ZERO = 0;
const NUM_NAN = Number.NaN;
const NUM_INF_POS = Number.POSITIVE_INFINITY;
const NUM_INF_NEG = Number.NEGATIVE_INFINITY;
const NUM_INT_MAX = Number.MAX_SAFE_INTEGER;
const NUM_INT_MIN = Number.MIN_SAFE_INTEGER;
const NUM_MAX = Number.MAX_VALUE;

const NUM_INT_POS = 1234;
const NUM_INT_NEG = -1234;
const NUM_INT_BIG = 100000000000000;
const NUM_FLOAT_POS = 1234.56789;
const NUM_FLOAT_NEG = -1234.56789;
const NUM_FLOAT_SMALL = 1.234e-6;
const NUM_FLOAT_BIG = 1.234e90;
const NUM_FRAC_FIFTH = 1 / 5;
const NUM_FRAC_THIRD = 1 / 3;

describe('formatNumber', () => {
  it('formats Automatic to match previous behavior', () => {
    const format = 'Automatic';
    // Chosen to match integration tests.
    expect(formatNumber(NUM_ZERO, format)).toEqual('0');
    expect(formatNumber(NUM_NAN, format)).toEqual('NaN');
    expect(formatNumber(NUM_INF_POS, format)).toEqual('Infinity');
    expect(formatNumber(NUM_INF_NEG, format)).toEqual('-Infinity');
    expect(formatNumber(NUM_INT_POS, format)).toEqual('1234');
    expect(formatNumber(NUM_INT_NEG, format)).toEqual('-1234');
    expect(formatNumber(NUM_FLOAT_POS, format)).toEqual('1234.568');
    expect(formatNumber(NUM_FLOAT_NEG, format)).toEqual('-1234.568');
    expect(formatNumber(NUM_FLOAT_BIG, format)).toEqual('1.234e+90');
    expect(formatNumber(NUM_FLOAT_SMALL, format)).toEqual('0.000001234');
    expect(formatNumber(NUM_FRAC_FIFTH, format)).toEqual('0.2');
    expect(formatNumber(NUM_FRAC_THIRD, format)).toEqual('0.3333');
    expect(formatNumber(Math.pow(2, 2.5), format)).toEqual('5.657');
  });
  it('matches Number.toString or unrecognized format specified', () => {
    const format = 'Anything else';
    expect(formatNumber(NUM_ZERO, format)).toEqual('0');
    expect(formatNumber(NUM_NAN, format)).toEqual('NaN');
    expect(formatNumber(NUM_INF_POS, format)).toEqual('Infinity');
    expect(formatNumber(NUM_INF_NEG, format)).toEqual('-Infinity');
    expect(formatNumber(NUM_INT_MAX, format)).toEqual('9007199254740991');
    expect(formatNumber(NUM_INT_MIN, format)).toEqual('-9007199254740991');
    expect(formatNumber(NUM_MAX, format)).toEqual('1.7976931348623157e+308');
    expect(formatNumber(NUM_INT_POS, format)).toEqual('1234');
    expect(formatNumber(NUM_INT_NEG, format)).toEqual('-1234');
    expect(formatNumber(NUM_INT_BIG, format)).toEqual('100000000000000');
    expect(formatNumber(NUM_FLOAT_POS, format)).toEqual('1234.56789');
    expect(formatNumber(NUM_FLOAT_NEG, format)).toEqual('-1234.56789');
    expect(formatNumber(NUM_FLOAT_BIG, format)).toEqual('1.234e+90');
    expect(formatNumber(NUM_FRAC_FIFTH, format)).toEqual('0.2');
    expect(formatNumber(NUM_FRAC_THIRD, format)).toEqual('0.3333333333333333');
  });

  it('formats Number', () => {
    const format = 'Number';
    expect(formatNumber(NUM_ZERO, format)).toEqual('0.00');
    expect(formatNumber(NUM_NAN, format)).toEqual('NaN');
    expect(formatNumber(NUM_INF_POS, format)).toEqual('∞');
    expect(formatNumber(NUM_INF_NEG, format)).toEqual('-∞');
    expect(formatNumber(NUM_INT_MAX, format)).toEqual(
      '9,007,199,254,740,991.00'
    );
    expect(formatNumber(NUM_INT_MIN, format)).toEqual(
      '-9,007,199,254,740,991.00'
    );
    expect(formatNumber(NUM_MAX, format)).toEqual(
      '179,769,313,486,231,570,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000.00'
    );
    expect(formatNumber(NUM_INT_POS, format)).toEqual('1,234.00');
    expect(formatNumber(NUM_INT_NEG, format)).toEqual('-1,234.00');
    expect(formatNumber(NUM_INT_BIG, format)).toEqual('100,000,000,000,000.00');
    expect(formatNumber(NUM_FLOAT_POS, format)).toEqual('1,234.57');
    expect(formatNumber(NUM_FLOAT_NEG, format)).toEqual('-1,234.57');
    expect(formatNumber(NUM_FLOAT_BIG, format)).toEqual(
      '1,234,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000.00'
    );
    expect(formatNumber(NUM_FRAC_FIFTH, format)).toEqual('0.20');
    expect(formatNumber(NUM_FRAC_THIRD, format)).toEqual('0.33');
  });

  it('formats Percent', () => {
    const format = 'Percent';
    expect(formatNumber(NUM_ZERO, format)).toEqual('0.00%');
    expect(formatNumber(NUM_NAN, format)).toEqual('NaN%');
    expect(formatNumber(NUM_INF_POS, format)).toEqual('∞%');
    expect(formatNumber(NUM_INF_NEG, format)).toEqual('-∞%');
    expect(formatNumber(NUM_INT_MAX, format)).toEqual('900719925474099100.00%');
    expect(formatNumber(NUM_INT_MIN, format)).toEqual(
      '-900719925474099100.00%'
    );
    expect(formatNumber(NUM_MAX, format)).toEqual(
      '17976931348623157000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000.00%'
    );

    expect(formatNumber(NUM_INT_POS, format)).toEqual('123400.00%');
    expect(formatNumber(NUM_INT_NEG, format)).toEqual('-123400.00%');
    expect(formatNumber(NUM_INT_BIG, format)).toEqual('10000000000000000.00%');
    expect(formatNumber(NUM_FLOAT_POS, format)).toEqual('123456.79%');
    expect(formatNumber(NUM_FLOAT_NEG, format)).toEqual('-123456.79%');
    expect(formatNumber(NUM_FLOAT_BIG, format)).toEqual(
      '123400000000000000000000000000000000000000000000000000000000000000000000000000000000000000000.00%'
    );
    expect(formatNumber(NUM_FRAC_FIFTH, format)).toEqual('20.00%');
    expect(formatNumber(NUM_FRAC_THIRD, format)).toEqual('33.33%');
  });

  it('formats Scientific', () => {
    const format = 'Scientific';
    expect(formatNumber(NUM_ZERO, format)).toEqual('0.000000e+00');
    expect(formatNumber(NUM_NAN, format)).toEqual('NaN');
    expect(formatNumber(NUM_INF_POS, format)).toEqual('∞');
    expect(formatNumber(NUM_INF_NEG, format)).toEqual('-∞');
    expect(formatNumber(NUM_INT_POS, format)).toEqual('1.234000e+03');
    expect(formatNumber(NUM_INT_NEG, format)).toEqual('-1.234000e+03');
    expect(formatNumber(NUM_INT_BIG, format)).toEqual('1.000000e+14');
    expect(formatNumber(NUM_FLOAT_POS, format)).toEqual('1.234568e+03');
    expect(formatNumber(NUM_FLOAT_NEG, format)).toEqual('-1.234568e+03');
    expect(formatNumber(NUM_FLOAT_BIG, format)).toEqual('1.234000e+90');
    expect(formatNumber(NUM_FRAC_FIFTH, format)).toEqual('2.000000e-01');
    expect(formatNumber(NUM_FRAC_THIRD, format)).toEqual('3.333333e-01');
  });

  it('formats Compact', () => {
    const format = 'Compact';
    expect(formatNumber(NUM_ZERO, format)).toEqual('0');
    expect(formatNumber(NUM_NAN, format)).toEqual('NaN');
    expect(formatNumber(NUM_INF_POS, format)).toEqual('∞');
    expect(formatNumber(NUM_INF_NEG, format)).toEqual('-∞');
    expect(formatNumber(NUM_INT_MAX, format)).toEqual('9.01e+15');
    expect(formatNumber(NUM_INT_MIN, format)).toEqual('-9.01e+15');
    expect(formatNumber(NUM_MAX, format)).toEqual('1.80e+308');
    expect(formatNumber(NUM_INT_POS, format)).toEqual('1.2K');
    expect(formatNumber(NUM_INT_NEG, format)).toEqual('-1.2K');
    expect(formatNumber(NUM_INT_BIG, format)).toEqual('100T');
    expect(formatNumber(NUM_FLOAT_POS, format)).toEqual('1.2K');
    expect(formatNumber(NUM_FLOAT_NEG, format)).toEqual('-1.2K');
    expect(formatNumber(NUM_FLOAT_BIG, format)).toEqual('1.23e+90');
    expect(formatNumber(NUM_FRAC_FIFTH, format)).toEqual('0.2');
    expect(formatNumber(NUM_FRAC_THIRD, format)).toEqual('0.33');
    expect(formatNumber(999_999_999_999_999, format)).toEqual('1000T');
    expect(formatNumber(1_000_000_000_000_000, format)).toEqual('1.00e+15');
  });

  it('formats Currency - USD', () => {
    const format = '$USD';
    expect(formatNumber(NUM_ZERO, format)).toEqual('$0.00');
    expect(formatNumber(NUM_NAN, format)).toEqual('$NaN');
    expect(formatNumber(NUM_INF_POS, format)).toEqual('$∞');
    expect(formatNumber(NUM_INF_NEG, format)).toEqual('-$∞');
    expect(formatNumber(NUM_INT_MAX, format)).toEqual(
      '$9,007,199,254,740,991.00'
    );
    expect(formatNumber(NUM_INT_MIN, format)).toEqual(
      '-$9,007,199,254,740,991.00'
    );
    expect(formatNumber(NUM_INT_POS, format)).toEqual('$1,234.00');
    expect(formatNumber(NUM_INT_NEG, format)).toEqual('-$1,234.00');
    expect(formatNumber(NUM_INT_BIG, format)).toEqual(
      '$100,000,000,000,000.00'
    );
    expect(formatNumber(NUM_FLOAT_POS, format)).toEqual('$1,234.57');
    expect(formatNumber(NUM_FLOAT_NEG, format)).toEqual('-$1,234.57');
    expect(formatNumber(NUM_FRAC_FIFTH, format)).toEqual('$0.20');
    expect(formatNumber(NUM_FRAC_THIRD, format)).toEqual('$0.33');
  });

  it('formats Custom', () => {
    // sign
    expect(formatNumber(NUM_ZERO, '*+')).toEqual('+0');
    expect(formatNumber(NUM_INT_POS, '*+')).toEqual('+1234');
    expect(formatNumber(NUM_INT_POS, '* ')).toEqual(' 1234');
    expect(formatNumber(NUM_INT_NEG, '* ')).toEqual('-1234');

    // zero
    expect(formatNumber(NUM_ZERO, '*04')).toEqual('0000');
    expect(formatNumber(NUM_INT_POS, '*08')).toEqual('00001234');
    expect(formatNumber(NUM_INT_POS, '*+08')).toEqual('+0001234');
    expect(formatNumber(NUM_INT_POS, '* 08')).toEqual(' 0001234');
    expect(formatNumber(NUM_INT_NEG, '*08')).toEqual('-0001234');
    expect(formatNumber(NUM_INT_NEG, '*+08')).toEqual('-0001234');

    // width
    expect(formatNumber(NUM_ZERO, '*3')).toEqual('  0');
    expect(formatNumber(NUM_INT_POS, '*3')).toEqual('1234');

    // grouping
    expect(formatNumber(NUM_ZERO, '*,')).toEqual('0');
    expect(formatNumber(NUM_INT_POS, '*,')).toEqual('1,234');
    expect(formatNumber(NUM_INT_NEG, '*,')).toEqual('-1,234');
    expect(formatNumber(NUM_FLOAT_POS, '*,')).toEqual('1,234.567890');
    expect(formatNumber(NUM_FLOAT_NEG, '*,')).toEqual('-1,234.567890');

    // precision
    expect(formatNumber(NUM_FLOAT_POS, '*.1')).toEqual('1234.6');
    expect(formatNumber(NUM_FLOAT_POS, '*.2')).toEqual('1234.57');
    expect(formatNumber(NUM_FLOAT_POS, '*.3')).toEqual('1234.568');
    expect(formatNumber(NUM_FLOAT_POS, '*.12')).toEqual('1234.567890000000');

    // type
    expect(formatNumber(NUM_INT_POS, '*')).toEqual('1234');
    expect(formatNumber(NUM_FLOAT_POS, '*')).toEqual('1234.567890');
    expect(formatNumber(NUM_INT_POS, '*f')).toEqual('1234.000000');
    expect(formatNumber(NUM_FLOAT_POS, '*f')).toEqual('1234.567890');
    expect(formatNumber(NUM_INT_POS, '*d')).toEqual('1234');
    expect(formatNumber(NUM_FLOAT_POS, '*d')).toEqual('1235'); // Python would error, unknown format code for float
    expect(formatNumber(NUM_INT_POS, '*e')).toEqual('1.234000e+03');
    expect(formatNumber(NUM_FLOAT_SMALL, '*e')).toEqual('1.234000e-06');
    expect(formatNumber(NUM_INT_POS, '*E')).toEqual('1.234000E+03');
    expect(formatNumber(NUM_FLOAT_SMALL, '*E')).toEqual('1.234000E-06');

    // combination
    expect(formatNumber(NUM_INT_POS, '*+010,.1f')).toEqual('+001,234.0');
  });
});
