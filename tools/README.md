# memoryctl - Daily Memory Loop Engine

`memoryctl` 是 Daily Memory 的确定性循环引擎，参考 [rowboat](https://github.com/rowboatlabs/rowboat) 知识图谱流水线(`graph_state.ts` / `build_graph.ts` / `run_pipeline.ts`)的 loop engineering 设计：

- 每个处理阶段是一个**小型幂等循环**，由独立状态文件驱动；
- **mtime + content hash** 双重增量检测，只处理新增/变更的文件；
- **小批量提交**：每批成功后立即持久化状态，中断后可断点恢复；
- **确定性代码管 loop 机制，LLM(宿主 agent)只做循环体内的判断**；
- 知识图谱是 Obsidian 兼容的 Markdown vault，`[[wikilink]]` 即图谱边。

引擎零依赖(Python 3.10+ 标准库)，不调用任何模型 API。

## 运行方式

```bash
python3 <skill>/tools/memoryctl.py --workdir <workdir> <command> ...
```

`<workdir>` 是 Daily Memory 工作区(例如 `~/.openclaw/workspace-daily-memory`)，也可通过环境变量 `DAILY_MEMORY_WORKDIR` 指定。

## 循环一览

| Loop | 类型 | 输入 | 循环体 | 输出 |
| --- | --- | --- | --- | --- |
| `classify` | llm | `sources/**/*.md` | agent 按 `prompts/classify_source.md` 给源文件补 `relevance` frontmatter | 源文件标注 |
| `graph` | llm | relevance 为 `event`/`context` 的源文件 | agent 按 `prompts/note_creation.md` 创建/合并 vault 笔记 | `knowledge/**` 笔记 |
| `attention` | llm | 开放状态的 `knowledge/Events/*.md`(变更/到期/过期) | agent 按 `prompts/attention.md` 更新 attention 字段与建议 | Event 笔记 attention 更新 |
| `index` | deterministic | `knowledge/**` | 引擎内联执行 | `index/edges.json` + `knowledge/daily-memory-<date>.md` 桥接笔记 |

## Agent 外层循环

```text
while true:
  result = memoryctl run --steps classify,graph,attention,index
  if result.done: break
  读取 result.next_action.batch_file 中列出的文件
  按 result.next_action.prompt_path 的提示词处理这一批
  memoryctl commit --loop <loop> --batch <batch_id>
```

`run` 在第一个仍有待处理工作的 LLM loop 处停下(下游 loop 依赖上游输出)，确定性 loop(`index`)内联执行。

## 命令

```bash
memoryctl init                                  # 创建工作区目录骨架
memoryctl scan --loop graph [--batch-size 25]   # 产出/恢复下一批工作单
memoryctl commit --loop graph --batch <id>      # 校验后提交一批(增量保存状态)
memoryctl fail --loop graph --batch <id> --reason "..."  # 标记失败，文件回到待处理
memoryctl validate [paths...]                   # 校验 vault 笔记 schema 与 wikilink
memoryctl index [--date YYYY-MM-DD]             # 重建 edges.json 与桥接笔记
memoryctl run [--steps classify,graph,attention,index]   # 流水线驱动，输出 next_action
memoryctl status                                # 每个 loop 的 total/processed/pending
memoryctl reset --loop graph | --all            # 清空状态，强制重建
```

## 状态与批次文件

```text
<workdir>/
  state/
    classify_state.json      # {"processed": {"<relpath>": {"mtime", "hash", "last_processed"}}}
    graph_state.json
    attention_state.json
    batches/<loop>/<batch_id>.json   # 工作单: files + prompt + status(pending/committed/failed)
  index/edges.json           # 派生的 wikilink 边与反链索引
```

关键行为：

- `scan` 优先返回已存在的 pending 批次(断点恢复)，不会重复发放同一文件。
- `commit` 在**提交时**重新计算文件 hash(classify 循环体会就地改写源文件 frontmatter)。
- `graph`/`attention` 的 commit 先跑 vault 校验，schema 错误会阻止提交(`--force` 可覆盖)。
- 只改 mtime 不改内容的文件会被 hash 校验识别为未变更并跳过。

## 测试

```bash
cd tools && python3 -m pytest tests/ -v
```
