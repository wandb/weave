import path from 'path';
import fs from 'fs';

/*
 * This function is used to require a package.json file from a given base directory.
 * It first checks if the base directory is an absolute path, and if so, it just reads the package.json file from that path.
 * If the base directory is not an absolute path, it looks for the package.json file in the module paths.
 * If the package.json file is not found, it throws an error.
 *
 * @param baseDir - The base directory to look for the package.json file.
 * @param modulePaths - The module paths to look for the package.json file.
 * @returns The package.json file as a JSON object.
 */
export function requirePackageJson(baseDir: string, modulePaths: string[]) {
  if (path.isAbsolute(baseDir)) {
    const candidate = path.join(baseDir, 'package.json');
    return JSON.parse(fs.readFileSync(candidate, 'utf8'));
  }
  for (const modulePath of modulePaths) {
    const candidate = path.join(modulePath, baseDir, 'package.json');
    try {
      return JSON.parse(fs.readFileSync(candidate, 'utf8'));
    } catch (e) {
      continue;
    }
  }
  throw new Error(`could not find ${baseDir}/package.json`);
}
