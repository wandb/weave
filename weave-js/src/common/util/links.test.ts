import {getAbsolutePrefixedUrl} from './links';

describe('getAbsolutePrefixedUrl', () => {
  it('returns correct link for mailto:', () => {
    expect(getAbsolutePrefixedUrl('mailto:support@wandb.com')).toEqual(
      'mailto:support@wandb.com'
    );
  });
  it('returns correct link with ://', () => {
    expect(
      getAbsolutePrefixedUrl('https://docs.wandb.ai/guides/runs/alert')
    ).toEqual('https://docs.wandb.ai/guides/runs/alert');
  });
  it('returns absolute prefixed url', () => {
    const path = 'iamfakeentity/iamfakeproject?nw=nwuserjofang';
    window.location.href = 'http://localhost:9000/home';

    expect(getAbsolutePrefixedUrl(path)).toEqual(
      'http://localhost:9000/' + path
    );
  });
});
