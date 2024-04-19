/*
 * This file converts all of the global styles in globals.less to constants that can be
 * used in styled components.
 */

import {css} from 'styled-components';

import {MOONBEAM, OBLIVION, WHITE} from './color.styles';
import {hexToRGB} from './utils';

/* Hardcoded values */
export const SEARCH_NAV_HEIGHT = '60px';

// TODO - need to talk to designers before making changes to black and transparent
export const BLACK = '#000000';
export const TRANSPARENT = 'rgba(255, 255, 255, 0)';

/* Colors */

/**
 * @deprecated
 */
export const GRAY_25 = '#fafafa';
/**
 * @deprecated
 */
export const GRAY_50 = '#f6f6f6';
/**
 * @deprecated
 */
export const GRAY_100 = '#f4f4f4'; // DEPRECATED - use GRAY_50
/**
 * @deprecated
 */
export const GRAY_200 = '#eeeeee';
/**
 * @deprecated
 */
export const GRAY_300 = '#e6e6e6';
/**
 * @deprecated
 */
export const GRAY_350 = '#dddddd';
/**
 * @deprecated
 */
export const GRAY_400 = '#cccdcf';
/**
 * @deprecated
 */
export const GRAY_450 = '#c0c1c2'; // DEPRECATED - use GRAY_400
/**
 * @deprecated
 */
export const GRAY_500 = '#949699';
/**
 * @deprecated
 */
export const GRAY_600 = '#76787a';
/**
 * @deprecated
 */
export const GRAY_700 = '#4b4e52';
/**
 * @deprecated
 */
export const GRAY_800 = '#33373d';
/**
 * @deprecated
 */
export const GRAY_840 = '#24262b';
/**
 * @deprecated
 */
export const GRAY_860 = '#222429';
/**
 * @deprecated
 */
export const GRAY_880 = '#1d1f24';
/**
 * @deprecated
 */
export const GRAY_900 = '#181b1f';
/**
 * @deprecated
 */
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
/**
 * @deprecated
 */
export const TEAL_TRANSPARENT = 'rgba(0, 150, 173, 0.10)'; // Deprecated, use hexToRGB
/**
 * @deprecated
 */
export const TEAL_LIGHT2 = '#00becc';
/**
 * @deprecated
 */
export const TEAL_LIGHT = '#00afc2';
/**
 * @deprecated
 */
export const TEAL = '#0096ad';
/**
 * @deprecated
 */
export const TEAL_DARK = '#038899';
/**
 * @deprecated
 */
export const TEALS = {
  TEAL_TRANSPARENT,
  TEAL_LIGHT2,
  TEAL_LIGHT,
  TEAL,
  TEAL_DARK,
} as const;
/**
 * @deprecated
 */
export const GREEN_LIGHT = '#0fb863';
/**
 * @deprecated
 */
export const GREEN = '#00a368';
/**
 * @deprecated
 */
export const GREENS = {
  GREEN_LIGHT,
  GREEN,
} as const;
/**
 * @deprecated
 */
export const GOLD_LIGHT = '#ffc933';
/**
 * @deprecated
 */
export const GOLD = '#fcb119';
/**
 * @deprecated
 */
export const GOLDS = {
  GOLD_LIGHT,
  GOLD,
} as const;
/**
 * @deprecated
 */
export const SIENNA_LIGHT2 = '#ffc5a3';
/**
 * @deprecated
 */
export const SIENNA_LIGHT = '#faa77d';
/**
 * @deprecated
 */
export const SIENNA = '#e57a53';
/**
 * @deprecated
 */
export const SIENNA_DARK = '#bf6448';
/**
 * @deprecated
 */
export const SIENNAS = {
  SIENNA_LIGHT2,
  SIENNA_LIGHT,
  SIENNA,
  SIENNA_DARK,
} as const;
/**
 * @deprecated
 */
export const RED_LIGHT = '#ff6670';
/**
 * @deprecated
 */
export const RED = '#ff3859';
/**
 * @deprecated
 */
export const RED_DARK = '#eb1c45';
/**
 * @deprecated
 */
export const REDS = {
  RED_LIGHT,
  RED,
  RED_DARK,
} as const;
/**
 * @deprecated
 */
export const MAGENTA_LIGHT = '#CD5BF0';
/**
 * @deprecated
 */
export const MAGENTA = '#B948E0';
/**
 * @deprecated
 */
export const MAGENTAS = {
  MAGENTA_LIGHT,
  MAGENTA,
} as const;
/**
 * @deprecated
 */
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
  ...MAGENTAS,
} as const;
/**
 * @deprecated
 */
