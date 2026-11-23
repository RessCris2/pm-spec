# spec.md template

Each section: the reader question it answers, what goes in, what stays out.
Keep the order; drop the guidance text. A section with nothing to say gets one
line saying so ("系统没有定时任务。"), not padding.

Which section owns which fact (say it there, link to it elsewhere):

| Fact | Owner |
|---|---|
| A field, its type, constraint or default | Entities |
| Cardinality, ownership, what a delete does | Relations |
| A state, a transition, its trigger, guard and side effect | Lifecycles |
| A rule, limit, permission, calculation, flag | Decisions |
| The order of calls across modules for one operation | Flows |
| What a page shows and lets the user do | Pages |

---

```markdown
# <系统名> 功能规格（现状）

> 依据 commit `<short sha>` 的代码整理，<date>。每条事实链接到证明它的源码；
> 〔推断〕是合理解读但代码未直接证明，〔未知〕是代码中找不到。更新记录见 [changes.md](changes.md)。

## 读者
<!-- spec:section readers -->
```

**Readers.** One row per reader: who, what they need from this document,
which sections answer it. Default readers: product manager taking over,
designer, tester, engineer new to the project. Add one line on scope: which
part of the codebase this covers and what is deliberately left out.

```markdown
## 概述
<!-- spec:section overview -->
```

**Overview** - "What is this system and who uses it?" Three to five sentences.
Then the user roles, each with a link to where the role is defined or
checked. Roles come from the auth/permission code, not from guesses.

```markdown
## 实体
<!-- spec:section entities -->
```

**Entities** - "What does the system keep track of?" One heading per entity.
Under it: one sentence on what it represents, then a table of only the fields
a reader needs (business meaning, constraints, defaults, enums), with a
source link above the table. Skip ids, timestamps and fields whose name says
everything. List skipped internal tables in one line at the end.

```markdown
## 实体关系
<!-- spec:section relations -->
```

**Relations** - "How do these things connect, and what happens on delete?"
An ER diagram (PlantUML), then only the relations a diagram cannot show:
ownership, cascade or restrict on delete, uniqueness across relations.

```markdown
## 生命周期
<!-- spec:section lifecycles -->
```

**Lifecycles** - "What states can X be in, and what moves it?" One heading per
stateful entity: a state diagram, then a table: from → to, trigger (endpoint,
job or user action), guard, side effects (notifications, payments, records
written). Then states no code enters, and states nothing leaves except
deletion: a list with links, or one plain sentence saying there are none. When there is no status field, derive states
from timestamps, soft-delete or flags and mark them 〔推断〕.

```markdown
## 业务决定
<!-- spec:section decisions -->
```

**Decisions** - "Which rules does the system enforce?" The choices the code
has fixed: permissions, limits, time windows, calculations, defaults,
validation that changes outcomes, feature flags. Group by domain. One line
each: the rule in plain words, the link, and the entities or pages it
affects. Do not invent the reason; if a comment, commit message or doc states
it, cite that; otherwise the reason belongs in Open questions.

```markdown
## 关键流程
<!-- spec:section flows -->
```

**Flows** - "What happens across the system when someone does Y?" Only for
operations that cross modules or services, or that a reader cannot follow
from Lifecycles alone. A sequence diagram per flow, then the steps that
change the outcome (branches, failures, retries). Where the trail leaves the
repository (external API, queue, another service), say so.

```markdown
## 页面
<!-- spec:section pages -->
```

**Pages** - "What can each user see and do?" A page map first (which pages
exist, how they link, who can open them), then one heading per page: route,
who can open it, what it shows, what the user can do and what each action
calls, and how it handles empty, loading and error states (〔未知〕 when the
code shows no handling). Real copy from the code or i18n files, not
paraphrase.

```markdown
## 不一致与缺口
<!-- spec:section gaps -->
```

**Gaps** - "Where does the system contradict itself or stop short?" Facts
only, each with links to both sides: frontend and backend disagree, one rule
implemented twice differently, endpoints no page calls, pages calling
endpoints that do not exist, states that trap an entity, dead code paths.

```markdown
## 建议
<!-- spec:section proposals -->
```

**Proposals** - "What should change, and what would the missing parts look
like?" Separate from everything above. Each proposal points at the gap or
fact it addresses. Prototypes for missing pages or states: ASCII draft first,
prototype marker, SVG only after confirmation (`references/diagrams.md`).

```markdown
## 待 PM 补充
<!-- spec:section open-questions -->
```

**Open questions** - "What can only a person answer?" Why rules exist, target
users, success metrics, intended behaviour where the code is ambiguous. Each
question names the section it would complete.
