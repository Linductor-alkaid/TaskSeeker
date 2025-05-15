# utils/text_processing.py
import platform
import logging
import time
import os
from typing import Optional

logger = logging.getLogger(__name__)

def get_selected_text() -> Optional[str]:
    """
    获取当前选中的文本内容（跨平台实现）
    
    Returns:
        str|None: 选中的文本内容，获取失败返回None
    """
    system = platform.system()
    try:
        if system == 'Windows':
            return _windows_get_selection()
        elif system == 'Linux':
            return _linux_get_selection()
        elif system == 'Darwin':
            logger.error("macOS平台暂未实现")
            return None
        else:
            logger.error(f"Unsupported platform: {system}")
            return None
    except Exception as e:
        logger.error(f"Error getting selected text: {str(e)}", exc_info=True)
        return None

def _windows_get_selection() -> Optional[str]:
    """Windows平台获取选中文本实现"""
    try:
        import win32clipboard
        import win32con
        import win32api
    except ImportError:
        logger.error("请安装pywin32库: pip install pywin32")
        return None

    # 保存原始剪贴板内容
    original_data = _save_clipboard()

    try:
        # 模拟物理按键Ctrl+C
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(0x43, 0, 0, 0)  # 'C'键
        win32api.keybd_event(0x43, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        
        # 获取剪贴板内容
        return _get_clipboard_text(timeout=1)
    finally:
        _restore_clipboard(original_data)

def _save_clipboard() -> dict:
    """保存剪贴板当前内容"""
    import win32clipboard
    data = {}
    try:
        win32clipboard.OpenClipboard()
        for fmt in [win32con.CF_TEXT, win32con.CF_UNICODETEXT, win32con.CF_OEMTEXT]:
            if win32clipboard.IsClipboardFormatAvailable(fmt):
                data[fmt] = win32clipboard.GetClipboardData(fmt)
    except Exception as e:
        logger.warning("保存剪贴板失败", exc_info=True)
    finally:
        win32clipboard.CloseClipboard()
    return data

def _restore_clipboard(data: dict):
    """恢复剪贴板内容"""
    import win32clipboard
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        for fmt, content in data.items():
            win32clipboard.SetClipboardData(fmt, content)
    except Exception as e:
        logger.warning("恢复剪贴板失败", exc_info=True)
    finally:
        win32clipboard.CloseClipboard()

def _get_clipboard_text(timeout=1) -> Optional[str]:
    """等待并获取剪贴板文本"""
    import win32clipboard
    start = time.time()
    while (time.time() - start) < timeout:
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                return win32clipboard.GetClipboardData(win32con.CF_TEXT).decode('latin1')
        except Exception as e:
            logger.debug("剪贴板访问重试中...")
        finally:
            win32clipboard.CloseClipboard()
        time.sleep(0.1)
    return None

def _linux_get_selection() -> Optional[str]:
    """Linux平台获取选中文本实现"""
    # 检测会话类型
    if _is_wayland():
        return _linux_wayland_selection()
    
    try:
        from Xlib import display, X
        from Xlib.error import ConnectionClosedError
    except ImportError:
        logger.error("请安装Xlib库: sudo apt install python3-xlib")
        return _linux_fallback_selection()
    
    try:
        d = display.Display()
        window = d.get_input_focus().focus
        
        # 获取PRIMARY选择缓冲区内容
        sel = d.get_selection_owner(X.XA_PRIMARY)
        
        if sel == X.NONE:
            return None
            
        sel.convert(d, X.XA_STRING, 0)
        start = time.time()
        while time.time() - start < 1:
            if sel.get_property(X.XA_STRING, 0, 0, 2**24-1):
                break
            d.io_process()
        else:
            return None
            
        response = sel.get_property(X.XA_STRING, 0, 0, 2**24-1)
        return response.value.decode('utf-8', errors='ignore') if response else ''
    except ConnectionClosedError:
        logger.error("X服务器连接关闭")
        return _linux_fallback_selection()
    except Exception as e:
        logger.error("Xlib操作异常", exc_info=True)
        return _linux_fallback_selection()

def _is_wayland() -> bool:
    """检测是否为Wayland环境"""
    return os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland'

def _linux_wayland_selection() -> Optional[str]:
    """Wayland环境获取选中文本"""
    import subprocess
    
    try:
        result = subprocess.run(
            ['wl-paste', '--primary'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=1
        )
        if result.returncode == 0:
            return result.stdout.decode('utf-8').strip()
        logger.error(f"wl-paste错误: {result.stderr.decode()}")
    except FileNotFoundError:
        logger.error("请安装wl-clipboard: sudo apt install wl-clipboard")
    except subprocess.TimeoutExpired:
        logger.error("wl-paste命令超时")
    return None

def _linux_fallback_selection() -> Optional[str]:
    """Linux备用方案"""
    import subprocess
    if _is_wayland():
        return None  # 已在前面的函数处理
    
    # 尝试xsel/xclip
    try:
        result = subprocess.run(
            ['xsel', '-o'],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            timeout=1
        )
        if result.returncode == 0:
            return result.stdout.decode('utf-8').strip()
        # 尝试xclip
        result = subprocess.run(
            ['xclip', '-out', '-selection', 'primary'],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            timeout=1
        )
        if result.returncode == 0:
            return result.stdout.decode('utf-8').strip()
        logger.error(f"剪贴板工具错误: {result.stderr.decode()}")
    except FileNotFoundError:
        logger.error("请安装xsel或xclip: sudo apt install xsel xclip")
    except subprocess.TimeoutExpired:
        logger.error("剪贴板命令超时")
    return None