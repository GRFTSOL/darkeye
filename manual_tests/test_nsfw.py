
from pathlib import Path
import sys
root_dir = Path(__file__).resolve().parents[1]  # 上两级
sys.path.insert(0, str(root_dir))

from nsfw_detector import predict

from config import WORKCOVER_PATH


from PIL import Image
from nsfw_image_detector import NSFWDetector

# 1. 初始化检测器 (第一次运行会自动从 Hugging Face 下载轻量级模型)
detector = NSFWDetector()

def check_image_safety(file_path):
    try:
        # 2. 加载图片
        image = Image.open(file_path)
        
        # 3. 获取各分类概率
        # 结果通常包含: normal (正常), sexy (性感), porn (色情)
        probs = detector.predict_proba(image)
        print(f"检测结果: {probs}")
        
        # 4. 判断逻辑：如果 porn 或 sexy 概率过高，则视为不安全
        if probs['porn'] > 0.5 or probs['sexy'] > 0.7:
            return False, probs
        return True, probs
    except Exception as e:
        print(f"检测出错: {e}")
        return True, None # 出错默认放行，防止程序卡死

if __name__ == "__main__":
    is_safe, result = check_image_safety(str(WORKCOVER_PATH/"abf017pl.jpg"))
    if not is_safe:
        print("警告：该封面存在违规内容")
