"""
启动性能分析工具
用于精确测量导入时间和执行时间
"""
import time
import sys
import importlib
import logging
from contextlib import contextmanager
from typing import Optional, Dict
from functools import wraps

logger = logging.getLogger(__name__)

class StartupProfiler:
    """启动性能分析器"""
    
    def __init__(self):
        self.start_time = time.perf_counter()
        self.checkpoints: Dict[str, float] = {}
        self.import_times: Dict[str, float] = {}
        self.execution_times: Dict[str, float] = {}
        
    def checkpoint(self, name: str) -> float:
        """记录一个检查点，返回从启动到现在的总时间"""
        now = time.perf_counter()
        elapsed = now - self.start_time
        self.checkpoints[name] = elapsed
        print(f"[PROFILE] {name}: {elapsed:.4f}s (累计)")
        return elapsed
    
    def measure_import(self, module_name: str) -> float:
        """测量导入一个模块的时间"""
        start = time.perf_counter()
        try:
            # 如果已经导入，记录为0
            if module_name in sys.modules:
                elapsed = 0.0
                print(f"[IMPORT] {module_name}: {elapsed:.4f}s (已缓存)")
            else:
                __import__(module_name)
                elapsed = time.perf_counter() - start
                self.import_times[module_name] = elapsed
                print(f"[IMPORT] {module_name}: {elapsed:.4f}s")
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error(f"[IMPORT] {module_name}: FAILED ({elapsed:.4f}s) - {e}")
        return elapsed
    
    @contextmanager
    def measure_execution(self, name: str, sync: bool = True):
        """测量一段代码的执行时间（上下文管理器）"""
        start = time.perf_counter()
        sync_str = "[SYNC]" if sync else "[ASYNC]"
        print(f"{sync_str} {name}: 开始执行...")
        try:
            yield
            elapsed = time.perf_counter() - start
            self.execution_times[name] = elapsed
            print(f"{sync_str} {name}: 完成 ({elapsed:.4f}s)")
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error(f"{sync_str} {name}: 失败 ({elapsed:.4f}s) - {e}")
            raise
    
    def measure_function(self, name: Optional[str] = None, sync: bool = True):
        """装饰器：测量函数执行时间"""
        def decorator(func):
            func_name = name or f"{func.__module__}.{func.__name__}"
            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.measure_execution(func_name, sync=sync):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def print_summary(self):
        """打印性能分析摘要"""
        print("=" * 60)
        print("启动性能分析摘要")
        print("=" * 60)
        
        if self.import_times:
            print("\n导入时间 (Import Time):")
            sorted_imports = sorted(self.import_times.items(), key=lambda x: x[1], reverse=True)
            for module, elapsed in sorted_imports:
                if elapsed > 0.01:  # 只显示超过10ms的导入
                    print(f"  {module}: {elapsed:.4f}s")
        
        if self.execution_times:
            print("\n执行时间 (Execution Time):")
            sorted_execs = sorted(self.execution_times.items(), key=lambda x: x[1], reverse=True)
            for name, elapsed in sorted_execs:
                print(f"  {name}: {elapsed:.4f}s")
        
        if self.checkpoints:
            print("\n检查点时间线 (Timeline):")
            sorted_checkpoints = sorted(self.checkpoints.items(), key=lambda x: x[1])
            prev_time = 0
            for name, elapsed in sorted_checkpoints:
                delta = elapsed - prev_time
                print(f"  {name}: {elapsed:.4f}s (+{delta:.4f}s)")
                prev_time = elapsed
        
        total_time = time.perf_counter() - self.start_time
        print(f"\n总启动时间: {total_time:.4f}s")
        print("=" * 60)


# 全局单例
_profiler: Optional[StartupProfiler] = None

def get_profiler() -> StartupProfiler:
    """获取全局性能分析器"""
    global _profiler
    if _profiler is None:
        _profiler = StartupProfiler()
    return _profiler
