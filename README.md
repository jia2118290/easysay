# EasySay - 多语言文本转MP3工具

基于 PySide6 + edge-tts 的桌面语音合成工具，支持中/英/日/韩/法/意/西 7 种语言、128 种音色。

## 目录结构

```
EasySay/
├── main.py                      # 程序入口，只负责启动 QApplication
├── app/
│   ├── config.py                 # 全局常量、资源路径解析（兼容打包后环境）
│   ├── ui/
│   │   ├── main_window.py        # 主窗口
│   │   └── about_dialog.py       # 关于弹窗
│   ├── core/
│   │   ├── tts_worker.py         # TTS 生成后台线程（真实流式进度）
│   │   ├── validator.py          # 文本语言校验逻辑
│   │   ├── voice_repository.py   # 音色数据查询封装
│   │   └── settings_manager.py   # 配置持久化（记住上次选择）
│   ├── data/
│   │   └── voices.json           # 音色数据（可独立更新，无需改代码）
│   └── resources/
│       ├── icons/                # app.ico / app.icns / app.png
│       └── qss/dark.qss          # 深色主题样式表
├── build/
│   ├── make_logo.py               # Logo 生成脚本
│   ├── app.spec                   # PyInstaller 打包配置
│   ├── build_win.bat              # Windows 打包脚本
│   └── build_mac.sh               # macOS 打包脚本
├── tests/
│   └── test_validator.py         # 单元测试
└── requirements.txt
```

## 本地运行（开发环境）

```bash
pip install -r requirements.txt
python main.py
```

## 运行测试

```bash
python tests/test_validator.py
```

## 打包成可执行软件

⚠️ **注意：Windows 和 macOS 必须分别在对应操作系统上打包，不能交叉编译。**

### Windows

```bat
build\build_win.bat
```
打包完成后，可执行文件位于 `dist\EasySay\EasySay.exe`

### macOS

```bash
bash build/build_mac.sh
```
打包完成后，App 位于 `dist/EasySay.app`

未签名的 App 在其他 Mac 上首次运行会被 Gatekeeper 拦截，用户需要右键 → 打开来绕过。
如需正式对外分发，建议使用 Apple Developer 账号（$99/年）进行签名和公证，体验会更顺畅。

## 后续可扩展方向

- **音色数据更新**：`app/data/voices.json` 可以做成远程拉取覆盖，而不用跟着代码一起发版
- **浅色主题**：`app/resources/qss/` 下再加一份 `light.qss`，在设置里加个切换开关
- **批量生成**：支持一次性导入多段文本批量转换
- **软件签名**：Windows 用代码签名证书减少 Defender 误报；macOS 用 Apple Developer 签名+公证

## 版权声明

1. 本软件可免费自由传播使用
2. 未经授权严禁售卖，侵权行为我方将依法追究法律责任

开发者：一直要求进步的昌强同学