export type ColorName = keyof typeof Colors;
/**
 * @deprecated
 */
export type ColorValue = (typeof Colors)[ColorName];

/**
 * The following names/colors do not align with the design system
 * and should be considered deprecated and phased out in favor of
 * an option above.
 */
/**
 * @deprecated
 */
export const GRAY_TRANSPARENT = 'rgba(24, 27, 31, 5%)';
/**
 * @deprecated
 */
export const BLACK_TRANSPARENT = 'rgba(0, 0, 0, 12%)';
/**
 * @deprecated
 */
export const BLACK_TRANSPARENT_2 = 'rgba(0, 0, 0, 40%)';
/**
 * @deprecated
 */
export const TEAL_LIGHT_TRANSPARENT = 'rgba(0, 175, 194, 20%)';
/**
 * @deprecated
 */
export const TEAL_TRANSPARENT_2 = 'rgba(3, 149, 168, 10%)';
/**
 * @deprecated
 */
export const TEAL_LIGHT_2 = TEAL_LIGHT2;
/**
 * @deprecated
 */
export const SIENNA_LIGHT_TRANSPARENT_30 = 'rgba(250, 167, 125, 30%)';
/**
 * @deprecated
 */
export const SIENNA_LIGHT_2 = SIENNA_LIGHT2;

/* Responsive styling standards */
/** @deprecated use MEDIUM_BREAKPOINT instead */
export const TABLET_BREAKPOINT = '768px'; // 48rem
/** @deprecated use MEDIUM_BREAKPOINT instead */
export const TABLET_BREAKPOINT_WIDTH = 768;

/** @deprecated */
export const TABLET_WIDTH = 1320;
/** @deprecated */
export const SMALL_TABLET_WIDTH = 1000;
/** @deprecated */
export const MOBILE_WIDTH = 600;

/* Borders */
export const BORDER_COLOR_FOCUSED = hexToRGB(TEAL_LIGHT2, 0.6);

/* Typography */
export const FONT_WEIGHT_STANDARD = 100;
export const TEXT_PRIMARY_COLOR = GRAY_800;

/* Shadows */
/**
 * @deprecated
 */
export const MENU_SHADOW_LIGHT_MODE = `0px 16px 32px 0px rgba(14,16,20,0.16)`;
/**
 * @deprecated
 */
export const MENU_SHADOW_NIGHT_MODE = `0px 16px 32px 0px rgba(14,16,20,0.6)`;
/**
 * @deprecated
 */
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
/**
 * @deprecated
 */
export const gray50 = `#f9f9f9`;
/**
 * @deprecated
 */
export const gray100 = `#f4f4f4`;
/**
 * @deprecated
 */
export const gray200 = `#eeeeee`;
/**
 * @deprecated
 */
export const gray300 = `#e6e6e6`;
/**
 * @deprecated
 */
export const gray400 = `#d2d2d2`;
/**
 * @deprecated
 */
export const gray500 = `#aaaaaa`;
/**
 * @deprecated
 */
export const gray600 = `#757575`;
/**
 * @deprecated
 */
export const gray700 = `#515457`;
/**
 * @deprecated
 */
export const gray800 = `#363a3d`;
/**
 * @deprecated
 */
export const darkerGray = `#222222`;
/**
 * @deprecated
 */
export const gray900 = `#1a1c1f`;
/**
 * @deprecated
 */
export const textDisabled = gray400;
/**
 * @deprecated
 */
export const textSecondary = gray600;
/**
 * @deprecated
 */
export const textPrimary = gray800;
/**
 * @deprecated
 */
export const disabled = gray400;
/**
 * @deprecated
 */
export const border = gray400;
/**
 * @deprecated
 */
export const divider = gray200;
/**
 * @deprecated
 */
export const backdrop = `rgba(0, 0, 0, 0.9)`;
/**
 * @deprecated
 */
export const hover = `rgba(0, 0, 0, 0.04)`;
/**
 * @deprecated
 */
export const selected = `rgba(0, 0, 0, 0.08)`;
/**
 * @deprecated
 */
export const hoverDark = `rgba(255, 255, 255, 0.08)`;
/**
 * @deprecated
 */
export const gray100alpha38 = `rgba(244, 244, 244, 38%)`;
/**
 * @deprecated
 */
export const selectedHover = '#E5EBF1';
/**
 * @deprecated
 */
export const white = `#ffffff`;
/**
 * @deprecated
 */
export const black = `#000000`;

/***************
  Theme colors
***************/
/**
 * @deprecated
 */
export const error = `#de6680`;
/**
 * @deprecated
 */
