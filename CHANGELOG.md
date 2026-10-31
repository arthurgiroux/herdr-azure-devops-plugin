# Changelog

## 0.2.0
- Plugin id is now `arthurgiroux.ado-builds`. Move your config and PAT files to the new `herdr plugin config-dir`.
- Install-time check for Python 3.11 or later.
- Clear errors for a missing `az` or `git`, invalid config, non-JSON or unexpected HTTP responses, detached HEAD and non-Azure DevOps remotes.
- Remote selection: configured `remote`, then the upstream remote, then `origin`, then the first Azure DevOps remote.
- Branch follows the upstream branch name when it differs from the local one.
- PAT also read from `AZURE_DEVOPS_EXT_PAT`.
- New config keys `notify` (`all`, `failures`, `off`) and `remote`; `poll_seconds` and `top_builds` are clamped.
- The pane exits cleanly without a tty or on EOF.

## 0.1.0
- Initial release: live build table and finish toasts.
