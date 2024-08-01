import React, {ElementType, SVGProps} from 'react';

import {ReactComponent as ImportAddNew} from '../../assets/icons/icon-add-new.svg';
import {ReactComponent as ImportAddReaction} from '../../assets/icons/icon-add-reaction.svg';
import {ReactComponent as ImportAdminShieldSafe} from '../../assets/icons/icon-admin-shield-safe.svg';
import {ReactComponent as ImportAmazonSagemaker} from '../../assets/icons/icon-amazon-sagemaker.svg';
import {ReactComponent as ImportArea} from '../../assets/icons/icon-area.svg';
import {ReactComponent as ImportArtifactTypeAlt} from '../../assets/icons/icon-artifact-type-alt.svg';
import {ReactComponent as ImportAudioVolume} from '../../assets/icons/icon-audio-volume.svg';
import {ReactComponent as ImportAutomationRobotArm} from '../../assets/icons/icon-automation-robot-arm.svg';
import {ReactComponent as ImportBack} from '../../assets/icons/icon-back.svg';
import {ReactComponent as ImportBellNotifications} from '../../assets/icons/icon-bell-notifications.svg';
import {ReactComponent as ImportBenchmarkSquare} from '../../assets/icons/icon-benchmark-square.svg';
import {ReactComponent as ImportBlogReport} from '../../assets/icons/icon-blog-report.svg';
import {ReactComponent as ImportBookDictionary} from '../../assets/icons/icon-book-dictionary.svg';
import {ReactComponent as ImportBoolean} from '../../assets/icons/icon-boolean.svg';
import {ReactComponent as ImportBoxPlot} from '../../assets/icons/icon-box-plot.svg';
import {ReactComponent as ImportBug} from '../../assets/icons/icon-bug.svg';
import {ReactComponent as ImportCategoryMultimodal} from '../../assets/icons/icon-category-multimodal.svg';
import {ReactComponent as ImportChartHorizontalBars} from '../../assets/icons/icon-chart-horizontal-bars.svg';
import {ReactComponent as ImportChartPie} from '../../assets/icons/icon-chart-pie.svg';
import {ReactComponent as ImportChartScatterplot} from '../../assets/icons/icon-chart-scatterplot.svg';
import {ReactComponent as ImportChartVerticalBars} from '../../assets/icons/icon-chart-vertical-bars.svg';
import {ReactComponent as ImportCheckmark} from '../../assets/icons/icon-checkmark.svg';
import {ReactComponent as ImportCheckmarkCircle} from '../../assets/icons/icon-checkmark-circle.svg';
import {ReactComponent as ImportChevronBack} from '../../assets/icons/icon-chevron-back.svg';
import {ReactComponent as ImportChevronDown} from '../../assets/icons/icon-chevron-down.svg';
import {ReactComponent as ImportChevronNext} from '../../assets/icons/icon-chevron-next.svg';
import {ReactComponent as ImportChevronUp} from '../../assets/icons/icon-chevron-up.svg';
import {ReactComponent as ImportCircle} from '../../assets/icons/icon-circle.svg';
import {ReactComponent as ImportClearAll} from '../../assets/icons/icon-clear-all.svg';
import {ReactComponent as ImportClose} from '../../assets/icons/icon-close.svg';
import {ReactComponent as ImportCloud} from '../../assets/icons/icon-cloud.svg';
import {ReactComponent as ImportCodeAlt} from '../../assets/icons/icon-code-alt.svg';
import {ReactComponent as ImportCollapse} from '../../assets/icons/icon-collapse.svg';
import {ReactComponent as ImportColor} from '../../assets/icons/icon-color.svg';
import {ReactComponent as ImportColumn} from '../../assets/icons/icon-column.svg';
import {ReactComponent as ImportContentFullWidth} from '../../assets/icons/icon-content-full-width.svg';
import {ReactComponent as ImportContentNarrow} from '../../assets/icons/icon-content-narrow.svg';
import {ReactComponent as ImportContentWide} from '../../assets/icons/icon-content-wide.svg';
import {ReactComponent as ImportContractLeft} from '../../assets/icons/icon-contract-left.svg';
import {ReactComponent as ImportCopy} from '../../assets/icons/icon-copy.svg';
import {ReactComponent as ImportCreditCardPayment} from '../../assets/icons/icon-credit-card-payment.svg';
import {ReactComponent as ImportCropBeginning} from '../../assets/icons/icon-crop-beginning.svg';
import {ReactComponent as ImportCropEnd} from '../../assets/icons/icon-crop-end.svg';
import {ReactComponent as ImportCropMiddle} from '../../assets/icons/icon-crop-middle.svg';
import {ReactComponent as ImportCross} from '../../assets/icons/icon-cross.svg';
import {ReactComponent as ImportCrownPro} from '../../assets/icons/icon-crown-pro.svg';
import {ReactComponent as ImportCubeContainer} from '../../assets/icons/icon-cube-container.svg';
import {ReactComponent as ImportDashboardBlackboard} from '../../assets/icons/icon-dashboard-blackboard.svg';
import {ReactComponent as ImportDatabaseArtifacts} from '../../assets/icons/icon-database-artifacts.svg';
import {ReactComponent as ImportDate} from '../../assets/icons/icon-date.svg';
import {ReactComponent as ImportDelete} from '../../assets/icons/icon-delete.svg';
import {ReactComponent as ImportDiamond} from '../../assets/icons/icon-diamond.svg';
import {ReactComponent as ImportDiscordSocial} from '../../assets/icons/icon-discord-social.svg';
import {ReactComponent as ImportDockerWhale} from '../../assets/icons/icon-docker-whale.svg';
import {ReactComponent as ImportDocument} from '../../assets/icons/icon-document.svg';
import {ReactComponent as ImportDocumentation} from '../../assets/icons/icon-documentation.svg';
import {ReactComponent as ImportDownload} from '../../assets/icons/icon-download.svg';
import {ReactComponent as ImportDraft} from '../../assets/icons/icon-draft.svg';
import {ReactComponent as ImportEducationAcademic} from '../../assets/icons/icon-education-academic.svg';
import {ReactComponent as ImportEmailAt} from '../../assets/icons/icon-email-at.svg';
import {ReactComponent as ImportEmailEnvelope} from '../../assets/icons/icon-email-envelope.svg';
import {ReactComponent as ImportExpandRight} from '../../assets/icons/icon-expand-right.svg';
import {ReactComponent as ImportExpandUncollapse} from '../../assets/icons/icon-expand-uncollapse.svg';
import {ReactComponent as ImportExportShareUpload} from '../../assets/icons/icon-export-share-upload.svg';
import {ReactComponent as ImportFacebookSocial} from '../../assets/icons/icon-facebook-social.svg';
import {ReactComponent as ImportFailed} from '../../assets/icons/icon-failed.svg';
import {ReactComponent as ImportFilterAlt} from '../../assets/icons/icon-filter-alt.svg';
import {ReactComponent as ImportFlashBolt} from '../../assets/icons/icon-flash-bolt.svg';
import {ReactComponent as ImportFolderAlt} from '../../assets/icons/icon-folder-alt.svg';
import {ReactComponent as ImportFolderFill} from '../../assets/icons/icon-folder-fill.svg';
import {ReactComponent as ImportFolderProject} from '../../assets/icons/icon-folder-project.svg';
import {ReactComponent as ImportFolderProjectMove} from '../../assets/icons/icon-folder-project-move.svg';
import {ReactComponent as ImportForumChatBubble} from '../../assets/icons/icon-forum-chat-bubble.svg';
import {ReactComponent as ImportForwardNext} from '../../assets/icons/icon-forward-next.svg';
import {ReactComponent as ImportFullScreenModeExpand} from '../../assets/icons/icon-full-screen-mode-expand.svg';
import {ReactComponent as ImportGhostAgent} from '../../assets/icons/icon-ghost-agent.svg';
import {ReactComponent as ImportGit} from '../../assets/icons/icon-git.svg';
import {ReactComponent as ImportGithub} from '../../assets/icons/icon-github.svg';
import {ReactComponent as ImportGroup} from '../../assets/icons/icon-group.svg';
import {ReactComponent as ImportHeadset} from '../../assets/icons/icon-headset.svg';
import {ReactComponent as ImportHeart} from '../../assets/icons/icon-heart.svg';
import {ReactComponent as ImportHeartFilled} from '../../assets/icons/icon-heart-filled.svg';
import {ReactComponent as ImportHelpAlt} from '../../assets/icons/icon-help-alt.svg';
import {ReactComponent as ImportHideHidden} from '../../assets/icons/icon-hide-hidden.svg';
import {ReactComponent as ImportHistory} from '../../assets/icons/icon-history.svg';
import {ReactComponent as ImportHome} from '../../assets/icons/icon-home.svg';
import {ReactComponent as ImportIdle} from '../../assets/icons/icon-idle.svg';
import {ReactComponent as ImportIgnoreOutliers} from '../../assets/icons/icon-ignore-outliers.svg';
import {ReactComponent as ImportImpersonateMaskAlt} from '../../assets/icons/icon-impersonate-mask-alt.svg';
import {ReactComponent as ImportImportInsert} from '../../assets/icons/icon-import-insert.svg';
import {ReactComponent as ImportInfo} from '../../assets/icons/icon-info.svg';
import {ReactComponent as ImportJobAutomation} from '../../assets/icons/icon-job-automation.svg';
import {ReactComponent as ImportJobCalculator} from '../../assets/icons/icon-job-calculator.svg';
import {ReactComponent as ImportJobProgramCode} from '../../assets/icons/icon-job-program-code.svg';
import {ReactComponent as ImportJoyceTransformersLogo} from '../../assets/icons/icon-joyce-transformers-logo.svg';
import {ReactComponent as ImportJoyceXgboostLogo} from '../../assets/icons/icon-joyce-xgboost-logo.svg';
import {ReactComponent as ImportKerasLogo} from '../../assets/icons/icon-keras-logo.svg';
import {ReactComponent as ImportKeyAdmin} from '../../assets/icons/icon-key-admin.svg';
import {ReactComponent as ImportKeyAdminPrivate} from '../../assets/icons/icon-key-admin-private.svg';
import {ReactComponent as ImportKubernetes} from '../../assets/icons/icon-kubernetes.svg';
import {ReactComponent as ImportLanguages} from '../../assets/icons/icon-languages.svg';
import {ReactComponent as ImportLaptopLocalComputer} from '../../assets/icons/icon-laptop-local-computer.svg';
import {ReactComponent as ImportLayoutGrid} from '../../assets/icons/icon-layout-grid.svg';
import {ReactComponent as ImportLayoutHorizontal} from '../../assets/icons/icon-layout-horizontal.svg';
import {ReactComponent as ImportLayoutTabs} from '../../assets/icons/icon-layout-tabs.svg';
import {ReactComponent as ImportLayoutVertical} from '../../assets/icons/icon-layout-vertical.svg';
import {ReactComponent as ImportLightbulbInfo} from '../../assets/icons/icon-lightbulb-info.svg';
import {ReactComponent as ImportLinePlotAlt2} from '../../assets/icons/icon-line-plot-alt2.svg';
import {ReactComponent as ImportLinearScale} from '../../assets/icons/icon-linear-scale.svg';
import {ReactComponent as ImportLinkAlt} from '../../assets/icons/icon-link-alt.svg';
import {ReactComponent as ImportLinkedinSocial} from '../../assets/icons/icon-linkedin-social.svg';
import {ReactComponent as ImportList} from '../../assets/icons/icon-list.svg';
import {ReactComponent as ImportListBullets} from '../../assets/icons/icon-list-bullets.svg';
import {ReactComponent as ImportLoading} from '../../assets/icons/icon-loading.svg';
import {ReactComponent as ImportLockClosed} from '../../assets/icons/icon-lock-closed.svg';
import {ReactComponent as ImportLockOpen} from '../../assets/icons/icon-lock-open.svg';
import {ReactComponent as ImportLockedConstrained} from '../../assets/icons/icon-locked-constrained.svg';
import {ReactComponent as ImportLogOut} from '../../assets/icons/icon-log-out.svg';
import {ReactComponent as ImportLogoColab} from '../../assets/icons/icon-logo-colab.svg';
import {ReactComponent as ImportMagicWandStar} from '../../assets/icons/icon-magic-wand-star.svg';
import {ReactComponent as ImportMagicWandStick} from '../../assets/icons/icon-magic-wand-stick.svg';
import {ReactComponent as ImportMenu} from '../../assets/icons/icon-menu.svg';
import {ReactComponent as ImportMicrophoneAudio} from '../../assets/icons/icon-microphone-audio.svg';
import {ReactComponent as ImportMinimizeMode} from '../../assets/icons/icon-minimize-mode.svg';
import {ReactComponent as ImportModel} from '../../assets/icons/icon-model.svg';
import {ReactComponent as ImportModelOnDark} from '../../assets/icons/icon-model-on-dark.svg';
import {ReactComponent as ImportMusicAudio} from '../../assets/icons/icon-music-audio.svg';
import {ReactComponent as ImportNumber} from '../../assets/icons/icon-number.svg';
import {ReactComponent as ImportOpenNewTab} from '../../assets/icons/icon-open-new-tab.svg';
import {ReactComponent as ImportOpenaiLogo} from '../../assets/icons/icon-openai-logo.svg';
import {ReactComponent as ImportOrchestrationLaunch} from '../../assets/icons/icon-orchestration-launch.svg';
import {ReactComponent as ImportOrganizationCorporate} from '../../assets/icons/icon-organization-corporate.svg';
import {ReactComponent as ImportOverflowHorizontal} from '../../assets/icons/icon-overflow-horizontal.svg';
import {ReactComponent as ImportPanTool} from '../../assets/icons/icon-pan-tool.svg';
import {ReactComponent as ImportPanTool1} from '../../assets/icons/icon-pan-tool-1.svg';
import {ReactComponent as ImportPanel} from '../../assets/icons/icon-panel.svg';
import {ReactComponent as ImportPanelAutoGen} from '../../assets/icons/icon-panel-auto-gen.svg';
import {ReactComponent as ImportPanelManual} from '../../assets/icons/icon-panel-manual.svg';
import {ReactComponent as ImportParentBackUp} from '../../assets/icons/icon-parent-back-up.svg';
import {ReactComponent as ImportPause} from '../../assets/icons/icon-pause.svg';
import {ReactComponent as ImportPaused} from '../../assets/icons/icon-paused.svg';
import {ReactComponent as ImportPencilEdit} from '../../assets/icons/icon-pencil-edit.svg';
import {ReactComponent as ImportPhoto} from '../../assets/icons/icon-photo.svg';
import {ReactComponent as ImportPin} from '../../assets/icons/icon-pin.svg';
import {ReactComponent as ImportPlay} from '../../assets/icons/icon-play.svg';
import {ReactComponent as ImportPriorityCritical} from '../../assets/icons/icon-priority-critical.svg';
import {ReactComponent as ImportPriorityHigh} from '../../assets/icons/icon-priority-high.svg';
import {ReactComponent as ImportPriorityLow} from '../../assets/icons/icon-priority-low.svg';
import {ReactComponent as ImportPriorityNone} from '../../assets/icons/icon-priority-none.svg';
import {ReactComponent as ImportPrivacyOpen} from '../../assets/icons/icon-privacy-open.svg';
import {ReactComponent as ImportPythonLogo} from '../../assets/icons/icon-python-logo.svg';
import {ReactComponent as ImportPytorchLightningLogo} from '../../assets/icons/icon-pytorch-lightning-logo.svg';
import {ReactComponent as ImportPytorchLogo} from '../../assets/icons/icon-pytorch-logo.svg';
import {ReactComponent as ImportQueue} from '../../assets/icons/icon-queue.svg';
import {ReactComponent as ImportQueued} from '../../assets/icons/icon-queued.svg';
import {ReactComponent as ImportRandomizeAlt} from '../../assets/icons/icon-randomize-alt.svg';
import {ReactComponent as ImportRandomizeResetReload} from '../../assets/icons/icon-randomize-reset-reload.svg';
import {ReactComponent as ImportRecentClock} from '../../assets/icons/icon-recent-clock.svg';
import {ReactComponent as ImportRedditSocial} from '../../assets/icons/icon-reddit-social.svg';
import {ReactComponent as ImportRedo} from '../../assets/icons/icon-redo.svg';
import {ReactComponent as ImportRegex} from '../../assets/icons/icon-regex.svg';
import {ReactComponent as ImportRegistries} from '../../assets/icons/icon-registries.svg';
import {ReactComponent as ImportRemove} from '../../assets/icons/icon-remove.svg';
import {ReactComponent as ImportRemoveAlt} from '../../assets/icons/icon-remove-alt.svg';
import {ReactComponent as ImportReport} from '../../assets/icons/icon-report.svg';
import {ReactComponent as ImportRetry} from '../../assets/icons/icon-retry.svg';
import {ReactComponent as ImportRobotServiceMember} from '../../assets/icons/icon-robot-service-member.svg';
import {ReactComponent as ImportRocketLaunch} from '../../assets/icons/icon-rocket-launch.svg';
import {ReactComponent as ImportRowHeightLarge} from '../../assets/icons/icon-row-height-large.svg';
import {ReactComponent as ImportRowHeightMedium} from '../../assets/icons/icon-row-height-medium.svg';
import {ReactComponent as ImportRowHeightSmall} from '../../assets/icons/icon-row-height-small.svg';
import {ReactComponent as ImportRowHeightXlarge} from '../../assets/icons/icon-row-height-xlarge.svg';
import {ReactComponent as ImportRun} from '../../assets/icons/icon-run.svg';
import {ReactComponent as ImportRunningRepeat} from '../../assets/icons/icon-running-repeat.svg';
import {ReactComponent as ImportSave} from '../../assets/icons/icon-save.svg';
import {ReactComponent as ImportScikitLogo} from '../../assets/icons/icon-scikit-logo.svg';
import {ReactComponent as ImportSearch} from '../../assets/icons/icon-search.svg';
import {ReactComponent as ImportSelectMoveTool} from '../../assets/icons/icon-select-move-tool.svg';
import {ReactComponent as ImportSettings} from '../../assets/icons/icon-settings.svg';
import {ReactComponent as ImportSettingsParameters} from '../../assets/icons/icon-settings-parameters.svg';
import {ReactComponent as ImportShareExport} from '../../assets/icons/icon-share-export.svg';
import {ReactComponent as ImportShareWith} from '../../assets/icons/icon-share-with.svg';
import {ReactComponent as ImportShieldRemove} from '../../assets/icons/icon-shield-remove.svg';
import {ReactComponent as ImportShowVisible} from '../../assets/icons/icon-show-visible.svg';
import {ReactComponent as ImportSmoothing} from '../../assets/icons/icon-smoothing.svg';
import {ReactComponent as ImportSort} from '../../assets/icons/icon-sort.svg';
import {ReactComponent as ImportSortAscending} from '../../assets/icons/icon-sort-ascending.svg';
import {ReactComponent as ImportSortDescending} from '../../assets/icons/icon-sort-descending.svg';
import {ReactComponent as ImportSplit} from '../../assets/icons/icon-split.svg';
import {ReactComponent as ImportSquare} from '../../assets/icons/icon-square.svg';
import {ReactComponent as ImportStar} from '../../assets/icons/icon-star.svg';
import {ReactComponent as ImportStarFilled} from '../../assets/icons/icon-star-filled.svg';
import {ReactComponent as ImportStop} from '../../assets/icons/icon-stop.svg';
import {ReactComponent as ImportStopped} from '../../assets/icons/icon-stopped.svg';
import {ReactComponent as ImportSweepBayes} from '../../assets/icons/icon-sweep-bayes.svg';
import {ReactComponent as ImportSweepGrid} from '../../assets/icons/icon-sweep-grid.svg';
import {ReactComponent as ImportSweepRandomSearch} from '../../assets/icons/icon-sweep-random-search.svg';
import {ReactComponent as ImportSweepsAlt} from '../../assets/icons/icon-sweeps-alt.svg';
import {ReactComponent as ImportSweepsBroom} from '../../assets/icons/icon-sweeps-broom.svg';
import {ReactComponent as ImportSweepsBroomAlt} from '../../assets/icons/icon-sweeps-broom-alt.svg';
import {ReactComponent as ImportSystem} from '../../assets/icons/icon-system.svg';
import {ReactComponent as ImportSystemChip} from '../../assets/icons/icon-system-chip.svg';
import {ReactComponent as ImportSystemChipAlt} from '../../assets/icons/icon-system-chip-alt.svg';
import {ReactComponent as ImportTable} from '../../assets/icons/icon-table.svg';
import {ReactComponent as ImportTag} from '../../assets/icons/icon-tag.svg';
import {ReactComponent as ImportTensorflowLogo} from '../../assets/icons/icon-tensorflow-logo.svg';
import {ReactComponent as ImportTextLanguage} from '../../assets/icons/icon-text-language.svg';
import {ReactComponent as ImportTextLanguageAlt} from '../../assets/icons/icon-text-language-alt.svg';
import {ReactComponent as ImportThumbsDown} from '../../assets/icons/icon-thumbs-down.svg';
import {ReactComponent as ImportThumbsUp} from '../../assets/icons/icon-thumbs-up.svg';
import {ReactComponent as ImportTriangleDown} from '../../assets/icons/icon-triangle-down.svg';
import {ReactComponent as ImportTriangleLeft} from '../../assets/icons/icon-triangle-left.svg';
import {ReactComponent as ImportTriangleRight} from '../../assets/icons/icon-triangle-right.svg';
import {ReactComponent as ImportTriangleUp} from '../../assets/icons/icon-triangle-up.svg';
import {ReactComponent as ImportTriggerAlt} from '../../assets/icons/icon-trigger-alt.svg';
import {ReactComponent as ImportTwitter} from '../../assets/icons/icon-twitter.svg';
import {ReactComponent as ImportTypeBoolean} from '../../assets/icons/icon-type-boolean.svg';
import {ReactComponent as ImportTypeNumber} from '../../assets/icons/icon-type-number.svg';
import {ReactComponent as ImportTypeStringQuote} from '../../assets/icons/icon-type-string-quote.svg';
import {ReactComponent as ImportUndeterminateVisibility} from '../../assets/icons/icon-undeterminate-visibility.svg';
import {ReactComponent as ImportUndo} from '../../assets/icons/icon-undo.svg';
import {ReactComponent as ImportUnlockedUnconstrained} from '../../assets/icons/icon-unlocked-unconstrained.svg';
import {ReactComponent as ImportUserAuthor} from '../../assets/icons/icon-user-author.svg';
import {ReactComponent as ImportUserProfilePersonal} from '../../assets/icons/icon-user-profile-personal.svg';
import {ReactComponent as ImportUsersTeam} from '../../assets/icons/icon-users-team.svg';
import {ReactComponent as ImportVersionsLayers} from '../../assets/icons/icon-versions-layers.svg';
import {ReactComponent as ImportVertexGCP} from '../../assets/icons/icon-vertex-gcp.svg';
import {ReactComponent as ImportVideoPlay} from '../../assets/icons/icon-video-play.svg';
import {ReactComponent as ImportViewGlasses} from '../../assets/icons/icon-view-glasses.svg';
import {ReactComponent as ImportWandb} from '../../assets/icons/icon-wandb.svg';
import {ReactComponent as ImportWarning} from '../../assets/icons/icon-warning.svg';
import {ReactComponent as ImportWarningAlt} from '../../assets/icons/icon-warning-alt.svg';
import {ReactComponent as ImportWeave} from '../../assets/icons/icon-weave.svg';
import {ReactComponent as ImportWeaveGroupBoard} from '../../assets/icons/icon-weave-group-board.svg';
import {ReactComponent as ImportWebhook} from '../../assets/icons/icon-webhook.svg';
import {ReactComponent as ImportXAxiAlt} from '../../assets/icons/icon-x-axi-alt.svg';
import {ReactComponent as ImportXAxis} from '../../assets/icons/icon-x-axis.svg';
import {ReactComponent as ImportYoutubeSocial} from '../../assets/icons/icon-youtube-social.svg';
import {ReactComponent as ImportZoomInTool} from '../../assets/icons/icon-zoom-in-tool.svg';
import {IconName} from './types';

