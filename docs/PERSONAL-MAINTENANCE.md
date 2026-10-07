# 个人版本维护说明

## 仓库与分支

- `upstream`：原作者 `AnCode666/multiCAD-mcp`，用于获取更新；本地已禁用向它推送。
- `origin`：个人仓库 `WangCheng0902/multiCAD-mcp`。本地地址已设置，首次推送前须完成 GitHub Fork。
- `main`：保持与原作者主分支一致，本地跟踪 `upstream/main`。
- `codex/personal-autocad`：个人开发分支，保留当前 CAD 线程调度、COM 读取保护和本机配置。

当前代码是已有修改的备份，尚未完成 AutoCAD 实机回归测试。配置修改与代码修改分别提交，方便将来单独迁移或贡献通用修复。保留原项目 README、作者信息和许可证。

## 首次完成 Fork 和推送

在 https://github.com/AnCode666/multiCAD-mcp/fork 创建 Fork，Owner 选择 `WangCheng0902`，名称保持 `multiCAD-mcp`。然后在项目目录执行：

```powershell
git fetch origin
git push -u origin codex/personal-autocad
```

Fork 默认主分支可以继续保持 `main`。个人功能先在 `codex/personal-autocad` 维护，不需要立即合入 `main`。

## 获取并查看原作者更新

开始新工作前或准备升级时执行：

```powershell
git fetch upstream
git log --oneline main..upstream/main
```

`fetch` 只获取更新，不会改动正在运行的个人版本。这个配置不会定时自动拉取；需要执行上述命令。

## 更新基线并合入个人版本

先提交或妥善保存未提交改动，确认 `git status --short` 没有输出。随后执行：

```powershell
git switch main
git merge --ff-only upstream/main
git push origin main
git switch codex/personal-autocad
git merge upstream/main
```

每一步成功后再执行下一步。如果个人分支合并出现冲突，检查双方修改并解决；想取消本次合并可执行 `git merge --abort`。不要用强制推送或硬重置来解决冲突。

合并后，在 AutoCAD 中检查连接、对象读取、图层和块统计、视图刷新、修改操作及断开连接；通过后执行：

```powershell
git push
```

## 日常个人开发

在个人分支开发，提交时明确选择要保存的文件，然后推送到自己的仓库。大型新功能可以从个人分支再建立 `codex/功能名称` 分支。

机器专用的 `src/config.json` 设置应继续单独提交。当前配置加载器不会读取 `config.local.json`；虽然该文件被 Git 忽略，直接把配置移过去不会生效。若以后需要支持不同电脑，可先增加本地配置加载机制，再迁移本机设置。

向原作者贡献修复时，从 `upstream/main` 新建分支，只选择通用修复，补充验证后通过自己的 Fork 提交 PR，避免包含本机专用配置。
