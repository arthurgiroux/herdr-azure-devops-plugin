# herdr Azure DevOps builds

A herdr plugin that shows live Azure DevOps builds for the repo and branch of the current workspace, and raises a herdr toast when a build finishes. Works with Azure DevOps Services (`dev.azure.com` and `*.visualstudio.com`).

## Requirements
- herdr 0.9.3 or later
- Python 3.11 or later
- Azure CLI logged in (`az login`), or a personal access token (see Auth)
- git

## Install
```sh
herdr plugin install arthurgiroux/herdr-ado-plugin
```
For development, link a local checkout instead:
```sh
herdr plugin link "$PWD"
```

## Use
Run the action from a workspace pane on an Azure DevOps repo:
```sh
herdr plugin action invoke arthurgiroux.ado-builds.open
```
Or bind a key in herdr `config.toml`:
```toml
[[keys.command]]
key = "prefix+shift+b"
type = "plugin_action"
command = "arthurgiroux.ado-builds.open"
description = "ADO builds"
```
In the pane: `r` refreshes, `q` quits.

## Config
Optional `config.toml` in `herdr plugin config-dir arthurgiroux.ado-builds`:
```toml
poll_seconds = 15      # refresh interval, minimum 5
top_builds = 15        # builds shown, 1 to 100
notify = "all"         # "all", "failures" or "off"
remote = "origin"      # git remote to use; default: upstream remote, then origin, then first Azure DevOps remote
```
An invalid file is reported in the pane.

## Auth
Default: Azure CLI token (`az login`). If your tenant has no Azure DevOps service principal (AADSTS500011), or you prefer not to use the CLI, use a PAT with scopes `Build (Read)` and `Code (Read)`.

Write the token to a file in the config dir (paste it, then press Ctrl-D):
```sh
dir="$(herdr plugin config-dir arthurgiroux.ado-builds)"
mkdir -p "$dir"
(umask 077; cat > "$dir/pat")
```
### macOS Keychain
On macOS you can keep the PAT in the Keychain instead of a file. Using `-w` with no value makes `security` prompt for the token, so it stays out of shell history:
```sh
security add-generic-password -U -s herdr-ado-builds -a my-org -w
```
The account is the organization name; use the account `default` for a token that applies to every organization.

### Precedence
`pat.<org>` file, Keychain item for the org, Keychain item `default`, `pat` file, then `AZURE_DEVOPS_EXT_PAT`. If none is found the Azure CLI token is used.

`pat` applies to every organization. For a different PAT per organization, name the file `pat.<org>`, for example `pat.my-org`; it overrides `pat`. 

## Troubleshooting
- `AADSTS500011`: your tenant lacks the Azure DevOps service principal; use a PAT.
- `Access denied` / 401: the PAT is invalid or expired, or run `az login` again.
- Permission denied / 403: the account or PAT lacks Build (Read) or Code (Read).
- `Detached HEAD`: check out a branch in the workspace pane.
- `No Azure DevOps remote found`: the repo has no `dev.azure.com` or `visualstudio.com` remote; set `remote` if you have several.
- Python version errors: install Python 3.11 or later and make sure `python3` points to it.

Errors from the `open` action appear in `herdr plugin log`.

## Test
```sh
python3 -m unittest discover tests
```

## Publishing
herdr lists public GitHub repos that have the topic `herdr-plugin` and a valid `herdr-plugin.toml` on the default branch.

## License
MIT
