import {
  getAbsolutePrefixedUrl,
  getIsExternalLink,
  getIsMailToLink,
  getSafeUrlWithoutXss,
} from './links';

describe('getIsExternalLink', () => {
  it('returns true for http', () => {
    expect(
      getIsExternalLink('https://docs.wandb.ai/guides/runs/alert')
    ).toBeTruthy();
  });
  it('returns false', () => {
    expect(getIsExternalLink('mailto:hellpiamlink')).not.toBeTruthy();
  });
});

describe('getIsMailToLink', () => {
  it('returns true for http', () => {
    expect(getIsMailToLink('mailto:hellpiamlink')).toBeTruthy();
  });
  it('returns false', () => {
    expect(
      getIsMailToLink('https://docs.wandb.ai/guides/runs/alert')
    ).not.toBeTruthy();
  });
});

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

describe('getSafeUrlWithoutXss', () => {
  it('returns correct link for mailto:', () => {
    expect(getSafeUrlWithoutXss('mailto:support@wandb.com')).toEqual(
      'mailto:support@wandb.com'
    );
  });
});
