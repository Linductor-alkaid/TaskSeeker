# TaskSeeker - 跨平台智能效率工具

![TaskSeeker Demo](demo.gif) <!-- 建议后续补充实际截图 -->

**突破平台限制的智能助手 | 划词翻译·OCR识别·AI增强**

## 🌟 项目简介

TaskSeeker 是一款面向现代办公场景的跨平台效率工具，深度融合OCR识别、AI语义分析和系统级交互能力，支持 Windows 10+/Ubuntu 20.04+ 双平台。通过创新的「三模交互体系」，实现：

- **精准划词翻译**：选中即译，学术文献阅读利器
- **智能截图OCR**：一键解析图片/PDF中的复杂公式
- **场景感知助手**：基于上下文提供编程/写作建议

## 🚀 功能亮点

| 功能模块         | 核心能力                                                                 |
|------------------|--------------------------------------------------------------------------|
| 智能划词         | 实时翻译、代码解释、学术术语解析                                         |
| 多模态OCR        | 表格识别、数学公式解析、多语言混合排版处理                               |
| AI工作流         | 上下文感知的连续对话、自定义Prompt模板库                               |
| 企业级特性       | 剪贴板历史管理、多显示器适配、私有化部署支持                           |

## 🛠 技术架构

```plaintext
+---------------------+
|  跨平台交互层        |  ← PyQt5 / Xlib / Win32 API
+---------------------+
|  智能处理引擎        |  ← Tesseract 5 / OpenCV / ONNXRuntime
+---------------------+
|  AI能力中台         |  ← DeepSeek API / 本地模型推理
+---------------------+
|  系统集成层         |  ← 剪贴板监控/快捷键管理/多屏渲染优化
+---------------------+
```

## 📦 安装指南

### 系统要求
- **Windows**: 10/11 (64-bit) + .NET Framework 4.8
- **Ubuntu**: 20.04+ with GNOME/KDE + X11 session

### 一键部署
```bash
git clone https://github.com/Linductor-alkaid/TaskSeeker.git
cd TaskSeeker

安装核心依赖
pip install -r requirements.txt

系统级依赖配置
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt install tesseract-ocr tesseract-ocr-chi-sim xclip libxcb-xinerama0
elif [[ "$OSTYPE" == "msys" ]]; then
    # 访问 https://github.com/UB-Mannheim/tesseract/wiki 安装Tesseract
    echo "请手动添加Tesseract安装路径到系统PATH"
fi
```

## 🔧 环境配置

1. 在项目根目录创建 `.env` 文件：

```ini
DeepSeek 服务配置
DEEPSEEK_API_KEY="sk-your-api-key-here"
DEEPSEEK_BASE_URL="https://api.deepseek.com/v1"
DEEPSEEK_TIMEOUT=30
```

2. [获取API密钥](https://platform.deepseek.com/)：
   - 注册DeepSeek账号
   - 进入控制台创建API Key
   - 复制密钥到 `.env` 文件

## 🎮 使用方法

### 系统托盘控制

右键点击任务栏图标开启功能矩阵：
- 🖱️ **即时翻译模式**：划选文本 → Ctrl+ALT+O
- 📷 **智能截图模式**：Win+Shift+S / Ctrl+ALT+P
### 核心工作流示例
**学术文献解析**：
1. 使用截图工具捕获PDF段落
2. 自动识别文本+数学公式
3. 输入 `/explain` 获取技术细节解释
4. 点击「导出Markdown」保存笔记


1. 划选注释 → 选择「生成单元测试」
2. AI生成测试用例并插入代码下方

## ⚠️ 注意事项

1. **首次运行准备**：
   ```bash
   # Linux需要授予X11访问权限
   xhost +local:$(whoami)
   
   # Windows需设置Tesseract路径
   setx TESSDATA_PREFIX "C:\Program Files\Tesseract-OCR\tessdata"
   ```

## 🤝 参与贡献

欢迎通过 Issue 提交需求或参与代码开发

## 📜 许可协议

本项目采用 **Apache 2.0** 开源协议，商业使用需遵守[DeepSeek API条款](https://www.deepseek.com/terms)。
