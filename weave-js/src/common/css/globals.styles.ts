/*
 * This file converts all of the global styles in globals.less to constants that can be
 * used in styled components.
 */

import {css} from 'styled-components';

/************
  NEWEST GLOBAL UNITS - START USING THESE!!
************/

/* Hardcoded values */
export const SEARCH_NAV_HEIGHT = '60px';

/* Colors */

export const WHITE = '#ffffff';
export const BLACK = '#000000';
export const MOONBEAM = '#eaeaff';
export const OBLIVION = '#0e1014';
export const TRANSPARENT = 'rgba(255, 255, 255, 0)';

export const GRAY_25 = '#fafafa';
export const GRAY_50 = '#f6f6f6';
export const GRAY_100 = '#f4f4f4'; // DEPRECATED - use GRAY_50
export const GRAY_200 = '#eeeeee';
export const GRAY_300 = '#e6e6e6';
export const GRAY_350 = '#dddddd';
export const GRAY_400 = '#cccdcf';
export const GRAY_450 = '#c0c1c2'; // DEPRECATED - use GRAY_400
export const GRAY_500 = '#949699';
export const GRAY_600 = '#76787a';
export const GRAY_700 = '#4b4e52';
export const GRAY_800 = '#33373d';
export const GRAY_840 = '#24262b';
export const GRAY_860 = '#222429';
export const GRAY_880 = '#1d1f24';
export const GRAY_900 = '#181b1f';
export const GRAYS = {
  GRAY_25,
  GRAY_50,
  GRAY_100,
  GRAY_200,
  GRAY_300,
  GRAY_350,
  GRAY_400,
  GRAY_450,
  GRAY_500,
  GRAY_600,
  GRAY_700,
  GRAY_800,
  GRAY_840,
  GRAY_860,
  GRAY_880,
  GRAY_900,
} as const;
export const GRAY_PAGE_BG = GRAY_25;

export const TEAL_TRANSPARENT = 'rgba(0, 150, 173, 0.10)'; // Deprecated, use hexToRGB
export const TEAL_LIGHT2 = '#00becc';
export const TEAL_LIGHT = '#00afc2';
export const TEAL = '#0096ad';
export const TEAL_DARK = '#038899';
export const TEALS = {
  TEAL_TRANSPARENT,
  TEAL_LIGHT2,
  TEAL_LIGHT,
  TEAL,
  TEAL_DARK,
} as const;

export const GREEN_TRANSPARENT = 'rgba(0, 163, 104, 0.15)'; // Deprecated, use hexToRGB
export const GREEN_LIGHT2 = '#5ed686';
export const GREEN_LIGHT = '#0fb863';
export const GREEN = '#00a368';
export const GREEN_DARK = '#008f5d';
export const GREENS = {
  GREEN_TRANSPARENT,
  GREEN_LIGHT2,
  GREEN_LIGHT,
  GREEN,
  GREEN_DARK,
} as const;

export const GOLD_DARK_TRANSPARENT = 'rgba(245, 155, 20, 0.14)'; // Deprecated, use hexToRGB
export const GOLD_LIGHT2 = '#ffd95c';
export const GOLD_LIGHT = '#ffc933';
export const GOLD = '#fcb119';
export const GOLD_DARK = '#f59b14';
export const GOLD_DARK2 = '#c77905';
export const GOLD_DARK3 = '#c17401';
export const GOLDS = {
  GOLD_DARK_TRANSPARENT,
  GOLD_LIGHT2,
  GOLD_LIGHT,
  GOLD,
  GOLD_DARK,
  GOLD_DARK2,
  GOLD_DARK3,
} as const;

export const SIENNA_TRANSPARENT = 'rgba(229, 122, 83, 0.16)'; // Deprecated, use hexToRGB
export const SIENNA_LIGHT2 = '#ffc5a3';
export const SIENNA_LIGHT = '#faa77d';
export const SIENNA = '#e57a53';
export const SIENNA_DARK = '#bf6448';
export const SIENNAS = {
  SIENNA_TRANSPARENT,
  SIENNA_LIGHT2,
  SIENNA_LIGHT,
  SIENNA,
  SIENNA_DARK,
} as const;

export const RED_LIGHT_TRANSPARENT = 'rgba(252, 86, 97, 0.16)'; // Deprecated, use hexToRGB
export const RED_LIGHT2 = '#ff8585';
export const RED_LIGHT = '#ff6670';
export const RED = '#ff3859';
export const RED_DARK = '#eb1c45';

