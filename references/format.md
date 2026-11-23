# Format: links, markers, files

`check_spec.py` reads exactly these forms.

## Evidence links

A Markdown link to the source, from the repository root, with a line anchor:

```markdown
- 订单 30 分钟未支付自动取消 [order_jobs.py:41-58](/backend/app/jobs/order_jobs.py#L41-L58 "if order.created_at < cutoff")
```

- Path starts with `/` (repository root; GitHub renders it as a link on the
  current branch). Relative paths also work.
- `#L41` or `#L41-L58`: the narrowest range that shows the point. No anchor
  means the file as a whole; use that rarely, because any change to the file
  marks the fact as affected.
- The optional title in quotes is a snippet copied from those lines. The check
  confirms it occurs there (whitespace ignored). Put one on facts that matter
  most; it also catches a range that drifted onto other code. Write a `"`
  inside it as `\"`.
- Link text: `file.py:41-58`, short.

## Certainty

| Marker | Meaning |
|---|---|
| (none) | The cited lines show it directly. |
| 〔推断〕 | A reasonable reading the cited lines do not prove alone. Still cite what it rests on. |
| 〔未知〕 | Looked for and not found. No link needed. |

English specs may use `[inferred]` and `[unknown]`.

## Where links are required

In sections `overview`, `entities`, `relations`, `lifecycles`, `decisions`,
`flows`, `pages`, `gaps`, every list item and table row needs a link or
〔未知〕. A nested list item is covered by a cited parent. A table is covered by
a link in the line directly above it (for example "来源：[order.py:12-40](...)")
when all rows come from that range.

A statement that something does not exist ("没有代码进入的状态：无。") is
written as a plain sentence, not a list item: there is nothing to cite, and
the claim rests on the inventory being complete.

## Section markers

Each section heading is followed by a marker; the check uses markers, not
heading text, so headings can be in any language:

```markdown
## 实体
<!-- spec:section entities -->
```

Required ids, in order: `readers`, `overview`, `entities`, `relations`,
`lifecycles`, `decisions`, `flows`, `pages`, `gaps`, `proposals`,
`open-questions`.

Inside a section, give each entity, state machine and page a heading so other
sections can link to it (`[订单](#订单)`).

## Prototype markers

```markdown
<!-- spec:prototype id=order-refund status=pending -->
```

`id`: lowercase, hyphens; the SVG is `prototypes/<id>.svg`. `status`:
`pending` until a person confirms the ASCII draft, then `confirmed`. The check
fails on an SVG for a pending draft and warns on a confirmed draft with no SVG.

## Diagrams

Source `diagrams/<section>-<name>.puml`, rendered `diagrams/<section>-<name>.svg`,
embedded with a link to the source:

```markdown
![订单状态](diagrams/lifecycle-order.svg) · [源文件](diagrams/lifecycle-order.puml)
```

## changes.md

Newest first. One entry per update:

```markdown
## 2026-11-24 · #812 支持部分退款
- 生命周期 › 订单：新增 `partially_refunded` 状态及进入、离开条件
- 业务决定：退款上限改为实付金额（原为订单金额）
```

Each line names the section and what changed for the reader, not which files
changed.
