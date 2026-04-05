---
name: Workspace Regression Triage
description: Workspace-focused skill for inspecting files, running bounded regression checks, and continuing from the same filesystem artifact surface.
version: 1.0.0
skill_id: workspace-regression-triage
kind: executable
triggers:
  - pytest
  - regression
  - workspace
  - failing test
required_surfaces:
  - filesystem
  - sandbox
allowed_tools:
  - inspect_workspace_path
  - execute_workspace_command
sandbox_profiles:
  - workspace_write
source: local_authored
trust_tier: authored
---

## Use

- Prefer this skill when the task is to inspect a workspace artifact, run a bounded regression command, or continue from a recent run log or produced file.
- Reuse the current workspace root instead of inventing a new work surface.
- When execution is needed, stay inside the approved workspace boundary and use the existing restricted execution profile.

## Constraints

- Do not request permissions beyond the already defined workspace-local sandbox policy.
- Do not assume arbitrary host execution, browser runtime, package install, or new shell access.