export const errorBackground = `rgba(222, 102, 128, 0.08)`;
/**
 * @deprecated
 */
export const errorBorder = `rgba(222, 102, 128, 0.5)`;
/**
 * @deprecated
 */
export const errorDark = `#a93554`;
/**
 * @deprecated
 */
export const errorLight = `#ff97af`;
/**
 * @deprecated
 */
export const errorText = `#d53d5e`;
/**
 * @deprecated
 */
export const newError = `#f97575`;
/**
 * @deprecated
 */
export const primary = `#2e78c7`;
/**
 * @deprecated
 */
export const primaryBackground = `rgba(46, 120, 199, 0.08)`;
/**
 * @deprecated
 */
export const primaryBorder = `rgba(46, 120, 199, 0.5)`;
/**
 * @deprecated
 */
export const primaryDark = `#004d96`;
/**
 * @deprecated
 */
export const primaryLight = `#6ba6fa`;
/**
 * @deprecated
 */
export const primaryText = primary;
/**
 * @deprecated
 */
export const success = `#00B5A0`;
/**
 * @deprecated
 */
export const successBackground = `rgba(0, 181, 160, 0.08)`;
/**
 * @deprecated
 */
export const successBorder = `rgba(0, 181, 160, 0.5)`;
/**
 * @deprecated
 */
export const successDark = `#008472`;
/**
 * @deprecated
 */
export const successLight = `#5BE8D1`;
/**
 * @deprecated
 */
export const successText = `#008576`;
/**
 * @deprecated
 */
export const warning = `#F59174`;
/**
 * @deprecated
 */
export const warningBackground = `rgba(245, 145, 116, 0.08)`;
/**
 * @deprecated
 */
export const warningBorder = `rgba(245, 145, 116, 0.5)`;
/**
 * @deprecated
 */
export const warningDark = `#BF6248`;
/**
 * @deprecated
 */
export const warningLight = `#FFC2A3`;
/**
 * @deprecated
 */
export const warningText = `#DA3D10`;
/**
 * @deprecated
 */
export const info = `#03B7CE`;
/**
 * @deprecated
 */
export const infoBackground = `rgba(3, 182, 206, 0.08)`;
/**
 * @deprecated
 */
export const infoBorder = `rgba(3, 182, 206, 0.5)`;
/**
 * @deprecated
 */
export const infoDark = `#00879D`;
/**
 * @deprecated
 */
export const infoLight = `#61EAFF`;
/**
 * @deprecated
 */
export const infoText = `#028293`;

/*******************************
     User Global Variables
*******************************/

// TODO: This is out of date, update to match our semantic variables!
// Global colors
/**
 * @deprecated
 */
export const fontName = `Source Sans Pro`;
/**
 * @deprecated
 */
export const yellow = `#ffc933`;
/**
 * @deprecated
 */
export const gold = `#ffcc33`;
/**
 * @deprecated
 */
export const fullYellow = `#ffff00`;
/**
 * @deprecated
 */
export const red = error;
/**
 * @deprecated
 */
export const darkRed = `#ff2514`;
/**
 * @deprecated
 */
export const teal = info;
/**
 * @deprecated
 */
export const deepTeal = `#039cad`;
/**
 * @deprecated
 */
export const green = success;
/**
 * @deprecated
 */
export const blue = primary;
/**
 * @deprecated
 */
export const deepBlue = `#00648f`;
/**
 * @deprecated
 */
export const heartColor = `#bd70a3`;

// extended colors (These are only used in PanelMultiRunTable currently).
/**
 * @deprecated
 */
export const seaFoamGreen = `#7ed2bf`;
/**
 * @deprecated
 */
export const lightSeaFoamGreen = `#edf8f6`;
/**
 * @deprecated
 */
export const slateBlue = `#68abca`;
/**
 * @deprecated
 */
export const lightSlateBlue = `#e9f3f7`;
/**
 * @deprecated
 */
export const lightYellowOther = `#fff2cc`;
/**
 * @deprecated
 */
export const lightYellow = `#fffbec`;
/**
 * @deprecated
 */
export const goldenrod = `#daa300`;

// privacy badge colors
/**
 * @deprecated
 */
export const fern = `#3ac26c`; // public
/**
 * @deprecated
 */
export const aqua = `#21bfa4`; // team
/**
 * @deprecated
 */
export const cerulean = `#37a0c7`; // private
/**
 * @deprecated
 */
export const orchid = `#a97ccd`; // open
/**
 * @deprecated
 */
export const lightBlue = `#ddedfc`;
/**
 * @deprecated
 */
