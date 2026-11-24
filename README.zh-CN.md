# pm-spec

[English](README.md)

一个 agent skill：根据已有代码库写出**现状功能规格**，并在每个 PR 上保持更新。

规格写给没写过这些代码的人：产品经理、设计师、测试、新加入的工程师。内容包括实体及其关系、实体生命周期、代码固化的业务规则、关键流程、页面，以及缺失部分的原型。每条事实都链接到证明它的源码行，由脚本逐条校验。

它不是 PRD。代码只能说明系统做了什么，说明不了为什么做、怎样衡量成功；这些问题会集中列出，留给人来回答。

## 产出

```
docs/spec/
├── spec.md          # 规格
├── spec.pdf         # PDF 版，spec.md 或图有变化就重新生成
├── changes.md       # 每个 PR 对规格的改动
├── diagrams/        # PlantUML 源文件和渲染出的 SVG
└── prototypes/      # SVG 原型，ASCII 稿确认后才画
```

`spec.md` 的章节：读者 · 概述 · 实体 · 实体关系 · 生命周期 · 业务决定 · 关键流程 · 页面 · 不一致与缺口 · 建议 · 待 PM 补充。

## 工作方式

| 步骤 | 由谁完成 |
|---|---|
| 找出实体、状态、规则、页面和入口的定义位置 | `scripts/scan.py` |
| 确定读者，列出范围内的全部内容，逐节写作 | 模型（大型代码库拆给子代理） |
| 校验每个链接、行号和引文，标出没有来源的事实 | `scripts/check_spec.py` |
| 删除重复和不必要的内容 | 独立子代理（`references/reviewer.md`） |
| 在本地把 PlantUML 渲染成 SVG | `scripts/render_diagrams.py` |
| 用本地无头 Chrome 把 spec.md 打印成 PDF，没变化就跳过 | `scripts/render_pdf.py` |

写作规则：一个事实只写一处；删掉不影响理解的内容；现状和建议分开；代码不能直接证明的标〔推断〕，代码里没有的标〔未知〕。

原型先画 ASCII，有人确认逻辑和文案后才画 SVG。

## 持续更新

在 PR 上运行 `check_spec.py --diff <base> --fix-lines`：

- 代码只是移动了位置的事实，自动修正行号，文件改名也会跟上；
- 引用的代码行被改动的事实，列出来交给 agent 重读并改写；
- 没有任何事实引用的改动代码，列出来交给 agent 判断是否新增了实体、状态、规则或页面。

agent 只更新受影响的部分，记入 `changes.md`，提交到 PR 分支，并在 PR 里评论摘要。规格没有变化就不提交。

本地运行：让 agent 更新规格。每个 PR 自动运行：使用 `templates/spec-update.yml`（GitHub Actions，基于 `anthropics/claude-code-action`；需要配置 `ANTHROPIC_API_KEY` secret；每次运行产生 API 费用；跳过来自 fork 的 PR）。

## 安装

```bash
git clone https://github.com/RessCris2/pm-spec.git ~/.claude/skills/pm-spec
```

然后提出需求，例如：“根据代码写一份功能规格”。

环境要求：Python 3.10+、git。画图需要 PATH 中有 `plantuml`，或者 Java 加 `PLANTUML_JAR=/path/to/plantuml.jar`。图不会发送到远程渲染服务。

## 测试

```bash
python3 -m unittest discover -s tests
```

## 许可

MIT
