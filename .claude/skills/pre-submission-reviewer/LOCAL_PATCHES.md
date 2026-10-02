# Local patches to the vendored skill

`INSTALLED_FROM` records upstream v2.5 (academic-practice-agents 211bcc1). This copy differs from it in:

- `SKILL.md`, report template: the header says 10 subagents (was 9), and SECTION-BY-SECTION has an `[S-PR]` line.
  v2.5 added S-PR but did not update these two places (Copilot review of PR #36). The same fix is due upstream in
  `pre-submission-agent/skills/pre-submission-reviewer/SKILL.md`.
- `profiles/denolle-rainier3d.md`: added for this repository; not upstream.
