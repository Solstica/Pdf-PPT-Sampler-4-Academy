# Pdf-PPT-Sampler-4-Academy 1.0

确定性的课件图像工具 + 独立的多模态 AI 复习协议。Python 不依赖大模型 API，不 OCR、不提取文字、不总结。支持 Python 3.10+；Windows 为主要环境，PDF 处理使用跨平台 PyMuPDF/Pillow。

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

公开工具仓库与私人课程工作区必须分离。默认忽略 raw、sources、review、print、reports、来源映射与真实复习材料，不自动 push。若自行同步：先核实目标仓库 private、审查 staged 文件和授权，再自行选择提交；工具不会修改可见性。

`python -m pytest -q` 只生成合成 PDF；`python examples/synthetic_demo.py OUTPUT` 创建可复现演示。验收见 TEST_RESULTS.md，迁移见 docs/MIGRATION.md，限制见 docs/LIMITATIONS.md。
