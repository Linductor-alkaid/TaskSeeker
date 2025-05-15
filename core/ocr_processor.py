# core/ocr_processor.py
import pytesseract
import cv2
import numpy as np
import logging
import re
import os
import time
from typing import Optional, Tuple
from config import global_config
from PIL import Image, ImageEnhance
import platform

logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self):
        self._init_tesseract()
        self.mathpix_enabled = global_config.get('ocr.enable_mathpix', False)
        self.mathpix_appid = global_config.get('ocr.mathpix_appid', '')
        self.mathpix_key = global_config.get('ocr.mathpix_key', '')
        self.languages = global_config.get('ocr.languages', 'eng+chi_sim')
        self.test_mode = global_config.get('ocr.test_mode', False)  # 测试模式开关
        
        # 初始化公式检测模型
        self.formula_pattern = re.compile(
            r'(\${2,}(?:[^\$]|\$[^\$])+\${2,}|\\begin\{.*?}.*?\\end\{.*?})',
            re.DOTALL
        )

    def _init_tesseract(self):
        """配置 Tesseract 路径（根据平台自动处理）"""
        if global_config.get('ocr.tesseract_path'):
            pytesseract.pytesseract.tesseract_cmd = global_config.get('ocr.tesseract_path')
        elif platform.system() == 'Linux':
            pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        elif platform.system() == 'Windows':
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    def preprocess_image(self, img: np.ndarray) -> np.ndarray:
        """图像预处理增强 OCR 准确率"""
        try:
            # 转换为 PIL 格式进行增强处理
            pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            
            # 对比度增强
            enhancer = ImageEnhance.Contrast(pil_img)
            pil_img = enhancer.enhance(1.5)
            
            # 转换为 OpenCV 格式进行后续处理
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # # 自适应阈值二值化
            # processed = cv2.adaptiveThreshold(
            #     gray, 255,
            #     cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            #     cv2.THRESH_BINARY, 5, 2
            # )
            
            return gray
            
        except Exception as e:
            logger.error(f"图像预处理失败: {str(e)}")
            return img

    def recognize_text(self, img: np.ndarray) -> str:
        """
        执行 OCR 识别
        返回格式化的 Markdown 文本
        """
        try:
            # 预处理图像
            processed = self.preprocess_image(img)

            # 测试模式：保存预处理后的图像
            if self.test_mode:
                self._save_processed_image(processed)
            
            # 使用 Tesseract 进行识别
            text = pytesseract.image_to_string(
                processed,
                lang=self.languages,
                config='--psm 6 --oem 3'
            )
            
            # 后处理
            text = self._postprocess_text(text)
            
            # 公式检测与增强
            if self.mathpix_enabled:
                text = self._enhance_with_mathpix(text, img)
                
            return text
            
        except Exception as e:
            logger.error(f"OCR 识别失败: {str(e)}")
            return ""
        
    def _save_processed_image(self, img: np.ndarray):
        """保存预处理后的图像到test目录"""
        try:
            os.makedirs('test', exist_ok=True)
            timestamp = int(time.time() * 1000)
            filename = f'processed_{timestamp}.png'
            cv2.imwrite(os.path.join('test', filename), img)
            logger.info(f"已保存预处理图像至: test/{filename}")
        except Exception as e:
            logger.error(f"保存预处理图像失败: {str(e)}")

    def _postprocess_text(self, text: str) -> str:
        """文本后处理"""
        # 合并单词断行（保留连字符断行）
        text = re.sub(r'-\n\s*', '', text)  # 处理带连字符的断行
        # 保留原始换行和缩进
        text = re.sub(r'(?<=\S)\n(?=\S)', ' ', text)  # 合并同一段落内的换行
        text = re.sub(r'\n\s+\n', '\n\n', text)  # 标准化段落间距
        # 保留Markdown格式的特殊符号
        text = re.sub(r'\\\$(?!\w)', '$', text)  # 还原转义符号
        return text.strip()

    def _enhance_with_mathpix(self, text: str, img: np.ndarray) -> str:
        """使用 Mathpix 增强公式识别"""
        try:
            # 检测可能的公式位置
            formula_regions = self._detect_formula_regions(text, img)
            
            for (x, y, w, h) in formula_regions:
                # 裁剪公式区域
                formula_img = img[y:y+h, x:x+w]
                
                # 调用 Mathpix API
                latex = self._call_mathpix_api(formula_img)
                if latex:
                    # 替换原始文本中的公式部分
                    text = self._replace_formula(text, (x, y), latex)
                    
            return text
            
        except Exception as e:
            logger.warning(f"公式增强失败: {str(e)}")
            return text

    def _detect_formula_regions(self, text: str, img: np.ndarray) -> list:
        """检测可能的公式区域"""
        # 基于文本模式检测
        candidates = []
        for match in self.formula_pattern.finditer(text):
            start = match.start()
            end = match.end()
            
            # 获取对应的图像区域（需要实现坐标映射）
            region = self._map_text_position_to_image(start, end, img)
            if region:
                candidates.append(region)
                
        return candidates

    def _call_mathpix_api(self, img: np.ndarray) -> Optional[str]:
        """调用 Mathpix API 识别公式"""
        if not self.mathpix_appid or not self.mathpix_key:
            return None
            
        try:
            _, img_bytes = cv2.imencode('.png', img)
            response = requests.post(
                'https://api.mathpix.com/v3/text',
                files={'file': ('formula.png', img_bytes)},
                headers={
                    'app_id': self.mathpix_appid,
                    'app_key': self.mathpix_key
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('latex_styled')
            return None
            
        except Exception as e:
            logger.warning(f"Mathpix API 调用失败: {str(e)}")
            return None

    def _map_text_position_to_image(self, start: int, end: int, img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        将文本位置映射到图像区域（简化实现）
        实际需要结合 Tesseract 的布局分析
        """
        # 获取 OCR 布局信息
        data = pytesseract.image_to_data(
            img, lang=self.languages,
            output_type=pytesseract.Output.DICT
        )
        
        # 遍历识别结果寻找对应区域
        for i in range(len(data['text'])):
            if data['conf'][i] == '-1':
                continue
                
            text_start = sum(len(t) for t in data['text'][:i])
            text_end = text_start + len(data['text'][i])
            
            if start >= text_start and end <= text_end:
                return (
                    data['left'][i],
                    data['top'][i],
                    data['width'][i],
                    data['height'][i]
                )
        return None

    def _replace_formula(self, original: str, position: Tuple[int, int], latex: str) -> str:
        """替换原始文本中的公式部分"""
        # 根据公式类型添加 Markdown 标记
        # 去除多余空白字符
        latex = re.sub(r'\s+', ' ', latex).strip()
        
        # 判断公式类型
        is_block = any([
            '\\begin{' in latex,
            '\\[' in latex,
            '$$' in original,
            len(latex.split('\n')) > 1
        ])
        
        replacement = f'$$\n{latex}\n$$' if is_block else f'${latex}$'
        
        # 替换次数控制（避免重复替换）
        return original.replace(original[position[0]:position[1]], replacement, 1)
    
    def _validate_markdown(self, text: str) -> str:
        """校验和修正Markdown格式"""
        # 平衡公式分隔符
        text = re.sub(r'\${2,}(?!\s)', '$$', text)  # 确保公式分隔符成对
        text = re.sub(r'(?<!\\)\$', r'\\$', text)  # 转义游离的$
        # 规范代码块
        text = re.sub(r'```(?!\w)', '```\n', text)
        return text

if __name__ == "__main__":
    # 测试代码
    import sys
    logging.basicConfig(level=logging.INFO)
    
    processor = OCRProcessor()
    
    # 从文件读取测试图像
    test_img = cv2.imread('test_formula.png')
    if test_img is None:
        print("请准备测试图像")
        sys.exit(1)
        
    result = processor.recognize_text(test_img)
    print("识别结果：\n", result)