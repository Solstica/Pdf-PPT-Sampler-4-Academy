# Pdf-PPT-Sampler-4-Academy 1.2 (release candidate)

确定性的课件图像工具 + 独立的多模态 AI 复习协议。Python 不依赖大模型 API，不 OCR、不提取文字、不总结。支持 Python 3.10+；Windows 为主要环境，PDF 处理使用跨平台 PyMuPDF/Pillow。

## V1.2.3 每份资料的 README

trans 在每个已发布文档目录生成 README.md，包含原始文件名、原始相对路径、稳定文档 ID、首次归档时间（UTC）、页数和源文件 SHA256，附 manifest.json 链接。首次归档时间采用 manifest 首次进入 Git 历史的提交时间，不是 GitHub 服务器接收时间。升级后下一次 trans CODE 自动补齐旧文档 README，时间从 Git 历史恢复，缺少历史则明确标记未知。已有 README 不覆盖，重复同步不刷新时间；支持根目录和多级分组。原始 PDF/PPT 仍不上传。

## V1.2.2 双语进度与容量统计

~~~bash
trans PP --lang zh
trans PP --lang en
export ACADEMY_SAMPLER_LANG=zh
trans PP --group Notes -pre 1
academy render --lang zh
~~~

默认英文；--lang 覆盖环境变量。仅本工具的进度标签、阶段和常见 Git 进度前缀翻译，原始 Git 错误、JSON 和帮助文本保留原样。中文终端需要 UTF-8；窄终端定期换行输出，宽 TTY 单行刷新。

转换中显示选中原件总大小、已确认图像字节（含缓存）、新生成图像字节、预计选中图像最终大小；按已处理文档的页均值估算，未采样文档借用同预设的页均值，无足够数据时为 --，失败时不报告完整预测。转换结束给出选中图像占原件比例和全部归档图像实际大小。暂存阶段统计本次变更文件逻辑字节数，Git 原生进度显示实际 pack 写入量和速率；三者不等同，均不包含完整 Git 历史和本地 raw 镜像所需磁盘空间。单位为二进制 KiB/MiB/GiB。

## V1.2.1 终端实时进度

trans 与 academy render 均显示逐页进度（已处理/总页数、实际新转换、缓存跳过、失败、页/秒、已用时间和 ETA）。ETA 按近期页面完成速率估算，初始样本不足时显示 --:--:--。终端支持时单行刷新，重定向输出或非 TTY 时定期打印进度。扫描、Office 页数探测、校验、暂存和隐私检查分别显示阶段提示。

trans 上传使用 git push --progress，实时显示 Git 的对象计数、压缩、写入百分比、数据量及速率（由 Git 提供）。当有足够对象写入样本时附加 object ETA；它仅估算对象写入阶段，不代表服务器确认或整个流程的剩余时间。对象 100% 后仍须等待 Git push 成功。空推送不会伪造上传百分比。

## V1.2 增量与目录分类

已绑定远程的课程可以直接运行 trans PP，不再需要仓库地址。

~~~bash
trans PP
trans PP --group Notes -pre 1
trans PP --group Homework -pre 3
trans PP --group "Teacher A/Week 1"
trans PP --group .
~~~

--group 选择 raw 下相对目录及其后代；. 仅选根目录文件。同步时仍扫描和注册全课程新增原件，但仅转换/上传所选组中的新资料，其他已发布资料继续出现在完整索引中。-pre 与 --group 同用时保存该组的独立预设（最长匹配目录优先），不改变课程默认值。未指定 --group 时同步全部，使用各组已保存预设。

新增文件保持 raw 层级，GitHub 页面存储在 sources/by-group/<子目录>/<文档ID>/；根目录资料仍为 sources/<文档ID>/。全课程唯一编号追加，不按组重新编号。sources/GROUPS.md 按当前 raw 目录分类，链接到真实 manifest。原有 V1.1 文档保留原路径；移动已注册文件时依据唯一 SHA256 匹配更新分类，原页面 URL 和 ID 不改变。若手工改名，保留该新文件名，但文档 ID 不变。相同哈希的多候选、源内容修改或删除会安全拒绝。使用 trans --show PP 查看当前路径与分组预设。

升级后无需重建课程注册表或再次注册。旧版课件索引和复习资料不会删除。V1.2 候选版的实际 CI 状态见 Actions。

## V1.1 快速命令（trans）

安装 Git、GitHub CLI（gh）、Python 3.10+。先完成 SSH 或 HTTPS Git 凭据配置；使用 gh auth login 授权查询仓库可见性。工具不会读取或上传令牌。

~~~bash
python -m pip install --user pipx
python -m pipx ensurepath
# Reopen the shell after ensurepath.
pipx install "academy-sampler[windows] @ git+https://github.com/Solstica/Pdf-PPT-Sampler-4-Academy.git"
gh auth login
trans "D:/Courses/Material/raw" CM -pre 3
trans CM git@github.com:YOUR_ACCOUNT/PRIVATE-COURSE.git
~~~

升级已有 pipx 安装：pipx upgrade academy-sampler。Windows Git Bash 可用 D:/... 路径；Linux/macOS 省略 windows extra。若 Bash 中已有同名 translate-shell 命令，使用 type -a trans 检查 PATH 顺序，优先选择本工具的 pipx 可执行文件。Windows Git Bash 实际全局 PATH 仍需本机验收。

第一条命令只登记课程并在原目录安全重命名 PDF/PPT/PPTX，保留子目录及原始文件名映射；第二条命令自动发现新增文件、渲染、完整性校验并向已存在的 Private GitHub 仓库普通 push。不会发送 raw、打印 PDF 或全局本地注册表。每个课件有稳定编号，如 CM01-P003。已生成的 GitHub 复习稿及阅读状态不会被覆盖。

