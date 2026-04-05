# Local Skills

Authored local runtime skills live here.

Each skill should use:

```text
skills/
└── <skill_id>/
    ├── SKILL.md
    ├── assets/
    ├── templates/
    ├── scripts/
    └── tests/
```

`SKILL.md` is the canonical entrypoint.
Keep install/runtime truth out of the package body; registry and lock metadata belong under the managed runtime data dir.
