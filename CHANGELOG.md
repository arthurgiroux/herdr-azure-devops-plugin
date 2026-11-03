# Changelog

## 0.3.0
- Press `a` in the pane to list all builds of the project instead of only the current branch.
- Demo mode (`AZURE_DEVOPS_DEMO=1`) with dummy data for screenshots.

## 0.2.0
- Renamed from "ADO builds" to "Azure DevOps", since the plugin will cover more than builds. Plugin id is now `arthurgiroux.azure-devops` (was `arthurgiroux.ado-builds`) and the action is `arthurgiroux.azure-devops.builds` (was `...open`); move your config and PAT files to the new `herdr plugin config-dir` and update any key binding.
- `pat_cmd` now receives the organization as `$AZURE_DEVOPS_ORG` (was `$ADO_ORG`); update any existing `pat_cmd`.
- Install-time check for Python 3.11 or later.
- Clear errors for a missing `az` or `git`, invalid config, non-JSON or unexpected HTTP responses, detached HEAD and non-Azure DevOps remotes.
- Remote selection: configured `remote`, then the upstream remote, then `origin`, then the first Azure DevOps remote.
- Branch follows the upstream branch name when it differs from the local one.
- PAT also read from a user-configured `pat_cmd` (macOS Keychain, libsecret, `pass`, ...) and from `AZURE_DEVOPS_EXT_PAT`.
- New config keys `notify` (`all`, `failures`, `off`) and `remote`; `poll_seconds` and `top_builds` are clamped.
- The pane exits cleanly without a tty or on EOF.

## 0.1.0
- Initial release: live build table and finish toasts.
