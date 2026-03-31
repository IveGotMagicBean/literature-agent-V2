# scripts/

## 部署脚本

| 文件 | 用途 |
|------|------|
| `app.sh` (项目根目录) | SLURM 提交主程序，集群上用 `sbatch ../app.sh` |
| `install.sh` | 一键安装所有依赖（首次部署用） |
| `start_local.sh` | 本地开发启动（自动创建 venv） |
| `ngrok.sh` | SLURM 提交 ngrok 内网穿透服务 |
| `ollama.sh` | SLURM 提交 Ollama 本地模型服务 |

## dev/ — 开发调试工具（生产环境可忽略）

| 文件 | 用途 |
|------|------|
| `check_deps.py` | 检查依赖是否正确安装 |
| `diagnose.py` | 系统整体诊断 |
| `diagnose_extraction.py` | PDF 文本提取诊断 |
| `diagnose_figure_extraction.py` | 图片提取诊断 |
| `test_api.py / test_api.sh` | API 接口测试 |
| `test_setup.py` | 环境配置测试 |
| `test_ollama.py` | Ollama 连通性测试 |
| `visualize_bbox.py` | 图片 bbox 可视化调试 |