export const REDS = {
  RED_LIGHT_TRANSPARENT,
  RED_LIGHT2,
  RED_LIGHT,
  RED,
  RED_DARK,
} as const;

export const CACTUS_LIGHT2 = '#BFE573';
export const CACTUS_LIGHT = '#A3CC52';
export const CACTUS = '#84B043';
export const CACTUS_DARK = '#669432';
export const CACTUSES = {
  CACTUS_LIGHT2,
  CACTUS_LIGHT,
  CACTUS,
  CACTUS_DARK,
} as const;

export const MAGENTA_LIGHT2 = '#E07AFF';
export const MAGENTA_LIGHT = '#CD5BF0';
export const MAGENTA = '#B948E0';
export const MAGENTA_DARK = '#9E36C2';
export const MAGENTAS = {
  MAGENTA_LIGHT2,
  MAGENTA_LIGHT,
  MAGENTA,
  MAGENTA_DARK,
} as const;

export const PURPLE_LIGHT2 = '#BCA5FA';
export const PURPLE_LIGHT = '#A690F0';
export const PURPLE = '#9278EB';
export const PURPLE_DARK = '#775CD1';
export const PURPLES = {
  PURPLE_LIGHT2,
  PURPLE_LIGHT,
  PURPLE,
  PURPLE_DARK,
} as const;

export const BLUE_LIGHT2 = '#7CB1F7';
export const BLUE_LIGHT = '#559AFA';
export const BLUE = '#3E84ED';
export const BLUE_DARK = '#2D69E0';
export const BLUES = {
  BLUE_LIGHT2,
  BLUE_LIGHT,
  BLUE,
  BLUE_DARK,
} as const;

export const Colors = {
  WHITE,
  BLACK,
  MOONBEAM,
  OBLIVION,
  TRANSPARENT,
  ...GRAYS,
  ...TEALS,
  ...GREENS,
  ...GOLDS,
  ...SIENNAS,
  ...REDS,
  ...CACTUSES,
  ...MAGENTAS,
  ...PURPLES,
  ...BLUES,
} as const;
export type ColorName = keyof typeof Colors;
export type ColorValue = (typeof Colors)[ColorName];

export const hexToRGB = (hex: string, alpha?: number) => {
  if (!hex.startsWith('#')) {
    throw new Error(`Color hex code ${hex} missing '#' prefix`);
  }
  if (hex.length === 7) {
    const r = parseInt(hex.substring(1, 3), 16);
    const g = parseInt(hex.substring(3, 5), 16);
    const b = parseInt(hex.substring(5, 7), 16);
    if (isNaN(r) || isNaN(g) || isNaN(b)) {
      throw new Error(`Invalid hex code: ${hex}`);
    }
    return alpha !== undefined
      ? `rgba(${r}, ${g}, ${b}, ${alpha})`
      : `rgb(${r}, ${g}, ${b})`;
  }
  if (hex.length === 4) {
    const rc = parseInt(hex.charAt(1), 16);
    const gc = parseInt(hex.charAt(2), 16);
    const bc = parseInt(hex.charAt(3), 16);
    if (isNaN(rc) || isNaN(gc) || isNaN(bc)) {
      throw new Error(`Invalid hex code: ${hex}`);
    }
    const r = rc * 16 + rc;
    const g = gc * 16 + gc;
    const b = bc * 16 + bc;
    return alpha !== undefined
      ? `rgba(${r}, ${g}, ${b}, ${alpha})`
      : `rgb(${r}, ${g}, ${b})`;
  }
  throw new Error(`Invalid hex code: ${hex}`);
};

/**
 * The following names/colors do not align with the design system
 * and should be considered deprecated and phased out in favor of
 * an option above.
 */
export const GRAY_TRANSPARENT = 'rgba(24, 27, 31, 5%)';
export const BLACK_TRANSPARENT = 'rgba(0, 0, 0, 12%)';
export const BLACK_TRANSPARENT_2 = 'rgba(0, 0, 0, 40%)';
export const TEAL_LIGHT_TRANSPARENT = 'rgba(0, 175, 194, 20%)';
export const TEAL_TRANSPARENT_2 = 'rgba(3, 149, 168, 10%)';
export const TEAL_LIGHT_2 = TEAL_LIGHT2;
export const GREEN_LIGHT_2 = GREEN_LIGHT2;
export const SIENNA_LIGHT_TRANSPARENT_30 = 'rgba(250, 167, 125, 30%)';
export const SIENNA_LIGHT_2 = SIENNA_LIGHT2;
export const GOLD_DARK_2 = GOLD_DARK2;
export const RED_TRANSPARENT = RED_LIGHT_TRANSPARENT;
export const RED_LIGHT_2 = RED_LIGHT2;

