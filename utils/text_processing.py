# utils/text_processing.py
import platform
import logging
import time
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
        else:
            logger.error(f"Unsupported platform: {system}")
            return None
    except Exception as e:
        logger.error(f"Error getting selected text: {str(e)}")
        return None

def _windows_get_selection() -> Optional[str]:
    """Windows平台获取选中文本实现"""
    import win32clipboard
    import win32con
    import win32api
    import win32gui

    # 保存原始剪贴板内容
    try:
        win32clipboard.OpenClipboard()
        original_data = win32clipboard.GetClipboardData() if win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT) else None
    except Exception as e:
        logger.warning("Failed to get clipboard content", exc_info=True)
        original_data = None
    finally:
        win32clipboard.CloseClipboard()

    # 清空剪贴板并发送Ctrl+C
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.CloseClipboard()
        
        hwnd = win32gui.GetForegroundWindow()
        win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_CONTROL, 0)
        win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, 0x43, 0)  # VK_C
        win32api.SendMessage(hwnd, win32con.WM_KEYUP, 0x43, 0)
        win32api.SendMessage(hwnd, win32con.WM_KEYUP, win32con.VK_CONTROL, 0)
    except Exception as e:
        logger.error("Failed to simulate copy", exc_info=True)
        return None

    # 等待剪贴板更新（带超时机制）
    selected_text = None
    start_time = time.time()
    while time.time() - start_time < 1:
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                selected_text = win32clipboard.GetClipboardData()
                break
        except Exception as e:
            logger.debug("Clipboard access retrying...")
        finally:
            win32clipboard.CloseClipboard()
        time.sleep(0.05)

    # 恢复原始剪贴板内容
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        if original_data:
            win32clipboard.SetClipboardData(win32con.CF_TEXT, original_data)
    except Exception as e:
        logger.warning("Failed to restore clipboard", exc_info=True)
    finally:
        win32clipboard.CloseClipboard()

    return selected_text.decode(errors='ignore') if selected_text else ''

def _linux_get_selection() -> Optional[str]:
    """Linux平台获取选中文本实现"""
    try:
        from Xlib import X, display
        from Xlib.support import unix
        
        d = display.Display()
        window = d.get_input_focus().focus
        
        # 获取PRIMARY选择缓冲区内容
        sel = d.get_selection_owner(X.XA_PRIMARY)
        if sel == X.NONE:
            return ""
            
        sel.convert(d, X.XA_STRING, 0)
        start_time = time.time()
        while time.time() - start_time < 1:
            if sel.get_property(X.XA_STRING, 0, 0, 2**24-1):
                break
            d.io_process()
        else:
            return None
            
        response = sel.get_property(X.XA_STRING, 0, 0, 2**24-1)
        return response.value.decode('utf-8', errors='ignore') if response else ''
    except ImportError:
        # 回退到xsel命令
        return _linux_fallback_selection()

def _linux_fallback_selection() -> Optional[str]:
    """Linux备用方案（需要安装xsel）"""
    import subprocess
    
    try:
        result = subprocess.run(
            ['xsel', '-o'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=1
        )
        if result.returncode == 0:
            return result.stdout.decode('utf-8').strip()
        logger.error(f"xsel error: {result.stderr.decode()}")
    except FileNotFoundError:
        logger.error("xsel not installed. Please install with 'sudo apt install xsel'")
    except subprocess.TimeoutExpired:
        logger.error("xsel command timed out")
    
    return None

if __name__ == "__main__":
    # 测试模块
    import sys
    logging.basicConfig(level=logging.DEBUG)
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("请先选中一段文本，然后按回车继续...")
        input()
        print("选中的文本内容：", get_selected_text())