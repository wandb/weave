import fs from 'fs';
import os from 'os';
import path from 'path';
import {Netrc} from '../../utils/netrc';

jest.mock('fs');
jest.mock('os');

describe('Netrc', () => {
  const mockHomedir = '/mock/home';
  const mockNetrcPath = path.join(mockHomedir, '.netrc');

  beforeEach(() => {
    jest.resetAllMocks();
    (os.homedir as jest.Mock).mockReturnValue(mockHomedir);
  });

  test('load parses netrc file correctly', () => {
    const mockContent = `
      machine example.com
        login user1
        password pass1
      machine api.example.com
        login user2
        password pass2
    `;
    (fs.readFileSync as jest.Mock).mockReturnValue(mockContent);

    const netrc = new Netrc();

    expect(netrc.entries.size).toBe(2);
    expect(netrc.getEntry('example.com')).toEqual({
      machine: 'example.com',
      login: 'user1',
      password: 'pass1',
    });
    expect(netrc.getEntry('api.example.com')).toEqual({
      machine: 'api.example.com',
      login: 'user2',
      password: 'pass2',
    });
  });

  test('load handles non-existent file', () => {
    (fs.readFileSync as jest.Mock).mockImplementation(() => {
      throw new Error('File not found');
    });

    const netrc = new Netrc();
    expect(netrc.entries.size).toBe(0);
  });

  test('save writes entries correctly', () => {
    const netrc = new Netrc();
    netrc.setEntry({machine: 'example.com', login: 'user1', password: 'pass1'});
    netrc.setEntry({
      machine: 'api.example.com',
      login: 'user2',
      password: 'pass2',
    });

    netrc.save();

    const expectedContent = `machine example.com
  login user1
  password pass1

machine api.example.com
  login user2
  password pass2
`;

    expect(fs.writeFileSync).toHaveBeenCalledWith(
      mockNetrcPath,
      expectedContent,
      {mode: 0o600}
    );
  });

  test('getLastEntry returns the last entry', () => {
    const netrc = new Netrc();
    netrc.setEntry({
      machine: 'example1.com',
      login: 'user1',
      password: 'pass1',
    });
    netrc.setEntry({
      machine: 'example2.com',
      login: 'user2',
      password: 'pass2',
    });

    expect(netrc.getLastEntry()).toEqual({
      machine: 'example2.com',
      login: 'user2',
      password: 'pass2',
    });
  });

  test('getLastEntry returns undefined for empty entries', () => {
    const netrc = new Netrc();
    expect(netrc.getLastEntry()).toBeUndefined();
  });
});