type SVGIconProps = SVGProps<SVGElement>;

// The natural width/height in our SVG files is 24x24 when the design team provides them.
// However, the design team would also like the default icon size to be 20x20 in our app,
// so we override those attributes for the icon exports.
const updateIconProps = (props: SVGIconProps) => {
  return {
    width: 20,
    height: 20,
    ...props,
  };
};
export const IconAddNew = (props: SVGIconProps) => (
  <ImportAddNew {...updateIconProps(props)} />
);
export const IconAddReaction = (props: SVGIconProps) => (
  <ImportAddReaction {...updateIconProps(props)} />
);
export const IconAdminShieldSafe = (props: SVGIconProps) => (
  <ImportAdminShieldSafe {...updateIconProps(props)} />
);
export const IconAmazonSagemaker = (props: SVGIconProps) => (
  <ImportAmazonSagemaker {...updateIconProps(props)} />
);
export const IconArea = (props: SVGIconProps) => (
  <ImportArea {...updateIconProps(props)} />
);
export const IconArtifactTypeAlt = (props: SVGIconProps) => (
  <ImportArtifactTypeAlt {...updateIconProps(props)} />
);
export const IconAudioVolume = (props: SVGIconProps) => (
  <ImportAudioVolume {...updateIconProps(props)} />
);
export const IconAutomationRobotArm = (props: SVGIconProps) => (
  <ImportAutomationRobotArm {...updateIconProps(props)} />
);
export const IconBack = (props: SVGIconProps) => (
  <ImportBack {...updateIconProps(props)} />
);
export const IconBellNotifications = (props: SVGIconProps) => (
  <ImportBellNotifications {...updateIconProps(props)} />
);
export const IconBenchmarkSquare = (props: SVGIconProps) => (
  <ImportBenchmarkSquare {...updateIconProps(props)} />
);
export const IconBlogReport = (props: SVGIconProps) => (
  <ImportBlogReport {...updateIconProps(props)} />
);
export const IconBookDictionary = (props: SVGIconProps) => (
  <ImportBookDictionary {...updateIconProps(props)} />
);
export const IconBoolean = (props: SVGIconProps) => (
  <ImportBoolean {...updateIconProps(props)} />
);
export const IconBoxPlot = (props: SVGIconProps) => (
  <ImportBoxPlot {...updateIconProps(props)} />
);
export const IconBug = (props: SVGIconProps) => (
  <ImportBug {...updateIconProps(props)} />
);
export const IconCategoryMultimodal = (props: SVGIconProps) => (
  <ImportCategoryMultimodal {...updateIconProps(props)} />
);
export const IconChartHorizontalBars = (props: SVGIconProps) => (
  <ImportChartHorizontalBars {...updateIconProps(props)} />
);
export const IconChartPie = (props: SVGIconProps) => (
  <ImportChartPie {...updateIconProps(props)} />
);
export const IconChartScatterplot = (props: SVGIconProps) => (
  <ImportChartScatterplot {...updateIconProps(props)} />
);
export const IconChartVerticalBars = (props: SVGIconProps) => (
  <ImportChartVerticalBars {...updateIconProps(props)} />
);
export const IconCheckmark = (props: SVGIconProps) => (
  <ImportCheckmark {...updateIconProps(props)} />
);
export const IconCheckmarkCircle = (props: SVGIconProps) => (
  <ImportCheckmarkCircle {...updateIconProps(props)} />
);
export const IconChevronBack = (props: SVGIconProps) => (
  <ImportChevronBack {...updateIconProps(props)} />
);
export const IconChevronDown = (props: SVGIconProps) => (
  <ImportChevronDown {...updateIconProps(props)} />
);
export const IconChevronNext = (props: SVGIconProps) => (
  <ImportChevronNext {...updateIconProps(props)} />
);
export const IconChevronUp = (props: SVGIconProps) => (
  <ImportChevronUp {...updateIconProps(props)} />
);
export const IconCircle = (props: SVGIconProps) => (
  <ImportCircle {...updateIconProps(props)} />
);
export const IconClearAll = (props: SVGIconProps) => (
  <ImportClearAll {...updateIconProps(props)} />
);
export const IconClose = (props: SVGIconProps) => (
  <ImportClose {...updateIconProps(props)} />
);
export const IconCloud = (props: SVGIconProps) => (
  <ImportCloud {...updateIconProps(props)} />
);
export const IconCodeAlt = (props: SVGIconProps) => (
  <ImportCodeAlt {...updateIconProps(props)} />
);
export const IconCollapse = (props: SVGIconProps) => (
  <ImportCollapse {...updateIconProps(props)} />
);
export const IconColor = (props: SVGIconProps) => (
  <ImportColor {...updateIconProps(props)} />
);
export const IconColumn = (props: SVGIconProps) => (
  <ImportColumn {...updateIconProps(props)} />
);
export const IconContentFullWidth = (props: SVGIconProps) => (
  <ImportContentFullWidth {...updateIconProps(props)} />
);
export const IconContentNarrow = (props: SVGIconProps) => (
  <ImportContentNarrow {...updateIconProps(props)} />
);
export const IconContentWide = (props: SVGIconProps) => (
  <ImportContentWide {...updateIconProps(props)} />
);
export const IconContractLeft = (props: SVGIconProps) => (
  <ImportContractLeft {...updateIconProps(props)} />
);
export const IconCopy = (props: SVGIconProps) => (
  <ImportCopy {...updateIconProps(props)} />
);
export const IconCreditCardPayment = (props: SVGIconProps) => (
  <ImportCreditCardPayment {...updateIconProps(props)} />
);
export const IconCropBeginning = (props: SVGIconProps) => (
  <ImportCropBeginning {...updateIconProps(props)} />
);
export const IconCropEnd = (props: SVGIconProps) => (
  <ImportCropEnd {...updateIconProps(props)} />
);
export const IconCropMiddle = (props: SVGIconProps) => (
  <ImportCropMiddle {...updateIconProps(props)} />
);
export const IconCross = (props: SVGIconProps) => (
  <ImportCross {...updateIconProps(props)} />
);
export const IconCrownPro = (props: SVGIconProps) => (
  <ImportCrownPro {...updateIconProps(props)} />
);
export const IconCubeContainer = (props: SVGIconProps) => (
  <ImportCubeContainer {...updateIconProps(props)} />
);
export const IconDashboardBlackboard = (props: SVGIconProps) => (
  <ImportDashboardBlackboard {...updateIconProps(props)} />
);
export const IconDatabaseArtifacts = (props: SVGIconProps) => (
  <ImportDatabaseArtifacts {...updateIconProps(props)} />
);
export const IconDate = (props: SVGIconProps) => (
  <ImportDate {...updateIconProps(props)} />
);
export const IconDelete = (props: SVGIconProps) => (
  <ImportDelete {...updateIconProps(props)} />
);
export const IconDiamond = (props: SVGIconProps) => (
  <ImportDiamond {...updateIconProps(props)} />
);
export const IconDiscordSocial = (props: SVGIconProps) => (
  <ImportDiscordSocial {...updateIconProps(props)} />
);
export const IconDockerWhale = (props: SVGIconProps) => (
  <ImportDockerWhale {...updateIconProps(props)} />
);
export const IconDocument = (props: SVGIconProps) => (
  <ImportDocument {...updateIconProps(props)} />
);
export const IconDocumentation = (props: SVGIconProps) => (
  <ImportDocumentation {...updateIconProps(props)} />
);
export const IconDownload = (props: SVGIconProps) => (
  <ImportDownload {...updateIconProps(props)} />
);
export const IconDraft = (props: SVGIconProps) => (
  <ImportDraft {...updateIconProps(props)} />
);
export const IconEducationAcademic = (props: SVGIconProps) => (
  <ImportEducationAcademic {...updateIconProps(props)} />
);
export const IconEmailAt = (props: SVGIconProps) => (
  <ImportEmailAt {...updateIconProps(props)} />
);
export const IconEmailEnvelope = (props: SVGIconProps) => (
  <ImportEmailEnvelope {...updateIconProps(props)} />
);
export const IconExpandRight = (props: SVGIconProps) => (
  <ImportExpandRight {...updateIconProps(props)} />
);
export const IconExpandUncollapse = (props: SVGIconProps) => (
  <ImportExpandUncollapse {...updateIconProps(props)} />
);
export const IconExportShareUpload = (props: SVGIconProps) => (
  <ImportExportShareUpload {...updateIconProps(props)} />
);
export const IconFacebookSocial = (props: SVGIconProps) => (
  <ImportFacebookSocial {...updateIconProps(props)} />
);
export const IconFailed = (props: SVGIconProps) => (
  <ImportFailed {...updateIconProps(props)} />
);
export const IconFilterAlt = (props: SVGIconProps) => (
  <ImportFilterAlt {...updateIconProps(props)} />
);
export const IconFlashBolt = (props: SVGIconProps) => (
  <ImportFlashBolt {...updateIconProps(props)} />
);
export const IconFolderAlt = (props: SVGIconProps) => (
  <ImportFolderAlt {...updateIconProps(props)} />
);
export const IconFolderFill = (props: SVGIconProps) => (
  <ImportFolderFill {...updateIconProps(props)} />
);
export const IconFolderProject = (props: SVGIconProps) => (
  <ImportFolderProject {...updateIconProps(props)} />
);
export const IconFolderProjectMove = (props: SVGIconProps) => (
  <ImportFolderProjectMove {...updateIconProps(props)} />
);
export const IconForumChatBubble = (props: SVGIconProps) => (
  <ImportForumChatBubble {...updateIconProps(props)} />
);
export const IconForwardNext = (props: SVGIconProps) => (
  <ImportForwardNext {...updateIconProps(props)} />
);
export const IconFullScreenModeExpand = (props: SVGIconProps) => (
  <ImportFullScreenModeExpand {...updateIconProps(props)} />
);
export const IconGhostAgent = (props: SVGIconProps) => (
  <ImportGhostAgent {...updateIconProps(props)} />
);
export const IconGit = (props: SVGIconProps) => (
  <ImportGit {...updateIconProps(props)} />
);
export const IconGithub = (props: SVGIconProps) => (
  <ImportGithub {...updateIconProps(props)} />
);
export const IconGroup = (props: SVGIconProps) => (
  <ImportGroup {...updateIconProps(props)} />
);
export const IconHeadset = (props: SVGIconProps) => (
  <ImportHeadset {...updateIconProps(props)} />
);
export const IconHeart = (props: SVGIconProps) => (
  <ImportHeart {...updateIconProps(props)} />
);
export const IconHeartFilled = (props: SVGIconProps) => (
  <ImportHeartFilled {...updateIconProps(props)} />
);
export const IconHelpAlt = (props: SVGIconProps) => (
  <ImportHelpAlt {...updateIconProps(props)} />
);
export const IconHideHidden = (props: SVGIconProps) => (
  <ImportHideHidden {...updateIconProps(props)} />
);
export const IconHistory = (props: SVGIconProps) => (
  <ImportHistory {...updateIconProps(props)} />
);
export const IconHome = (props: SVGIconProps) => (
  <ImportHome {...updateIconProps(props)} />
);
export const IconIdle = (props: SVGIconProps) => (
  <ImportIdle {...updateIconProps(props)} />
);
export const IconIgnoreOutliers = (props: SVGIconProps) => (
  <ImportIgnoreOutliers {...updateIconProps(props)} />
);
export const IconImpersonateMaskAlt = (props: SVGIconProps) => (
  <ImportImpersonateMaskAlt {...updateIconProps(props)} />
);
export const IconImportInsert = (props: SVGIconProps) => (
  <ImportImportInsert {...updateIconProps(props)} />
);
export const IconInfo = (props: SVGIconProps) => (
  <ImportInfo {...updateIconProps(props)} />
);
export const IconJobAutomation = (props: SVGIconProps) => (
  <ImportJobAutomation {...updateIconProps(props)} />
);
export const IconJobCalculator = (props: SVGIconProps) => (
  <ImportJobCalculator {...updateIconProps(props)} />
);
export const IconJobProgramCode = (props: SVGIconProps) => (
  <ImportJobProgramCode {...updateIconProps(props)} />
);
export const IconJoyceTransformersLogo = (props: SVGIconProps) => (
  <ImportJoyceTransformersLogo {...updateIconProps(props)} />
);
export const IconJoyceXgboostLogo = (props: SVGIconProps) => (
  <ImportJoyceXgboostLogo {...updateIconProps(props)} />
);
export const IconKerasLogo = (props: SVGIconProps) => (
  <ImportKerasLogo {...updateIconProps(props)} />
);
export const IconKeyAdmin = (props: SVGIconProps) => (
  <ImportKeyAdmin {...updateIconProps(props)} />
);
export const IconKeyAdminPrivate = (props: SVGIconProps) => (
  <ImportKeyAdminPrivate {...updateIconProps(props)} />
);
export const IconKubernetes = (props: SVGIconProps) => (
  <ImportKubernetes {...updateIconProps(props)} />
);
export const IconLanguages = (props: SVGIconProps) => (
  <ImportLanguages {...updateIconProps(props)} />
);
export const IconLaptopLocalComputer = (props: SVGIconProps) => (
  <ImportLaptopLocalComputer {...updateIconProps(props)} />
);
export const IconLayoutGrid = (props: SVGIconProps) => (
  <ImportLayoutGrid {...updateIconProps(props)} />
);
export const IconLayoutHorizontal = (props: SVGIconProps) => (
  <ImportLayoutHorizontal {...updateIconProps(props)} />
);
export const IconLayoutTabs = (props: SVGIconProps) => (
  <ImportLayoutTabs {...updateIconProps(props)} />
);
export const IconLayoutVertical = (props: SVGIconProps) => (
  <ImportLayoutVertical {...updateIconProps(props)} />
);
export const IconLightbulbInfo = (props: SVGIconProps) => (
  <ImportLightbulbInfo {...updateIconProps(props)} />
);
export const IconLinePlotAlt2 = (props: SVGIconProps) => (
  <ImportLinePlotAlt2 {...updateIconProps(props)} />
);
export const IconLinearScale = (props: SVGIconProps) => (
  <ImportLinearScale {...updateIconProps(props)} />
);
export const IconLinkAlt = (props: SVGIconProps) => (
  <ImportLinkAlt {...updateIconProps(props)} />
);
export const IconLinkedinSocial = (props: SVGIconProps) => (
  <ImportLinkedinSocial {...updateIconProps(props)} />
);
export const IconList = (props: SVGIconProps) => (
  <ImportList {...updateIconProps(props)} />
);
export const IconListBullets = (props: SVGIconProps) => (
  <ImportListBullets {...updateIconProps(props)} />
);
export const IconLoading = (props: SVGIconProps) => (
  <ImportLoading {...updateIconProps(props)} />
);
export const IconLockClosed = (props: SVGIconProps) => (
  <ImportLockClosed {...updateIconProps(props)} />
);
export const IconLockOpen = (props: SVGIconProps) => (
  <ImportLockOpen {...updateIconProps(props)} />
);
export const IconLockedConstrained = (props: SVGIconProps) => (
  <ImportLockedConstrained {...updateIconProps(props)} />
);
export const IconLogOut = (props: SVGIconProps) => (
  <ImportLogOut {...updateIconProps(props)} />
);
export const IconLogoColab = (props: SVGIconProps) => (
  <ImportLogoColab {...updateIconProps(props)} />
);
export const IconMagicWandStar = (props: SVGIconProps) => (
  <ImportMagicWandStar {...updateIconProps(props)} />
);
export const IconMagicWandStick = (props: SVGIconProps) => (
  <ImportMagicWandStick {...updateIconProps(props)} />
);
export const IconMenu = (props: SVGIconProps) => (
  <ImportMenu {...updateIconProps(props)} />
);
export const IconMicrophoneAudio = (props: SVGIconProps) => (
  <ImportMicrophoneAudio {...updateIconProps(props)} />
);
export const IconMinimizeMode = (props: SVGIconProps) => (
  <ImportMinimizeMode {...updateIconProps(props)} />
);
export const IconModel = (props: SVGIconProps) => (
  <ImportModel {...updateIconProps(props)} />
);
export const IconModelOnDark = (props: SVGIconProps) => (
  <ImportModelOnDark {...updateIconProps(props)} />
);
export const IconMusicAudio = (props: SVGIconProps) => (
  <ImportMusicAudio {...updateIconProps(props)} />
);
export const IconNumber = (props: SVGIconProps) => (
  <ImportNumber {...updateIconProps(props)} />
);
export const IconOpenNewTab = (props: SVGIconProps) => (
  <ImportOpenNewTab {...updateIconProps(props)} />
);
export const IconOpenaiLogo = (props: SVGIconProps) => (
  <ImportOpenaiLogo {...updateIconProps(props)} />
);
export const IconOrchestrationLaunch = (props: SVGIconProps) => (
  <ImportOrchestrationLaunch {...updateIconProps(props)} />
);
export const IconOrganizationCorporate = (props: SVGIconProps) => (
  <ImportOrganizationCorporate {...updateIconProps(props)} />
);
export const IconOverflowHorizontal = (props: SVGIconProps) => (
  <ImportOverflowHorizontal {...updateIconProps(props)} />
);
export const IconPanTool = (props: SVGIconProps) => (
  <ImportPanTool {...updateIconProps(props)} />
);
export const IconPanTool1 = (props: SVGIconProps) => (
  <ImportPanTool1 {...updateIconProps(props)} />
);
export const IconPanel = (props: SVGIconProps) => (
  <ImportPanel {...updateIconProps(props)} />
);
export const IconPanelAutoGen = (props: SVGIconProps) => (
  <ImportPanelAutoGen {...updateIconProps(props)} />
);
export const IconPanelManual = (props: SVGIconProps) => (
  <ImportPanelManual {...updateIconProps(props)} />
);
export const IconParentBackUp = (props: SVGIconProps) => (
  <ImportParentBackUp {...updateIconProps(props)} />
);
export const IconPause = (props: SVGIconProps) => (
  <ImportPause {...updateIconProps(props)} />
);
export const IconPaused = (props: SVGIconProps) => (
  <ImportPaused {...updateIconProps(props)} />
);
export const IconPencilEdit = (props: SVGIconProps) => (
  <ImportPencilEdit {...updateIconProps(props)} />
);
export const IconPhoto = (props: SVGIconProps) => (
  <ImportPhoto {...updateIconProps(props)} />
);
export const IconPin = (props: SVGIconProps) => (
  <ImportPin {...updateIconProps(props)} />
);
export const IconPlay = (props: SVGIconProps) => (
  <ImportPlay {...updateIconProps(props)} />
);
export const IconPriorityCritical = (props: SVGIconProps) => (
  <ImportPriorityCritical {...updateIconProps(props)} />
);
export const IconPriorityHigh = (props: SVGIconProps) => (
  <ImportPriorityHigh {...updateIconProps(props)} />
);
export const IconPriorityLow = (props: SVGIconProps) => (
  <ImportPriorityLow {...updateIconProps(props)} />
);
export const IconPriorityNone = (props: SVGIconProps) => (
  <ImportPriorityNone {...updateIconProps(props)} />
);
export const IconPrivacyOpen = (props: SVGIconProps) => (
  <ImportPrivacyOpen {...updateIconProps(props)} />
);
export const IconPythonLogo = (props: SVGIconProps) => (
  <ImportPythonLogo {...updateIconProps(props)} />
);
export const IconPytorchLightningLogo = (props: SVGIconProps) => (
  <ImportPytorchLightningLogo {...updateIconProps(props)} />
);
export const IconPytorchLogo = (props: SVGIconProps) => (
  <ImportPytorchLogo {...updateIconProps(props)} />
);
export const IconQueue = (props: SVGIconProps) => (
  <ImportQueue {...updateIconProps(props)} />
);
export const IconQueued = (props: SVGIconProps) => (
  <ImportQueued {...updateIconProps(props)} />
);
export const IconRandomizeAlt = (props: SVGIconProps) => (
  <ImportRandomizeAlt {...updateIconProps(props)} />
);
export const IconRandomizeResetReload = (props: SVGIconProps) => (
  <ImportRandomizeResetReload {...updateIconProps(props)} />
);
export const IconRecentClock = (props: SVGIconProps) => (
  <ImportRecentClock {...updateIconProps(props)} />
);
export const IconRedditSocial = (props: SVGIconProps) => (
  <ImportRedditSocial {...updateIconProps(props)} />
);
export const IconRedo = (props: SVGIconProps) => (
  <ImportRedo {...updateIconProps(props)} />
);
export const IconRegex = (props: SVGIconProps) => (
  <ImportRegex {...updateIconProps(props)} />
);
export const IconRegistries = (props: SVGIconProps) => (
  <ImportRegistries {...updateIconProps(props)} />
);
export const IconRemove = (props: SVGIconProps) => (
  <ImportRemove {...updateIconProps(props)} />
);
export const IconRemoveAlt = (props: SVGIconProps) => (
  <ImportRemoveAlt {...updateIconProps(props)} />
);
export const IconReport = (props: SVGIconProps) => (
  <ImportReport {...updateIconProps(props)} />
);
export const IconRetry = (props: SVGIconProps) => (
  <ImportRetry {...updateIconProps(props)} />
);
export const IconRobotServiceMember = (props: SVGIconProps) => (
  <ImportRobotServiceMember {...updateIconProps(props)} />
);
export const IconRocketLaunch = (props: SVGIconProps) => (
  <ImportRocketLaunch {...updateIconProps(props)} />
);
export const IconRowHeightLarge = (props: SVGIconProps) => (
  <ImportRowHeightLarge {...updateIconProps(props)} />
);
export const IconRowHeightMedium = (props: SVGIconProps) => (
  <ImportRowHeightMedium {...updateIconProps(props)} />
);
export const IconRowHeightSmall = (props: SVGIconProps) => (
  <ImportRowHeightSmall {...updateIconProps(props)} />
);
export const IconRowHeightXlarge = (props: SVGIconProps) => (
  <ImportRowHeightXlarge {...updateIconProps(props)} />
);
export const IconRun = (props: SVGIconProps) => (
  <ImportRun {...updateIconProps(props)} />
);
export const IconRunningRepeat = (props: SVGIconProps) => (
  <ImportRunningRepeat {...updateIconProps(props)} />
);
export const IconSave = (props: SVGIconProps) => (
  <ImportSave {...updateIconProps(props)} />
);
export const IconScikitLogo = (props: SVGIconProps) => (
  <ImportScikitLogo {...updateIconProps(props)} />
);
export const IconSearch = (props: SVGIconProps) => (
  <ImportSearch {...updateIconProps(props)} />
);
export const IconSelectMoveTool = (props: SVGIconProps) => (
  <ImportSelectMoveTool {...updateIconProps(props)} />
);
export const IconSettings = (props: SVGIconProps) => (
  <ImportSettings {...updateIconProps(props)} />
);
export const IconSettingsParameters = (props: SVGIconProps) => (
  <ImportSettingsParameters {...updateIconProps(props)} />
);
export const IconShareExport = (props: SVGIconProps) => (
  <ImportShareExport {...updateIconProps(props)} />
);
export const IconShareWith = (props: SVGIconProps) => (
  <ImportShareWith {...updateIconProps(props)} />
);
export const IconShieldRemove = (props: SVGIconProps) => (
  <ImportShieldRemove {...updateIconProps(props)} />
);
export const IconShowVisible = (props: SVGIconProps) => (
  <ImportShowVisible {...updateIconProps(props)} />
);
export const IconSmoothing = (props: SVGIconProps) => (
  <ImportSmoothing {...updateIconProps(props)} />
);
export const IconSort = (props: SVGIconProps) => (
  <ImportSort {...updateIconProps(props)} />
);
export const IconSortAscending = (props: SVGIconProps) => (
  <ImportSortAscending {...updateIconProps(props)} />
);
export const IconSortDescending = (props: SVGIconProps) => (
  <ImportSortDescending {...updateIconProps(props)} />
);
export const IconSplit = (props: SVGIconProps) => (
  <ImportSplit {...updateIconProps(props)} />
);
export const IconSquare = (props: SVGIconProps) => (
  <ImportSquare {...updateIconProps(props)} />
);
export const IconStar = (props: SVGIconProps) => (
  <ImportStar {...updateIconProps(props)} />
);
export const IconStarFilled = (props: SVGIconProps) => (
  <ImportStarFilled {...updateIconProps(props)} />
);
export const IconStop = (props: SVGIconProps) => (
  <ImportStop {...updateIconProps(props)} />
);
export const IconStopped = (props: SVGIconProps) => (
  <ImportStopped {...updateIconProps(props)} />
);
export const IconSweepBayes = (props: SVGIconProps) => (
  <ImportSweepBayes {...updateIconProps(props)} />
);
export const IconSweepGrid = (props: SVGIconProps) => (
  <ImportSweepGrid {...updateIconProps(props)} />
);
export const IconSweepRandomSearch = (props: SVGIconProps) => (
  <ImportSweepRandomSearch {...updateIconProps(props)} />
);
export const IconSweepsAlt = (props: SVGIconProps) => (
  <ImportSweepsAlt {...updateIconProps(props)} />
);
export const IconSweepsBroom = (props: SVGIconProps) => (
  <ImportSweepsBroom {...updateIconProps(props)} />
);
export const IconSweepsBroomAlt = (props: SVGIconProps) => (
  <ImportSweepsBroomAlt {...updateIconProps(props)} />
);
export const IconSystem = (props: SVGIconProps) => (
  <ImportSystem {...updateIconProps(props)} />
);
export const IconSystemChip = (props: SVGIconProps) => (
  <ImportSystemChip {...updateIconProps(props)} />
);
export const IconSystemChipAlt = (props: SVGIconProps) => (
  <ImportSystemChipAlt {...updateIconProps(props)} />
);
export const IconTable = (props: SVGIconProps) => (
  <ImportTable {...updateIconProps(props)} />
);
export const IconTag = (props: SVGIconProps) => (
  <ImportTag {...updateIconProps(props)} />
);
export const IconTensorflowLogo = (props: SVGIconProps) => (
  <ImportTensorflowLogo {...updateIconProps(props)} />
);
export const IconTextLanguage = (props: SVGIconProps) => (
  <ImportTextLanguage {...updateIconProps(props)} />
);
export const IconTextLanguageAlt = (props: SVGIconProps) => (
  <ImportTextLanguageAlt {...updateIconProps(props)} />
);
export const IconThumbsDown = (props: SVGIconProps) => (
  <ImportThumbsDown {...updateIconProps(props)} />
);
export const IconThumbsUp = (props: SVGIconProps) => (
  <ImportThumbsUp {...updateIconProps(props)} />
);
export const IconTriangleDown = (props: SVGIconProps) => (
  <ImportTriangleDown {...updateIconProps(props)} />
);
export const IconTriangleLeft = (props: SVGIconProps) => (
  <ImportTriangleLeft {...updateIconProps(props)} />
);
export const IconTriangleRight = (props: SVGIconProps) => (
  <ImportTriangleRight {...updateIconProps(props)} />
);
export const IconTriangleUp = (props: SVGIconProps) => (
  <ImportTriangleUp {...updateIconProps(props)} />
);
export const IconTriggerAlt = (props: SVGIconProps) => (
  <ImportTriggerAlt {...updateIconProps(props)} />
);
export const IconTwitter = (props: SVGIconProps) => (
  <ImportTwitter {...updateIconProps(props)} />
);
export const IconTypeBoolean = (props: SVGIconProps) => (
  <ImportTypeBoolean {...updateIconProps(props)} />
);
export const IconTypeNumber = (props: SVGIconProps) => (
  <ImportTypeNumber {...updateIconProps(props)} />
);
export const IconTypeStringQuote = (props: SVGIconProps) => (
  <ImportTypeStringQuote {...updateIconProps(props)} />
);
export const IconUndeterminateVisibility = (props: SVGIconProps) => (
  <ImportUndeterminateVisibility {...updateIconProps(props)} />
);
export const IconUndo = (props: SVGIconProps) => (
  <ImportUndo {...updateIconProps(props)} />
);
export const IconUnlockedUnconstrained = (props: SVGIconProps) => (
  <ImportUnlockedUnconstrained {...updateIconProps(props)} />
);
export const IconUserAuthor = (props: SVGIconProps) => (
  <ImportUserAuthor {...updateIconProps(props)} />
);
export const IconUserProfilePersonal = (props: SVGIconProps) => (
  <ImportUserProfilePersonal {...updateIconProps(props)} />
);
export const IconUsersTeam = (props: SVGIconProps) => (
  <ImportUsersTeam {...updateIconProps(props)} />
);
export const IconVersionsLayers = (props: SVGIconProps) => (
  <ImportVersionsLayers {...updateIconProps(props)} />
);
export const IconVertexGCP = (props: SVGIconProps) => (
  <ImportVertexGCP {...updateIconProps(props)} />
);
export const IconVideoPlay = (props: SVGIconProps) => (
  <ImportVideoPlay {...updateIconProps(props)} />
);
export const IconViewGlasses = (props: SVGIconProps) => (
  <ImportViewGlasses {...updateIconProps(props)} />
);
export const IconWandb = (props: SVGIconProps) => (
  <ImportWandb {...updateIconProps(props)} />
);
export const IconWarning = (props: SVGIconProps) => (
  <ImportWarning {...updateIconProps(props)} />
);
export const IconWarningAlt = (props: SVGIconProps) => (
  <ImportWarningAlt {...updateIconProps(props)} />
);
export const IconWeave = (props: SVGIconProps) => (
  <ImportWeave {...updateIconProps(props)} />
);
export const IconWeaveGroupBoard = (props: SVGIconProps) => (
  <ImportWeaveGroupBoard {...updateIconProps(props)} />
);
export const IconWebhook = (props: SVGIconProps) => (
  <ImportWebhook {...updateIconProps(props)} />
);
export const IconXAxiAlt = (props: SVGIconProps) => (
  <ImportXAxiAlt {...updateIconProps(props)} />
);
export const IconXAxis = (props: SVGIconProps) => (
  <ImportXAxis {...updateIconProps(props)} />
);
export const IconYoutubeSocial = (props: SVGIconProps) => (
  <ImportYoutubeSocial {...updateIconProps(props)} />
);
export const IconZoomInTool = (props: SVGIconProps) => (
  <ImportZoomInTool {...updateIconProps(props)} />
);

