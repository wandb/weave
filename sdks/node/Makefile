install-pnpm:
	curl -fsSL https://get.pnpm.io/install.sh | sh -

bootstrap: install-pnpm
	pnpm env use --global 20
	pnpm install
	pnpm run generate-api