export const mediumBlue = `#80b3f8`;
/**
 * @deprecated
 */
export const darkBlue = `#338dd8`;
/**
 * @deprecated
 */
export const linkHoverBlue = `#006c95`;
/**
 * @deprecated
 */
export const sky = primaryBackground; // highlighted table cell
/**
 * @deprecated
 */
export const lightSky = `#f3fafd`; // highlighted table row/col

// (almost) AA compliant run text colors (used for legend and tooltip)
// yellow, cyan and seafoam are compromised because AA ver. is very different
/**
 * @deprecated
 */
export const runBlueText = `#3874D8`;
/**
 * @deprecated
 */
export const runRedText = `#D73E3E`;
/**
 * @deprecated
 */
export const runKellyGreenText = `#3D8452`;
/**
 * @deprecated
 */
export const runPurpleText = `#7D54B2`;
/**
 * @deprecated
 */
export const runPinkText = `#DB3169`;
/**
 * @deprecated
 */
export const runOrangeText = `#C5541A`;
/**
 * @deprecated
 */
export const runSeafoamText = `#55AA99`;
/**
 * @deprecated
 */
export const runMagentaText = `#B946BC`;
/**
 * @deprecated
 */
export const runYellowText = `#DD9200`;
/**
 * @deprecated
 */
export const runCyanText = `#1FA8D4`;
/**
 * @deprecated
 */
export const runForestText = `#1E8479`;
/**
 * @deprecated
 */
export const runPeachText = `#C1571C`;
/**
 * @deprecated
 */
export const runLimeText = `#62802C`;
/**
 * @deprecated
 */
export const runBrownText = `#A46750`;
/**
 * @deprecated
 */
export const runMaroonText = `#A12864`;
/**
 * @deprecated
 */
export const runGrayText = `#6E787E`;

// Shared CSS Rules
/**
 * @deprecated
 */
export const accordionContentPadding = `25px 20px`;
/**
 * @deprecated
 */
export const transitionTime = `0.3s`;
/**
 * @deprecated
 */
export const actionAnimationTime = `0.3s`;
/**
 * @deprecated
 */
export const backgroundColorTransition = `background-color ${transitionTime} linear`;
/**
 * @deprecated
 */
export const borderColorTransition = `border-color ${transitionTime} linear`;
/**
 * @deprecated
 */
export const pillBorderRadius = `20px`;
/**
 * @deprecated
 */
export const tabletBreakpoint = `768px`;
/**
 * @deprecated
 */
export const tagPurple = `#e5d6ff`;
/**
 * @deprecated
 */
export const tagBerry = `#ffd6f0`;
/**
 * @deprecated
 */
export const tagRed = `#ffe0e0`;
/**
 * @deprecated
 */
export const tagPeach = `#ffe7cc`;
/**
 * @deprecated
 */
export const tagYellow = `#fde8ad`;
/**
 * @deprecated
 */
export const tagAcid = `#c9f5b5`;
/**
 * @deprecated
 */
export const tagGreen = `#c2f2da`;
/**
 * @deprecated
 */
export const tagTeal = `#c0f0ed`;
/**
 * @deprecated
 */
export const tagBlue = `#d6efff`;
/**
 * @deprecated
 */
export const tagMidnight = `#e0e4ff`;
/**
 * @deprecated
 */
export const tagLightBlue = `#ccf1db`;
/**
 * @deprecated
 */
export const tagTealLightTransparent = `rgba(3, 149, 168, 0.14)`;
/**
 * @deprecated
 */
export const tagTealLight = `rgba(3, 149, 168, 0.2)`;
/**
 * @deprecated
 */
export const tagTealDark = `#038899`;
/**
 * @deprecated
 */
export const tagRedLightTransparent = `rgba(255, 102, 112, 0.16)`;
/**
 * @deprecated
 */
export const tagRedDark = `#eb1c45`;
/**
 * @deprecated
 */
export const galleryAdminPurple = `#bd9df4`;
/**
 * @deprecated
 */
export const commentYellow = `#FFE897`;

// Box shadows

// Box shadows at different levels from material
/**
 * @deprecated
 */
export const levelNavbarBoxShadow = `0 1px 3px rgba(0, 0, 0, 0.02),
0 1px 2px rgba(0, 0, 0, 0.12)`;
/**
 * @deprecated
 */
export const level1BoxShadow = `0 1px 3px rgba(0, 0, 0, 0.12),
0 1px 2px rgba(0, 0, 0, 0.24)`;
/**
 * @deprecated
 */
