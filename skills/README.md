# Rhino MCP Skills

Prompt packages that teach an AI client *how* to use the Rhino MCP tools for a
specific workflow. Each folder holds a `SKILL.md` in the
[Agent Skills](https://agentskills.io) format, which Claude Code, Codex CLI, and
ChatGPT (via Skill Creator) all read. Longer reference tables sit beside the
skill as plain Markdown.

Every skill was written against the tool source in `src/rhmcp/tools/`, not the
README, so parameter names, return keys, and the `applied` / `not_applied`
caveats reflect what the code does.

| Skill | Use it for |
|---|---|
| [rhino-mcp-basics](rhino-mcp-basics/SKILL.md) | Conventions every other skill assumes: response shapes, units, defaults, undo, scripting |
| [text-to-3d](text-to-3d/SKILL.md) | Build a model from a written brief. Includes the full geometry type table |
| [image-to-3d](image-to-3d/SKILL.md) | Trace a plan or PDF to scale, or generate a mesh from a photo |
| [document-reading](document-reading/SKILL.md) | PDFs, drawings, spreadsheets, SVG, Word, images |
| [grasshopper-parametric](grasshopper-parametric/SKILL.md) | GH1 and GH2 definitions, script components, third-party plugin helpers |
| [landscape-site-plan](landscape-site-plan/SKILL.md) | Terrain, paths, water, planting, schedules |
| [urban-massing-studio](urban-massing-studio/SKILL.md) | Massing typologies, FAR, solar, AI renders, PDF reports |
| [rendering-and-export](rendering-and-export/SKILL.md) | Materials, HDRI, views, image capture, file export |

## Install

**Claude Code**
```bash
cp -r skills/* ~/.claude/skills/
```

**Codex CLI**
```bash
cp -r skills/* ~/.codex/skills/
```

**ChatGPT Desktop**
Open Skill Creator, paste the contents of a `SKILL.md`, and name the skill after
its folder. Paste the sibling `.md` reference files as additional knowledge.

## Write your own

Copy a folder, change `name` and `description` in the frontmatter, and list the
tools and steps. Keep `SKILL.md` under about 80 lines and move tables into a
sibling file. Check tool names against the README tool table before committing:

```bash
uv run python scripts/check_skill_tools.py
```
