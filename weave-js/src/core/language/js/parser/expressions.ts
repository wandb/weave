// For testing

const expressions = [
  ``,
  // numbers
  `42`,
  `3.14`,

  // bools
  `true`,
  `false`,

  // string
  `'foo'`,
  `"bar"`,

  // null
  `null`,

  // lists
  `[]`,
  `[1,2,3]`,
  `[42, "foo", true]`,

  // dicts
  `{}`,
  `{ foo: "bar" }`,
  `{ "foo": "bar", "baz": 42, "qux": true }`,

  // nested
  `{ "foo": [1,2,3] }`,
  `[{ "foo": 42 }]`,

  // var
  `someVar`,

  // arrow function
  `(x) => x`,
  `(x,y) => x + y`,

  // unary
  `-42`,
  `!true`,

  // binary
  `1 + 2`,
  `1 == 2`,
  `1 != 2`,
  `'foo' + "bar"`,
  `true || false`,
  `true && false`,

  // function calls
  `Date("2022-01-01")`,
  `Link("https://wandb.ai/", "W&B")`,
  `project("foo","bar")`,

  // subscript
  `[1,2,3][0]`,
  `{"foo": 1, "bar": 2}["bar"]`,

  // member (chain)
  `foo.bar`,

  // ERROR (partially valid inputs?)
];

export default expressions;
