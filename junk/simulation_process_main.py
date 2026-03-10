# 模拟核心，会开一个新的进程，从程序运行开始
from multiprocessing import Process, Pipe


def _worker_entry(conn):
    # Lazy import in child process to avoid heavy imports in main process
    # 确保子进程也能正确记录日志
    import core.utils.log_config 
    from core.graph.simulation_worker import simulation_process_main
    simulation_process_main(conn)

_global_sim_parent_conn = None
_global_sim_process = None


def get_global_simulation_process():
    global _global_sim_parent_conn, _global_sim_process
    if _global_sim_process is not None and _global_sim_process.is_alive():
        return _global_sim_parent_conn

    parent_conn, child_conn = Pipe()
    _global_sim_parent_conn = parent_conn
    proc = Process(
        target=_worker_entry,
        args=(child_conn,),
        name="ForceDirectSimulationProcess",
    )
    proc.daemon = True
    proc.start()
    _global_sim_process = proc
    return _global_sim_parent_conn
