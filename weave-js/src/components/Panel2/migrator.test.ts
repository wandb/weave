import {makeMigrator} from './PanelPlot/versions/migrator';

it('test config migration', () => {
  // config versions
  type CV1 = {a: number; configVersion: 1};
  type CV2 = {a: number; b: string; configVersion: 2};
  type CV3 = {a: {aa: number}; b: string; c: boolean; configVersion: 3};

  const M_1_2 = (config: CV1): CV2 => {
    return {...config, b: `${config.a}`, configVersion: 2};
  };

  const M_2_3 = (config: CV2): CV3 => {
    return {
      ...config,
      c: config.a % 2 === 0,
      a: {aa: config.a * 10},
      configVersion: 3,
    };
  };

  const startingUserConfig = {a: 1, configVersion: 1 as const};
  const m1 = makeMigrator(M_1_2);
  const m2 = m1.add(M_2_3);

  const result = m2.migrate(startingUserConfig);
  expect(m2.migrate(m1.migrate(startingUserConfig))).toEqual(result);
});