/* Spacing */
export const SPU = '0.5rem'; // standard spacing unit = 8px

/* Responsive styling standards */
export const TABLET_BREAKPOINT = '768px'; // 48rem
export const TABLET_BREAKPOINT_WIDTH = 768;

export const TABLET_WIDTH = 1320;
export const SMALL_TABLET_WIDTH = 1000;
export const MOBILE_WIDTH = 600;

/* Borders */
export const BORDER_RADIUS_STANDARD = '4px';
export const BORDER_COLOR_FOCUSED = hexToRGB(TEAL_LIGHT2, 0.6);

/* Typography */
export const FONT_WEIGHT_STANDARD = 100;
export const TEXT_PRIMARY_COLOR = GRAY_800;

/* Shadows */
export const MENU_SHADOW_LIGHT_MODE = `0px 16px 32px 0px rgba(14,16,20,0.16)`;
export const MENU_SHADOW_NIGHT_MODE = `0px 16px 32px 0px rgba(14,16,20,0.6)`;
export const MODAL_SHADOW_LIGHT_MODE = `0px 24px 48px 0px ${hexToRGB(
  OBLIVION,
  0.24
)}`;
export const MODAL_SHADOW_NIGHT_MODE = `0px 24px 48px 0px ${hexToRGB(
  OBLIVION,
  0.48
)}`;
export const PANEL_HOVERED_SHADOW = `0px 4px 8px 0px ${hexToRGB(
  OBLIVION,
  0.04
)}`;

/* Scrollbars */
export const SCROLLBAR_STYLES = css<{scrollbarVisible?: boolean}>`
  // Firefox
  scrollbar-width: thin;
  scrollbar-color: ${p => hexToRGB(OBLIVION, p.scrollbarVisible ? 0.12 : 0)}
    transparent;

  // Webkit
  ::-webkit-scrollbar {
    width: 14px;
  }
  ::-webkit-scrollbar-thumb {
    border-radius: 9001px;
    border: 4px solid transparent;
    background-clip: padding-box;
    background-color: ${p => hexToRGB(OBLIVION, p.scrollbarVisible ? 0.12 : 0)};
    &:hover {
      background-color: ${p =>
        hexToRGB(OBLIVION, p.scrollbarVisible ? 0.24 : 0)};
    }
  }
`;

/* ------------------------------------------------------------------------------------------------ */

/************
  Grayscale
************/

export const gray50 = `#f9f9f9`;
export const gray100 = `#f4f4f4`;
export const gray200 = `#eeeeee`;
export const gray300 = `#e6e6e6`;
export const gray400 = `#d2d2d2`;
export const gray500 = `#aaaaaa`;
export const gray600 = `#757575`;
export const gray700 = `#515457`;
export const gray800 = `#363a3d`;
export const darkerGray = `#222222`;
export const gray900 = `#1a1c1f`;

export const textDisabled = gray400;
export const textSecondary = gray600;
export const textPrimary = gray800;

export const disabled = gray400;
export const border = gray400;
export const divider = gray200;
export const backdrop = `rgba(0, 0, 0, 0.9)`;
export const hover = `rgba(0, 0, 0, 0.04)`;
export const selected = `rgba(0, 0, 0, 0.08)`;
export const hoverDark = `rgba(255, 255, 255, 0.08)`;
export const gray100alpha38 = `rgba(244, 244, 244, 38%)`;
export const selectedHover = '#E5EBF1';

export const white = `#ffffff`;
export const black = `#000000`;

/***************
  Theme colors
***************/

export const error = `#de6680`;
export const errorBackground = `rgba(222, 102, 128, 0.08)`;
export const errorBorder = `rgba(222, 102, 128, 0.5)`;
export const errorDark = `#a93554`;
export const errorLight = `#ff97af`;
export const errorText = `#d53d5e`;

export const newError = `#f97575`;

