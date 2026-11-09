# P16/U7 installed-wheel replay

Status: **pass**

This is the published P16/U7 contract from PR #93, replayed on an installed wheel.
The retained Product QA database is not in this repository. The fixture is 89
rows for `demo-archaeology`, one author (`Claude 3.7` → Claude), and mixed
ISO-8601 `Z` / offset dates plus legacy Git-log dates from 2026-04-29 to 2026-11-03.

- git HEAD at runtime: `dec18b36bad26470e4fb1580627678a71812d805`
- That SHA is the tree that was wheeled. A later commit that only adds this receipt does not change the analyzer.
- wheel: `devarch_framework-0.4.1-py3-none-any.whl`
- installed archaeology: `/tmp/devarch-p16-nb9jubkx/venv/lib/python3.12/site-packages/archaeology/__init__.py`
- analyzer total_commits: 89
- sum of agent commits: 89
- agents: ['Claude']
- date_range: 2026-04-29 to 2026-11-03
- benchmark stdout: Analyzing agent performance for 'demo-archaeology'...
Benchmark visualization generated at projects/demo-archaeology/deliverables/visuals/agent-benchmark.html
- elapsed_seconds: 6.496

## Installed versions

```
Name: devarch-framework
Version: 0.4.1
Summary: Forensic archaeology framework for git repositories
Home-page: https://github.com/KyaniteLabs/devarch-framework
Author: Simon Gonzalez De Cruz
Author-email: simon@puenteworks.com
License: Apache-2.0
Location: /tmp/devarch-p16-nb9jubkx/venv/lib/python3.12/site-packages
Requires: click, datasette, sqlite-utils
Required-by: 
---
Name: click
Version: 8.5.1
Summary: Composable command line interface toolkit
Home-page: 
Author: 
Author-email: 
License: 
Location: /tmp/devarch-p16-nb9jubkx/venv/lib/python3.12/site-packages
Requires: 
Required-by: click-default-group, datasette, devarch-framework, sqlite-utils, uvicorn
---
Name: sqlite-utils
Version: 4.2.1
Summary: CLI tool and Python library for manipulating SQLite databases
Home-page: 
Author: Simon Willison
Author-email: 
License: 
Location: /tmp/devarch-p16-nb9jubkx/venv/lib/python3.12/site-packages
Requires: click, click-default-group, pip, pluggy, python-dateutil, sqlite-fts4, tabulate
Required-by: devarch-framework
```

Catalog publication is still Simon's step. This receipt does not submit anything.
