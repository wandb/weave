/**
 * Select a grid column.
 */
import {Select} from '@wandb/weave/components/Form/Select';
// import {IconShareWith} from '@wandb/weave/components/Icon';
// import _ from 'lodash';
import React from 'react';

// // eslint-disable-next-line wandb/no-deprecated-imports
// import {Loader} from 'semantic-ui-react';

// import {useAccountTeamsList} from '../../..//pages/HomePage/HomePageSidebar/useAccountTeamsList';
// import {AccountSelectorContext} from '../../../components/Search/SearchNav/AccountSelectorContextProvider';
// import {useUserEntitiesQuery} from '../../../generated/graphql';
// import {useViewer} from '../../../state/viewer/hooks';
// import {useRampFlagAccountSelector} from '../../../util/rampFeatureFlags';
// import {AccountType} from '../../Search/SearchNav/types';
// import {WANDB_ENTITY_NAME} from '../utils';
// import * as S from './SelectEntity.styles';

type FieldOption = {
  value: string;
  label: string;
  //   type: 'user' | 'team' | 'all';
  //   image: string | null;
  //   isAdmin: boolean;
  isDisabled?: boolean;
};

type GroupedOption = {
  readonly label: string;
  readonly options: FieldOption[];
};

export type SelectFieldOption = FieldOption | GroupedOption;

type SelectFieldProps = {
  options: SelectFieldOption[];

  //   size?: SelectSize;
  //   includeAll?: boolean;
  //   includePersonalEntity?: boolean;
  //   // If true, show the role of the entity in the label.
  //   showRole?: boolean;
  //   // If true, disable entities the viewer is not an admin for.
  //   entityAdminOnly?: boolean;
  //   value: string;
  //   onSelectEntity: (name: string) => void;
};

// const OPTION_ALL: EntityOption = {
//   type: 'all',
//   value: '',
//   label: 'All teams',
//   isAdmin: false,
//   image: null,
// };

export const SelectField = ({
  options,
}: //   size = 'medium',
//   includeAll,
//   includePersonalEntity,
//   showRole,
//   entityAdminOnly,
//   value,
//   onSelectEntity,
SelectFieldProps) => {
  console.log({options});
  //   const cols = columnInfo.cols.filter(c => c.filterable ?? true);
  //   const grouped: Record<string, FieldOption[]> = {
  //     Other: [],
  //   };
  //   for (const group of columnInfo.colGroupingModel) {
  //     grouped[group.groupId] = [];
  //   }
  //   console.log('SelectField');
  //   console.log({columnInfo, cols, grouped});

  //   const viewer = useViewer();
  //   const queryEntities = useUserEntitiesQuery();
  //   const enableAccountSelector = useRampFlagAccountSelector();
  //   const {selectedAccount} = useContext(AccountSelectorContext);
  //   const {
  //     accountTeams: organizationEntities,
  //     loading: isOrganizationEntitiesLoading,
  //     error: organizationEntitiesError,
  //   } = useAccountTeamsList();

  //   const loading = enableAccountSelector
  //     ? isOrganizationEntitiesLoading
  //     : queryEntities.loading;
  //   const error = enableAccountSelector
  //     ? organizationEntitiesError
  //     : queryEntities.error;

  //   const teams =
  //     (enableAccountSelector
  //       ? organizationEntities?.edges?.map(edge => edge.node) ?? []
  //       : queryEntities?.data?.viewer?.teams?.edges.map(edge => edge.node)) ?? [];

  //   includePersonalEntity = enableAccountSelector
  //     ? selectedAccount?.accountType === AccountType.Personal
  //     : includePersonalEntity ?? true;

  //   if (loading) {
  //     return <Loader active inline size="tiny" />;
  //   }
  //   if (error) {
  //     return <Alert severity="error">Could not load entities</Alert>;
  //   }

  //   const username = viewer?.username ?? '';

  //   const options: EntityOption[] = includeAll ? [OPTION_ALL] : [];

  //   for (const team of teams) {
  //     if (!team || team.name === username) {
  //       continue;
  //     }
  //     const isTeamAdmin = team?.members.some(
  //       m => m.username === username && m.role === 'admin'
  //     );
  //     const option: EntityOption = {
  //       type: 'team',
  //       value: team.name,
  //       label: team.name,
  //       image: team.photoUrl ?? null,
  //       isAdmin: isTeamAdmin,
  //     };
  //     if (entityAdminOnly && !isTeamAdmin) {
  //       option.isDisabled = true;
  //     }
  //     options.push(option);
  //   }
  //   if (includePersonalEntity) {
  //     options.push({
  //       type: 'user',
  //       value: username,
  //       label: username,
  //       image: viewer?.photoUrl ?? null,
  //       isAdmin: true,
  //     });
  //   }

  //   const selected = _.find(options, o => o.value === value && !o.isDisabled);
  //   const onChange = (option: EntityOption | null) => {
  //     if (option) {
  //       onSelectEntity(option.value);
  //     }
  //   };

  //   const formatOptionLabel = ({
  //     type,
  //     label,
  //     image,
  //     isAdmin,
  //     isDisabled,
  //   }: EntityOption) => (
  //     <S.EntityOption>
  //       <span
  //         data-test="entity-select-option"
  //         style={{opacity: isDisabled ? 0.3 : 'inherit'}}>
  //         {type === 'all' ? null : image ? (
  //           <S.AvatarImage size={size} src={image} />
  //         ) : (
  //           <S.AvatarImage size={size}>
  //             <IconShareWith />
  //           </S.AvatarImage>
  //         )}
  //       </span>
  //       {label}
  //       {showRole && type === 'team' && (isAdmin ? ' (admin)' : ' (member)')}
  //       {showRole && type === 'user' && ' (personal)'}
  //     </S.EntityOption>
  //   );
  const onReactSelectChange = (option: FieldOption | null) => {
    console.log('onReactSelectChange');
    console.log({option});
  };

  return (
    <Select<FieldOption>
      //   size={size}
      options={options}
      placeholder="Select column"
      //   value={selected}
      //   formatOptionLabel={formatOptionLabel}
      //   onChange={onChange}
      isOptionDisabled={option => !!option.isDisabled}
      onChange={onReactSelectChange}
    />
  );
};
