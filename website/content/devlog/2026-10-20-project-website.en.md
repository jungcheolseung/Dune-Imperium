+++
title = "Publishing the project website"
description = "Collect project information, installation/play guides, and engine/AI articles using Hugo and GitHub Pages."
date = 2026-10-20
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-20"
retrospective = true
source_ref = "b7787979"
sources = ["website/README.md", ".github/workflows/website.yml"]
+++
## An entry point for documentation

A project website was added alongside development documentation: introduction, downloads/installation, guides, engine and AI articles, and updates. Its source lives in `website/` and builds with Hugo.

Responsive menus, contents, categories, search, and RSS were added. Building the site needs neither game dependencies nor private images/models.

## GitHub Pages

Site-related pushes to `master` run build, link, and browser checks before deploying to Pages. After the initial merge, deployment and responses for the home page, guides, search data, and RSS were checked. A PR is an optional review path; deployment starts when changes reach `master`.

Publishing the website is separate from distributing game installers or models. Downloads describe only what is available.

## Continuing the journal

Promotional home-page copy was replaced with a direct project description. Earlier commits and documents were grouped into dated journal entries. Later implementation and experiments will continue in the same format.

## References

- [Build the project website with navigation and search](https://github.com/jungcheolseung/Dune-Imperium/commit/7c2cac41)
- [Prepare website checks and GitHub Pages deployment](https://github.com/jungcheolseung/Dune-Imperium/commit/40322e7b)
- [Merge pull request #2 from jungcheolseung/docs/project-site-plan](https://github.com/jungcheolseung/Dune-Imperium/commit/b7787979)