| -pre | 长边 | WebP质量 |
|---|---:|---:|
|1|1920|90|
|2|1600|80|
|3（默认）|1280|75|
|4|1024|70|
|5|800|60|

~~~bash
trans --list
trans --show CM
trans "D:/Courses/Material/raw" CM --dry-run
trans "D:/Moved/raw" CM --relocate
trans CM git@github.com:YOUR_ACCOUNT/PRIVATE-COURSE.git -pre 4
~~~

在任意目录均可执行。课程注册表在 ~/.academy-sampler/courses.json（ACADEMY_SAMPLER_HOME 可覆盖）。原件由本地 raw 管理；另有一份哈希校验的本地镜像以复用原 academy 工作区与矢量打印。注册使用同目录独占硬链接再删除旧名称，NTFS、常见 Linux/macOS 文件系统可用；不支持硬链接的文件系统会安全失败。执行中断后重复原命令恢复 journal，不要手工删除 journal 或中途修改文件。原件内容改变时拒绝沿用旧 ID；恢复原件并把新版本作为独立新文件加入。已有课程只能绑定同一远程，旧版课程仓库若 ID/manifest 格式冲突须迁移后再发布。

发布前后核实 GitHub 可见性，公开仓库或无法验证时终止。推送失败时保留本地提交，普通重试；分支冲突或未提交改动需要人工核对，不自动重置。只有经过完整验证的 manifest 及其列出的图像进入发布清单；复习协议模板缺失时才补充。旧 academy 命令继续可用。详见 docs/V1.1_TRANS_SPEC.md 和 docs/LIMITATIONS.md。

## 安装与快速开始

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[test,windows]"
.venv/Scripts/academy init my-course
cd my-course
# 把 PDF/PPT/PPTX 放入 raw 下的对应分组
academy ingest
academy render
academy validate
academy index
academy progress
academy batch --document L01 --size 15
academy render --document L01 --pages 3-8 --preset inspection
academy print --pages L01-P003,L02-P006 --output print/selected.pdf
```

激活虚拟环境后可直接执行 academy。Linux/macOS 使用 `.venv/bin/activate`，安装 `pip install -e ".[test]"`。所有命令支持 --help；`academy --workspace PATH COMMAND` 指定工作区。

## 配置与稳定来源

course.yaml 定义课程、教师（可选）、考试要求、任意分组路径、唯一 ASCII 前缀、教学顺序 order 和预设。order 为组内相对路径列表；其余自然排序。默认 lectures=L、notes=N、homework=H、exams=E；notes 使用 inspection，避免无条件低清压缩。编号不表示章节。

原件不移动、不改名、不修改。同路径同哈希不分配新号；移动后尽可能按哈希识别并保存路径历史；相同内容并存时保留且报告。内容变化时拒绝，使用 `academy ingest --new-version` 注册新 ID，旧引用保留，旧原件应由用户归档保留以便验证和打印。新文件追加编号。不要同时运行多个写入命令。

## 图像与索引

|预设|长边|质量|
|---|---:|---:|
|compact|1024|70|
|balanced|1280|75|
|detailed|1920|90|
|inspection|2560|95|

预设可配置；render 支持 --input、--document、--group、--pages、--preset、--long-edge、--quality、--format webp/png/jpg/jpeg、--force。WebP method 6，RGB 白底、完整页面、原色、不裁切拼接增强，含空白页。PNG 无损编码不使用 quality。实际参数按页写入 manifest。

sources 下每文档独立目录、manifest、index.json、INDEX.md、source_registry.json 和 SOURCE_REGISTRY.md；页面引用如 L01-P003 永久稳定。batch 生成有序图像路径清单，不声称 AI 已读。缓存检查源哈希、页码、参数、转换器版本及实际图像 SHA256/解码；每页检查点支持断点恢复。局部渲染保留其他页面。validate 检查真实图像、页数、比例、元数据、来源及全局索引。部分渲染在尚无其他页面时会被完整性检查正确标记为未完成。

## AI 协议与打印

详见 AGENTS.md、protocols/ 与工作区 review 模板。阅读状态默认 pending；由 AI/用户实际读图后显式登记：

```bash
academy progress --page L01-P003 --state read
academy progress --page L01-P004 --state needs_high_resolution --reason "formula unclear"
academy print --list review/PRINT_LIST.md
academy print --list reports/print_pages.json
```

JSON 打印清单为字符串数组；Markdown 按出现顺序提取有效格式 page_id，保留重复。跨文档打印直接复制原始 PDF 页面，保留矢量对象，绝不从压缩图片重建。PPT 使用临时 PDF。

## Office、隐私与测试

Windows 优先本机 PowerPoint（安装 windows extra）；其他平台或 PowerPoint 不可用时使用 PATH 中 LibreOffice，macOS 可安装 LibreOffice 并将 soffice 加入 PATH。包含隐藏页；记录页数差异、备用导出和字体人工核验警告。无法可靠导出则提示手动导出 PDF。临时文件自动清理。字体、动画和动态对象无法保证与源演示播放一致，须目视核对。

公开工具仓库与私人课程工作区必须分离。默认忽略 raw、sources、review、print、reports、来源映射与真实复习材料，旧版 academy 不自动 push；显式 trans 发布命令例外，必须验证私人仓库。若自行同步：先核实目标仓库 private、审查 staged 文件和授权，再自行选择提交；工具不会修改可见性。

`python -m pytest -q` 只生成合成 PDF；`python examples/synthetic_demo.py OUTPUT` 创建可复现演示。验收见 TEST_RESULTS.md，迁移见 docs/MIGRATION.md，限制见 docs/LIMITATIONS.md。