export const primary = `#2e78c7`;
export const primaryBackground = `rgba(46, 120, 199, 0.08)`;
export const primaryBorder = `rgba(46, 120, 199, 0.5)`;
export const primaryDark = `#004d96`;
export const primaryLight = `#6ba6fa`;
export const primaryText = primary;

export const success = `#00B5A0`;
export const successBackground = `rgba(0, 181, 160, 0.08)`;
export const successBorder = `rgba(0, 181, 160, 0.5)`;
export const successDark = `#008472`;
export const successLight = `#5BE8D1`;
export const successText = `#008576`;

export const warning = `#F59174`;
export const warningBackground = `rgba(245, 145, 116, 0.08)`;
export const warningBorder = `rgba(245, 145, 116, 0.5)`;
export const warningDark = `#BF6248`;
export const warningLight = `#FFC2A3`;
export const warningText = `#DA3D10`;

export const info = `#03B7CE`;
export const infoBackground = `rgba(3, 182, 206, 0.08)`;
export const infoBorder = `rgba(3, 182, 206, 0.5)`;
export const infoDark = `#00879D`;
export const infoLight = `#61EAFF`;
export const infoText = `#028293`;

/*******************************
     User Global Variables
*******************************/

// TODO: This is out of date, update to match our semantic variables!
// Global colors
export const fontName = `Source Sans Pro`;
export const yellow = `#ffc933`;
export const gold = `#ffcc33`;
export const fullYellow = `#ffff00`;
export const red = error;
export const darkRed = `#ff2514`;
export const teal = info;
export const deepTeal = `#039cad`;
export const green = success;
export const blue = primary;
export const deepBlue = `#00648f`;

export const heartColor = `#bd70a3`;

// extended colors (These are only used in PanelMultiRunTable currently).
export const seaFoamGreen = `#7ed2bf`;
export const lightSeaFoamGreen = `#edf8f6`;
export const slateBlue = `#68abca`;
export const lightSlateBlue = `#e9f3f7`;
export const lightYellowOther = `#fff2cc`;
export const lightYellow = `#fffbec`;
export const goldenrod = `#daa300`;

// privacy badge colors
export const fern = `#3ac26c`; // public
export const aqua = `#21bfa4`; // team
export const cerulean = `#37a0c7`; // private
export const orchid = `#a97ccd`; // open

export const lightBlue = `#ddedfc`;
export const mediumBlue = `#80b3f8`;
export const darkBlue = `#338dd8`;
export const linkHoverBlue = `#006c95`;
export const sky = primaryBackground; // highlighted table cell
export const lightSky = `#f3fafd`; // highlighted table row/col

// (almost) AA compliant run text colors (used for legend and tooltip)
// yellow, cyan and seafoam are compromised because AA ver. is very different
export const runBlueText = `#3874D8`;
export const runRedText = `#D73E3E`;
export const runKellyGreenText = `#3D8452`;
export const runPurpleText = `#7D54B2`;
export const runPinkText = `#DB3169`;
export const runOrangeText = `#C5541A`;
export const runSeafoamText = `#55AA99`;
export const runMagentaText = `#B946BC`;
export const runYellowText = `#DD9200`;
export const runCyanText = `#1FA8D4`;
export const runForestText = `#1E8479`;
export const runPeachText = `#C1571C`;
export const runLimeText = `#62802C`;
export const runBrownText = `#A46750`;
export const runMaroonText = `#A12864`;
export const runGrayText = `#6E787E`;

// Shared CSS Rules
export const accordionContentPadding = `25px 20px`;
export const transitionTime = `0.3s`;
export const actionAnimationTime = `0.3s`;
export const backgroundColorTransition = `background-color ${transitionTime} linear`;
export const borderColorTransition = `border-color ${transitionTime} linear`;
export const pillBorderRadius = `20px`;
export const tabletBreakpoint = `768px`;

export const tagPurple = `#e5d6ff`;
export const tagBerry = `#ffd6f0`;
export const tagRed = `#ffe0e0`;
export const tagPeach = `#ffe7cc`;
export const tagYellow = `#fde8ad`;
export const tagAcid = `#c9f5b5`;
export const tagGreen = `#c2f2da`;
export const tagTeal = `#c0f0ed`;
export const tagBlue = `#d6efff`;
export const tagMidnight = `#e0e4ff`;
export const tagLightBlue = `#ccf1db`;
export const tagTealLightTransparent = `rgba(3, 149, 168, 0.14)`;
export const tagTealLight = `rgba(3, 149, 168, 0.2)`;
export const tagTealDark = `#038899`;
export const tagRedLightTransparent = `rgba(255, 102, 112, 0.16)`;
export const tagRedDark = `#eb1c45`;