const ICON_NAME_TO_ICON: Record<IconName, ElementType> = {
  'add-new': IconAddNew,
  'add-reaction': IconAddReaction,
  'admin-shield-safe': IconAdminShieldSafe,
  'amazon-sagemaker': IconAmazonSagemaker,
  area: IconArea,
  'artifact-type-alt': IconArtifactTypeAlt,
  'audio-volume': IconAudioVolume,
  'automation-robot-arm': IconAutomationRobotArm,
  back: IconBack,
  'bell-notifications': IconBellNotifications,
  'benchmark-square': IconBenchmarkSquare,
  'blog-report': IconBlogReport,
  'book-dictionary': IconBookDictionary,
  boolean: IconBoolean,
  'box-plot': IconBoxPlot,
  bug: IconBug,
  'category-multimodal': IconCategoryMultimodal,
  'chart-horizontal-bars': IconChartHorizontalBars,
  'chart-pie': IconChartPie,
  'chart-scatterplot': IconChartScatterplot,
  'chart-vertical-bars': IconChartVerticalBars,
  checkmark: IconCheckmark,
  'checkmark-circle': IconCheckmarkCircle,
  'chevron-back': IconChevronBack,
  'chevron-down': IconChevronDown,
  'chevron-next': IconChevronNext,
  'chevron-up': IconChevronUp,
  circle: IconCircle,
  'clear-all': IconClearAll,
  close: IconClose,
  cloud: IconCloud,
  'code-alt': IconCodeAlt,
  collapse: IconCollapse,
  color: IconColor,
  column: IconColumn,
  'content-full-width': IconContentFullWidth,
  'content-narrow': IconContentNarrow,
  'content-wide': IconContentWide,
  'contract-left': IconContractLeft,
  copy: IconCopy,
  'credit-card-payment': IconCreditCardPayment,
  'crop-beginning': IconCropBeginning,
  'crop-end': IconCropEnd,
  'crop-middle': IconCropMiddle,
  cross: IconCross,
  'crown-pro': IconCrownPro,
  'cube-container': IconCubeContainer,
  'dashboard-blackboard': IconDashboardBlackboard,
  'database-artifacts': IconDatabaseArtifacts,
  date: IconDate,
  delete: IconDelete,
  diamond: IconDiamond,
  'discord-social': IconDiscordSocial,
  'docker-whale': IconDockerWhale,
  document: IconDocument,
  documentation: IconDocumentation,
  download: IconDownload,
  draft: IconDraft,
  'education-academic': IconEducationAcademic,
  'email-at': IconEmailAt,
  'email-envelope': IconEmailEnvelope,
  'expand-right': IconExpandRight,
  'expand-uncollapse': IconExpandUncollapse,
  'export-share-upload': IconExportShareUpload,
  'facebook-social': IconFacebookSocial,
  failed: IconFailed,
  'filter-alt': IconFilterAlt,
  'flash-bolt': IconFlashBolt,
  'folder-alt': IconFolderAlt,
  'folder-fill': IconFolderFill,
  'folder-project': IconFolderProject,
  'folder-project-move': IconFolderProjectMove,
  'forum-chat-bubble': IconForumChatBubble,
  'forward-next': IconForwardNext,
  'full-screen-mode-expand': IconFullScreenModeExpand,
  'ghost-agent': IconGhostAgent,
  git: IconGit,
  github: IconGithub,
  group: IconGroup,
  headset: IconHeadset,
  heart: IconHeart,
  'heart-filled': IconHeartFilled,
  'help-alt': IconHelpAlt,
  'hide-hidden': IconHideHidden,
  history: IconHistory,
  home: IconHome,
  idle: IconIdle,
  'ignore-outliers': IconIgnoreOutliers,
  'impersonate-mask-alt': IconImpersonateMaskAlt,
  'import-insert': IconImportInsert,
  info: IconInfo,
  'job-automation': IconJobAutomation,
  'job-calculator': IconJobCalculator,
  'job-program-code': IconJobProgramCode,
  'joyce-transformers-logo': IconJoyceTransformersLogo,
  'joyce-xgboost-logo': IconJoyceXgboostLogo,
  'keras-logo': IconKerasLogo,
  'key-admin': IconKeyAdmin,
  'key-admin-private': IconKeyAdminPrivate,
  kubernetes: IconKubernetes,
  languages: IconLanguages,
  'laptop-local-computer': IconLaptopLocalComputer,
  'layout-grid': IconLayoutGrid,
  'layout-horizontal': IconLayoutHorizontal,
  'layout-tabs': IconLayoutTabs,
  'layout-vertical': IconLayoutVertical,
  'lightbulb-info': IconLightbulbInfo,
  'line-plot-alt2': IconLinePlotAlt2,
  'linear-scale': IconLinearScale,
  'link-alt': IconLinkAlt,
  'linkedin-social': IconLinkedinSocial,
  list: IconList,
  'list-bullets': IconListBullets,
  loading: IconLoading,
  'lock-closed': IconLockClosed,
  'lock-open': IconLockOpen,
  'locked-constrained': IconLockedConstrained,
  'log-out': IconLogOut,
  'logo-colab': IconLogoColab,
  'magic-wand-star': IconMagicWandStar,
  'magic-wand-stick': IconMagicWandStick,
  menu: IconMenu,
  'microphone-audio': IconMicrophoneAudio,
  'minimize-mode': IconMinimizeMode,
  model: IconModel,
  'model-on-dark': IconModelOnDark,
  'music-audio': IconMusicAudio,
  number: IconNumber,
  'open-new-tab': IconOpenNewTab,
  'openai-logo': IconOpenaiLogo,
  'orchestration-launch': IconOrchestrationLaunch,
  'organization-corporate': IconOrganizationCorporate,
  'overflow-horizontal': IconOverflowHorizontal,
  'pan-tool': IconPanTool,
  'pan-tool-1': IconPanTool1,
  panel: IconPanel,
  'panel-auto-gen': IconPanelAutoGen,
  'panel-manual': IconPanelManual,
  'parent-back-up': IconParentBackUp,
  pause: IconPause,
  paused: IconPaused,
  'pencil-edit': IconPencilEdit,
  photo: IconPhoto,
  pin: IconPin,
  play: IconPlay,
  'priority-critical': IconPriorityCritical,
  'priority-high': IconPriorityHigh,
  'priority-low': IconPriorityLow,
  'priority-none': IconPriorityNone,
  'privacy-open': IconPrivacyOpen,
  'python-logo': IconPythonLogo,
  'pytorch-lightning-logo': IconPytorchLightningLogo,
  'pytorch-logo': IconPytorchLogo,
  queue: IconQueue,
  queued: IconQueued,
  'randomize-alt': IconRandomizeAlt,
  'randomize-reset-reload': IconRandomizeResetReload,
  'recent-clock': IconRecentClock,
  'reddit-social': IconRedditSocial,
  redo: IconRedo,
  regex: IconRegex,
  registries: IconRegistries,
  remove: IconRemove,
  'remove-alt': IconRemoveAlt,
  report: IconReport,
  retry: IconRetry,
  'robot-service-member': IconRobotServiceMember,
  'rocket-launch': IconRocketLaunch,
  'row-height-large': IconRowHeightLarge,
  'row-height-medium': IconRowHeightMedium,
  'row-height-small': IconRowHeightSmall,
  'row-height-xlarge': IconRowHeightXlarge,
  run: IconRun,
  'running-repeat': IconRunningRepeat,
  save: IconSave,
  'scikit-logo': IconScikitLogo,
  search: IconSearch,
  'select-move-tool': IconSelectMoveTool,
  settings: IconSettings,
  'settings-parameters': IconSettingsParameters,
  'share-export': IconShareExport,
  'share-with': IconShareWith,
  'shield-remove': IconShieldRemove,
  'show-visible': IconShowVisible,
  smoothing: IconSmoothing,
  sort: IconSort,
  'sort-ascending': IconSortAscending,
  'sort-descending': IconSortDescending,
  split: IconSplit,
  square: IconSquare,
  star: IconStar,
  'star-filled': IconStarFilled,
  stop: IconStop,
  stopped: IconStopped,
  'sweep-bayes': IconSweepBayes,
  'sweep-grid': IconSweepGrid,
  'sweep-random-search': IconSweepRandomSearch,
  'sweeps-alt': IconSweepsAlt,
  'sweeps-broom': IconSweepsBroom,
  'sweeps-broom-alt': IconSweepsBroomAlt,
  system: IconSystem,
  'system-chip': IconSystemChip,
  'system-chip-alt': IconSystemChipAlt,
  table: IconTable,
  tag: IconTag,
  'tensorflow-logo': IconTensorflowLogo,
  'text-language': IconTextLanguage,
  'text-language-alt': IconTextLanguageAlt,
  'thumbs-down': IconThumbsDown,
  'thumbs-up': IconThumbsUp,
  'triangle-down': IconTriangleDown,
  'triangle-left': IconTriangleLeft,
  'triangle-right': IconTriangleRight,
  'triangle-up': IconTriangleUp,
  'trigger-alt': IconTriggerAlt,
  twitter: IconTwitter,
  'type-boolean': IconTypeBoolean,
  'type-number': IconTypeNumber,
  'type-string-quote': IconTypeStringQuote,
  'undeterminate-visibility': IconUndeterminateVisibility,
  undo: IconUndo,
  'unlocked-unconstrained': IconUnlockedUnconstrained,
  'user-author': IconUserAuthor,
  'user-profile-personal': IconUserProfilePersonal,
  'users-team': IconUsersTeam,
  'versions-layers': IconVersionsLayers,
  'vertex-gcp': IconVertexGCP,
  'video-play': IconVideoPlay,
  'view-glasses': IconViewGlasses,
  wandb: IconWandb,
  warning: IconWarning,
  'warning-alt': IconWarningAlt,
  weave: IconWeave,
  'weave-group-board': IconWeaveGroupBoard,
  webhook: IconWebhook,
  'x-axi-alt': IconXAxiAlt,
  'x-axis': IconXAxis,
  'youtube-social': IconYoutubeSocial,
  'zoom-in-tool': IconZoomInTool,
};

export interface IconProps {
  name: IconName;
  [x: string]: any;
}

export const Icon = ({name, ...props}: IconProps) => {
  const IconComponent: ElementType = ICON_NAME_TO_ICON[name];
  if (!IconComponent) {
    throw new Error(`Could not find icon ${name}`);
  }
  return <IconComponent {...props} />;
};
