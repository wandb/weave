# @wandb/weave/common/assets

## Fonts

Onprem needs to work airgapped so we host the google fonts ourselves.

### Adding a new font

1. Go to https://gwfh.mranftl.com (previously was https://google-webfonts-helper.herokuapp.com)
2. Search for the font that you want to add.
3. Select the charsets - latin should be sufficient for the time being.
4. Select the styles you want to add. See the table below for some guidance.
5. Select the "Modern Browsers" option.
6. Customize the folder prefix - "../../assets/fonts"
7. Download the files and copy them into the `src/assets/fonts` folder.
8. Copy the css into the `.css` file.
9. Add in the font name for `local()` using the suffix from the table for guidance. (e.g. `src: local('Source Code Pro SemiBold Italic'), local('SourceCodePro-SemiBoldItalic')`)

### Styles and local font names

| Style         | Local Font Name Suffix              |
| ------------- | ----------------------------------- |
| 200           | ExtraLight                          |
| 300           | Light                               |
| regular (400) | Regular                             |
| 600           | SemiBold                            |
| 700           | Bold                                |
| 200italic     | ExtraLight Italic, ExtraLightItalic |
| 300italic     | Light Italic, LightItalic           |
| italic        | Italic                              |
| 700italic     | Bold Italic, BoldItalic             |
