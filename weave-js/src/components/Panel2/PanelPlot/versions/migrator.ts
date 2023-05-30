export type HasVersion = {
  configVersion: number;
};

/* Function to generate an config migrator.

   Example usage:

  // assume we have the following config versions
  type CV1 = {a: number; configVersion: 1};
  type CV2 = {a: number; b: string; configVersion: 2};
  type CV3 = {a: {aa: number}; b: string; c: boolean; configVersion: 3};

  We could define a series of migrations to migrate a value from CV1 to CV4
  as follows:

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

  Then we could make a migrator via:
  const migrator = makeMigrator(M_1_2).add(M_2_3);

  Then we could perform the migration via:
  const startingConfig = {a: 1, configVersion: 1 as const};
  const result = migrator.migrate(startingConfig);

  And we would see:

  result === {a: {aa: 10}, b: "1", c: false, configVersion: 4}
 */
export const makeMigrator = <
  FC extends HasVersion,
  TC extends HasVersion,
  PC extends HasVersion = FC
>(
  migration: (config: FC) => TC,
  version: number = 1,
  migratePrevious?: (config: PC) => FC
) => {
  const migrate = (userConfig: PC | FC | TC): TC => {
    let v = 'configVersion' in userConfig ? userConfig.configVersion : 1;

    if (v < version) {
      if (migratePrevious == null) {
        throw new Error(
          `Need to provide a migration function for version ${v}`
        );
      }
      userConfig = {
        ...migratePrevious(userConfig as PC),
        configVersion: version,
      };
      v = version;
    }

    if (v === version) {
      return {...migration(userConfig as FC), configVersion: version + 1};
    } else if (v === version + 1) {
      return userConfig as TC;
    } else {
      // The provided config has a version greater than I know what to do with.
      throw new Error(
        `Unknown config version: ${v}, known up to ${version + 1}`
      );
    }
  };

  const add = <CN extends HasVersion>(nextMigration: (config: TC) => CN) => {
    return makeMigrator(nextMigration, version + 1, migrate);
  };

  return {
    migrate,
    add,
  };
};
