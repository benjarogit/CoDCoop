# AGENTS.md — CoDCoop

## Documentation languages

Use English as the default repository language. Keep player instructions for
installation, configuration, and play equivalent in English and German. Update
both language versions when changing a player workflow. Keep the changelog and
release notes bilingual.

## Disk space and QA cleanup

`run/` holds disposable QA work and is listed in `.gitignore`. QA runs can
create complete game copies under `run/<tag>/host/`, `join1/`, `join2/`,
`prefix/`, and `runtime/`, taking about 15 GB per run. In a previous incident,
266 runs took about 596 GB and left only 15 GB free on `/mnt/intern-1tb`.

### Before each QA run

```bash
df -h /mnt/intern-1tb           # Clean up before starting if less than 60 GB is free
home-cleanup --cod-status       # Count QA runs and show the largest ones
```

### After each QA run, in the same session

1. Copy `result.json`, `provenance.json`, `*.log`, `tree-watch.json`,
   and `*-proof.json` to `run/<tag>/evidence/`.
2. Remove the temporary copies in `run/<tag>/{host,join1,join2,join3,prefix,runtime}`.
3. Run `home-cleanup --cod-runs` for runs that are no longer needed. Follow the
   protections below.

Treat a run older than 12 hours with no reference in `docs/` as disposable,
subject to the cleanup protections.

### Run names

Use `run/<family><n>`, such as `qa-noville-m1-union1` through
`qa-noville-m1-union7`. The cleanup tool uses the numeric suffix to group runs
and keeps the newest N members of each family. Avoid names such as
`switch-protocol9-bundled-final-final`.

### Cleanup commands

```bash
home-cleanup --cod-status
home-cleanup --cod-runs --dry-run          # Preview what would be deleted
home-cleanup --cod-runs                    # Remove superseded QA runs
home-cleanup --cod-runs --keep 2 --max-age-d 7
```

The cleanup tool protects runs referenced as `run/<name>` in `docs/`, `notes/`,
`README*.md`, or `CHANGELOG.md`. It also protects runs younger than
`--min-age-h` (12 hours by default) and stops if a process is using a run.

| Free space on `/mnt/intern-1tb` | Required action |
| --- | --- |
| More than 100 GB | Normal QA operation |
| 60–100 GB | Run `home-cleanup --cod-runs` before starting the next QA run |
| Under 60 GB | Clean up before starting any new QA run |
| Under 20 GB | Emergency cleanup of old run families with `--keep 1 --max-age-d 3` |

### Protected files

- Keep `run/<tag>/evidence/` and runs referenced in the documentation.
- Ask before removing anything from `game/` or `build/`.
- Leave `run/` in place while a Wine, Xvfb, or QA process is running.

### Reporting

Every final QA report includes the free space from `df -h /mnt/intern-1tb`
and confirms whether the test run was cleaned up.
