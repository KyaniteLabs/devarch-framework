# AG4TE for Hermes

![AG4TE](../../branding/ag4te-lockup-dark.png)

You know a repository's code, but not the story of how it got that way: when the work happened, what kind of work it was, who did it, and where it went quiet. AG4TE digs a local git repository's history with DevArch and draws that story as strata in Hermes Desktop.

A dig gives you:

- commits per day, split by kind of work (features, fixes, docs, tests, chores and the rest)
- eras, quiet gaps and notable signals
- weekly rhythm and practice health
- authors merged across name spellings and split into people, agents and bots

Digs run on your machine. They read only the repository you choose, keep their results under `plugin-data/ag4te`, and never call an LLM. The only network access is `uvx` fetching the pinned DevArch release from GitHub the first time.

## What you get

- **Desktop:** an AG4TE page. Pick a repository under your `repo_roots`, start a dig, watch its steps, and read the strata chart (Days or Weeks), eras, gaps, signals, rhythm and authors. A running dig can be stopped and resumed.
- **Slash command:** `/ag4te list | show <project> | status <project> | dig <repo-path> [project] | stop <project> | resume <project>`. On Telegram, Discord and other chat platforms, `dig` and `resume` are off unless you set `allow_dig_on_gateway: true`, because they read local files.
- **Agent tool:** `ag4te_dig` gives agents a read-only summary of a finished dig, or lists the digs.

## Install

AG4TE lives in the `plugins/ag4te-hermes` folder of [KyaniteLabs/ag4te](https://github.com/KyaniteLabs/ag4te). Link it into your Hermes plugins folder and enable it:

```
git clone https://github.com/KyaniteLabs/ag4te.git
ln -s "$PWD/ag4te/plugins/ag4te-hermes" "${HERMES_HOME:-$HOME/.hermes}/plugins/ag4te"
hermes plugins enable ag4te
```

You also need [`uv`](https://docs.astral.sh/uv/) on the gateway host, because AG4TE runs DevArch with `uvx`. Requires Hermes `>= 0.21.6`. If Hermes Desktop connects to a remote gateway, install AG4TE on the gateway host. Desktop loads the page from there.

## Settings

Set these in Desktop (**Settings → Plugins → AG4TE**) or with `hermes config set plugins.entries.ag4te.settings.<name> <value>`.

| Setting | Default | What it does |
|---|---|---|
| `repo_roots` | `~/workspaces` | Folders (comma separated) that repositories must sit under. |
| `time_zone` | host zone | IANA zone for bucketing days and hours, e.g. `America/Los_Angeles`. |
| `history` | `head` | `head` reads the current branch; `all` reads every branch and tag. |
| `bots` | none | Extra bot or service accounts, names or emails, `*` wildcards allowed. |
| `timeout_seconds` | `600` | Time limit for each DevArch step. |
| `data_dir` | `<HERMES_HOME>/plugin-data/ag4te` | Where digs are stored. |
| `devarch_command` | pinned `uvx` install | Override how DevArch is run, for example a local checkout. |
| `allow_dig_on_gateway` | `false` | Allow `/ag4te dig` and `resume` from chat platforms. |

## What the numbers mean

Kinds of work come from commit messages and changed paths. They are keyword heuristics, not a reading of the code. Signals and eras are leads to investigate, not conclusions. Commit counts are not a productivity measure. See [docs/DATA-MODEL-ROAST.md](docs/DATA-MODEL-ROAST.md) for how the data model was reviewed and fixed.

## License

Apache-2.0. See [LICENSE](LICENSE).
