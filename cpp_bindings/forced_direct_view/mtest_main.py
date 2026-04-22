import math
import random
import sys

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

import os, sys

from pathlib import Path
import PySide6
qt_bin = Path(PySide6.__file__).resolve().parent
print(qt_bin)
here = Path(__file__).resolve().parent

if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(str(here))  # 把当前目录加入 DLL 搜索路径
    os.add_dll_directory(str(qt_bin)) 

sys.path.insert(0, str(here))       # 确保可以找到 PyForceView.pyd

import PyForceView
from PyForceView import ForceViewOpenGL


def generate_random_graph(n_nodes, avg_degree):
    """
    Standalone test helper: creates a random graph, mirroring the C++ generateRandomGraph().
    Returns:
        edges (list[int]): flat list [src0, dst0, src1, dst1, ...]
        pos (list[float]): [x0, y0, x1, y1, ...]
        ids (list[str]): external ids for each node (same type as labels)
        labels (list[str]): label for each node
        radii (list[float]): radius for each node
    """
    # Random initial positions in a circle (same formula as C++)
    scale = math.sqrt(float(n_nodes)) * 25.0 + 150.0
    pos = [0.0] * (2 * n_nodes)
    ids = [None] * n_nodes
    labels = [None] * n_nodes
    radii = [0.0] * n_nodes

    for i in range(n_nodes):
        angle = float(i) / n_nodes * 2.0 * math.pi
        r = scale * (0.3 + 0.7 * random.random())
        pos[2 * i] = r * math.cos(angle)
        pos[2 * i + 1] = r * math.sin(angle)
        ids[i]=f"A{i}" # external id as string (same type as labels)
        labels[i] = f"NN{i}"
        radii[i] = 4.0 + float(random.randrange(7))  # 4..10

    # Generate random edges (Poisson-distributed connections per node, matching C++ logic)
    edges = []
    for i in range(n_nodes):
        u = random.random()
        # -log(1 - rand) * mean, rounded (exponential approx to Poisson)
        num_connections = int(round(-math.log(1.0 - u) * avg_degree))
        for _ in range(num_connections):
            target = random.randrange(n_nodes)
            if target != i:
                edges.append(i)
                edges.append(target)

    print(f"Generated graph: {n_nodes} nodes, {len(edges) // 2} edges")
    return edges, pos, ids, labels, radii


def main():
    app = QApplication(sys.argv)

    # Keep behavior similar to C++: default to OpenGL.
    use_opengl = True


    # Generate a nodenum-node random graph
    nodenum = 1990
    edges, pos, ids, labels, radii = generate_random_graph(nodenum, 1)

    node_colors = [
        QColor(random.randrange(256), random.randrange(256), random.randrange(256))
        for _ in range(nodenum)
    ]

    def on_left_clicked(node_id: int):
        print(f"Left-clicked node: id[{node_id}]")

    def on_hovered(node_id: int):
        if node_id >= 0:
            print(f"Hovered node: id: {node_id}")

    def on_fps(fps: float):
        print(f"FPS: {fps}")

    if use_opengl:
        view = ForceViewOpenGL()
        view.setWindowTitle("ForceView OpenGL Test (Python)")
        view.resize(1000, 700)
        view.setGraph(nodenum, edges, pos, ids, labels, radii, node_colors)
        #view.nodeLeftClicked.connect(on_left_clicked)
        #view.nodeHovered.connect(on_hovered)
        #view.fpsUpdated.connect(on_fps)
        view.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()