export const level2BoxShadow = `0 3px 6px rgba(0, 0, 0, 0.16),
0 3px 6px rgba(0, 0, 0, 0.23)`;
/**
 * @deprecated
 */
export const level3BoxShadow = `0 10px 20px rgba(0, 0, 0, 0.19),
0 6px 6px rgba(0, 0, 0, 0.23)`;
/**
 * @deprecated
 */
export const level3BoxShadowFaint = `0 10px 20px rgba(0, 0, 0, 0.07),
0 6px 6px rgba(0, 0, 0, 0.07)`;
/**
 * @deprecated
 */
export const level4BoxShadow = `0 14px 28px rgba(0, 0, 0, 0.25),
0 10px 10px rgba(0, 0, 0, 0.22)`;
/**
 * @deprecated
 */
export const level5BoxShadow = `0 19px 38px rgba(0, 0, 0, 0.30),
0 15px 12px rgba(0, 0, 0, 0.22)`;
/**
 * @deprecated
 */
export const boxShadowButtonsCharts = `0px 1px 3px 0px rgba(54,58,61,0.12)`;
/**
 * @deprecated
 */
export const boxShadowButtonsChartsHover = `0px 3px 6px 0px rgba(54,58,61,0.12)`;
/**
 * @deprecated
 */
export const boxShadowModal = `0px 8px 16px 0px rgba(54,58,61,0.16)`;
/**
 * @deprecated
 */
export const boxShadowDropdown = `0px 4px 8px 0px rgba(54,58,61,0.12)`;
/**
 * @deprecated
 */
export const boxShadowSection = `1px 1px 20px 0px #e6e6e6`;

// Inner tab box-shadow
/**
 * @deprecated
 */
export const tabBoxShadow = `inset 0 -4px 25px -8px rgba(0, 0, 0, 0.2)`;

// Font sizes
/**
 * @deprecated
 */
export const fontSizeStandard = `16px`;
/**
 * @deprecated
 */
export const lineHeightStandard = `24px`;
/**
 * @deprecated
 */
export const fontWeightStandard = `100`;

// Sizes
/**
 * @deprecated
 */
export const navbarHeight = `0px`;

// Spacing
/**
 * @deprecated
 */
export const pageHeaderButtonSpacing = `10px`;
/**
 * @deprecated
 */
export const standardSpacingUnit = `8px`;
/**
 * @deprecated
 */
export const spu = standardSpacingUnit;
/**
 * @deprecated
 */
export const largeStandardSpacingUnit = `10px`;
/**
 * @deprecated
 */
export const largeSpu = largeStandardSpacingUnit;

// Functional Color Rules
// These should wrap the above colors with semantic names
// TODO: Figure out how tofontSizeStandard organize this
// Action Colors, buttons,
/**
 * @deprecated
 */
export const actionButtonFocusedColor = deepTeal;
/**
 * @deprecated
 */
export const actionButtonFocusedFontColor = white;
/**
 * @deprecated
 */
export const actionButtonFocusedBorderColor = deepTeal;
/**
 * @deprecated
 */
export const actionButtonActiveColor = info;
/**
 * @deprecated
 */
export const actionButtonActiveFontColor = white;
/**
 * @deprecated
 */
export const actionButtonActiveBorderColor = info;
/**
 * @deprecated
 */
export const actionButtonDefaultColor = gray100;
/**
 * @deprecated
 */
export const actionButtonDefaultFontColor = textPrimary;
/**
 * @deprecated
 */
export const actionButtonDefaultBorderColor = `transparent`;
/**
 * @deprecated
 */
export const actionFocusedColor = primaryBackground;
/**
 * @deprecated
 */
export const actionFocusedFontColor = textPrimary;
/**
 * @deprecated
 */
export const actionActiveColor = primaryBackground;
/**
 * @deprecated
 */
export const actionActiveFontColor = textPrimary;
/**
 * @deprecated
 */
export const separatorBorder = `1px solid ${border}`;
/**
 * @deprecated
 */
export const searchNavHeight = SEARCH_NAV_HEIGHT;
/**
 * @deprecated
 */
export const galleryNavHeight = SEARCH_NAV_HEIGHT;
/**
 * @deprecated
 */
export const fancyPageSidebarWidth = `52px`;
/**
 * @deprecated
 */
export const mobileBarHeight = fancyPageSidebarWidth;
/**
 * @deprecated
 */
export const reportCoverHorizontalMargin = `28px`;
/**
 * @deprecated
 */
export const reportDraftBackgroundColor = `#fff8e3`;
/**
 * @deprecated
 */
export const reportFontSize = `18px`;