export const galleryAdminPurple = `#bd9df4`;

export const commentYellow = `#FFE897`;

// Box shadows

// Box shadows at different levels from material
export const levelNavbarBoxShadow = `0 1px 3px rgba(0, 0, 0, 0.02),
0 1px 2px rgba(0, 0, 0, 0.12)`;
export const level1BoxShadow = `0 1px 3px rgba(0, 0, 0, 0.12),
0 1px 2px rgba(0, 0, 0, 0.24)`;
export const level2BoxShadow = `0 3px 6px rgba(0, 0, 0, 0.16),
0 3px 6px rgba(0, 0, 0, 0.23)`;
export const level3BoxShadow = `0 10px 20px rgba(0, 0, 0, 0.19),
0 6px 6px rgba(0, 0, 0, 0.23)`;
export const level3BoxShadowFaint = `0 10px 20px rgba(0, 0, 0, 0.07),
0 6px 6px rgba(0, 0, 0, 0.07)`;
export const level4BoxShadow = `0 14px 28px rgba(0, 0, 0, 0.25),
0 10px 10px rgba(0, 0, 0, 0.22)`;
export const level5BoxShadow = `0 19px 38px rgba(0, 0, 0, 0.30),
0 15px 12px rgba(0, 0, 0, 0.22)`;

export const boxShadowButtonsCharts = `0px 1px 3px 0px rgba(54,58,61,0.12)`;
export const boxShadowButtonsChartsHover = `0px 3px 6px 0px rgba(54,58,61,0.12)`;
export const boxShadowModal = `0px 8px 16px 0px rgba(54,58,61,0.16)`;
export const boxShadowDropdown = `0px 4px 8px 0px rgba(54,58,61,0.12)`;
export const boxShadowSection = `1px 1px 20px 0px #e6e6e6`;

// Inner tab box-shadow
export const tabBoxShadow = `inset 0 -4px 25px -8px rgba(0, 0, 0, 0.2)`;

// Font sizes
export const fontSizeStandard = `16px`;
export const lineHeightStandard = `24px`;
export const fontWeightStandard = `100`;

// Sizes
export const navbarHeight = `0px`;

// Spacing
export const pageHeaderButtonSpacing = `10px`;
export const standardSpacingUnit = `8px`;
export const spu = standardSpacingUnit;
export const largeStandardSpacingUnit = `10px`;
export const largeSpu = largeStandardSpacingUnit;

// Night Mode
// Need contrast and brightness adjustments, otherwise very dark gray merges with black.
export const nightModeFilter = `invert(100%) hue-rotate(180deg) contrast(80%) brightness(120%)`;
// Need to re-apply filter to images to revert them.
export const nightModeFilterRevert = `brightness(83.3333%) contrast(125%) hue-rotate(180deg) invert(100%)`;
export const nightModeTransition = `filter 2s`;

// Functional Color Rules
// These should wrap the above colors with semantic names
// TODO: Figure out how tofontSizeStandard organize this
// Action Colors, buttons,
export const actionButtonFocusedColor = deepTeal;
export const actionButtonFocusedFontColor = white;
export const actionButtonFocusedBorderColor = deepTeal;

export const actionButtonActiveColor = info;
export const actionButtonActiveFontColor = white;
export const actionButtonActiveBorderColor = info;

export const actionButtonDefaultColor = gray100;
export const actionButtonDefaultFontColor = textPrimary;
export const actionButtonDefaultBorderColor = `transparent`;

export const actionFocusedColor = primaryBackground;
export const actionFocusedFontColor = textPrimary;

export const actionActiveColor = primaryBackground;
export const actionActiveFontColor = textPrimary;

export const separatorBorder = `1px solid ${border}`;

export const searchNavHeight = SEARCH_NAV_HEIGHT;
export const galleryNavHeight = SEARCH_NAV_HEIGHT;
export const fancyPageSidebarWidth = `52px`;
export const mobileBarHeight = fancyPageSidebarWidth;
export const reportCoverHorizontalMargin = `28px`;
export const reportDraftBackgroundColor = `#fff8e3`;
export const reportFontSize = `18px`;
