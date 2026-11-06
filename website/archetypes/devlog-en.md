+++
title = "Development journal title"
description = "Summarize the change in one or two sentences."
date = {{ time.Format "2006-01-02" .Date }}
publishDate = {{ time.Format "2006-01-02" .Date }}
lastmod = {{ time.Format "2006-01-02" .Date }}
draft = true
[params]
work_start = "{{ time.Format "2006-01-02" .Date }}"
source_ref = ""
sources = []
+++

## Background

Explain the problem being addressed.

## Changes

Describe the resulting behavior and what changed.

## Verification and remaining work

Record checks, experiment conditions and results, and unresolved points.
Do not present an unmeasured effect as a result.

## References

Link supporting commits and documents at pinned revisions.
