
import math,random
import networkx as nx

import numpy as np
from config import ACTRESSIMAGES_PATH,WORKCOVER_PATH

def generate_random_connections(mean: float) -> int:
    """生成符合泊松分布的连接数量（用指数分布近似）"""
    # JS 中的：-Math.log(1 - Math.random()) * mean
    return round(-math.log(1 - random.random()) * mean)

def generate_random_graph(node_number=200, mean=1)-> nx.Graph:
    """生成随机图"""
    G = nx.Graph()

    # 添加节点
    for i in range(1, node_number + 1):
        G.add_node(i)

    # 随机生成边
    for i in range(1, node_number + 1):
        num_connections = generate_random_connections(mean)
        for _ in range(num_connections):
            target = random.randint(1, node_number)
            if target != i:
                G.add_edge(i, target)

    return G

def generate_graph()->nx.Graph:
    '''产生无向图'''
    
    from core.database.connection import get_connection
    from config import DATABASE
    conn=get_connection(DATABASE,True)
    cursor = conn.cursor()

    q1="""
    SELECT 
    actress_id,
    (SELECT cn FROM actress_name WHERE actress_id=actress.actress_id)AS name
    FROM
    actress
    """
    cursor.execute(q1)
    actresses = cursor.fetchall()
    q2="""
    SELECT 
    work_id,
    serial_number
    FROM
    work
    """
    cursor.execute(q2)
    works = cursor.fetchall()

    cursor.execute("SELECT work_id, actress_id FROM work_actress_relation")
    relations = cursor.fetchall()

    cursor.close()
    conn.close()

    print("开始生成图")
    #添加图
    G=nx.Graph()
            # 添加女优节点
    for aid, name in actresses:
        G.add_node(
            f"a{aid}",  # 避免与作品 id 冲突
            label=name,
            group="actress",
            color="#ff99cc"
        )
                # 添加作品节点
    for wid, title in works:
        G.add_node(
            f"w{wid}",
            label=title,
            group="work",
            color="#99ccff",
        )

    # 添加边（参演关系）
    for wid, aid in relations:
        G.add_edge(f"a{aid}", f"w{wid}")
    return G

def generate_similar_graph()->nx.Graph:
    '''计算两两作品间的相似度，产生图，相似度高于阈值的连接'''

    from scipy.sparse import lil_matrix
    from sklearn.metrics.pairwise import cosine_similarity

    #从数据库获取作品及其标签
    from core.database.connection import get_connection
    from core.database.db_utils import attach_private_db,detach_private_db
    from config import DATABASE
    conn=get_connection(DATABASE,True)
    cursor = conn.cursor()
    attach_private_db(cursor)

    q1="""
    SELECT 
    wtr.work_id,
    wtr.tag_id
    FROM
    work_tag_relation wtr
    JOIN priv.favorite_work fw ON fw.work_id=wtr.work_id
    JOIN tag ON tag.tag_id=wtr.tag_id
	JOIN tag_type ON tag_type.tag_type_id=tag.tag_type_id
	WHERE tag_type.tag_type_id  IN(1,3,7,8)
    """
    cursor.execute(q1)
    work_tags_list= cursor.fetchall()

    q2="""
    SELECT 
    w.work_id,
    w.serial_number
    FROM
    work w
    JOIN priv.favorite_work fw ON fw.work_id=w.work_id
    """
    cursor.execute(q2)
    works = cursor.fetchall()

    detach_private_db(cursor)
    cursor.close()
    conn.close()

    # work_tags_list 示例：[(1,5),(1,2),(2,5),(2,3)]
    # 先把 work_id 和 tag_id 映射到连续索引
    work_ids = sorted({w for w, t in work_tags_list})
    tag_ids = sorted({t for w, t in work_tags_list})

    # 建立 id -> index 映射  ,由于work_id，tag_id不连续
    work_id_to_idx = {w:i for i,w in enumerate(work_ids)}
    tag_id_to_idx = {t:i for i,t in enumerate(tag_ids)}

    # 构建稀疏矩阵
    row_idx = []
    col_idx = []

    for work_id, tag_id in work_tags_list:
        row_idx.append(work_id_to_idx[work_id])
        col_idx.append(tag_id_to_idx[tag_id])

    data = np.ones(len(row_idx))  # 值全为1，表示作品拥有该标签
    from scipy.sparse import csr_matrix
    # csr_matrix(shape=(num_works, num_tags))
    X = csr_matrix((data, (row_idx, col_idx)), shape=(len(work_ids), len(tag_ids)))

    print("稀疏矩阵形状:", X.shape)
    print("非零元素数量:", X.nnz)

    # 计算相似度矩阵
    sim_matrix = cosine_similarity(X)  # 或者使用 jaccard_distance_matrix
    print("相似度矩阵形状:", sim_matrix.shape)

    # 根据阈值构建图的边
    threshold = 0.7
    edges = []

    num_works = len(work_ids)
    for i in range(num_works):
        for j in range(i + 1, num_works):  # 只取上三角，避免重复
            sim = sim_matrix[i, j]
            if sim > threshold:
                edges.append((work_ids[i], work_ids[j], sim))  # (作品A, 作品B, 相似度)


    G = nx.Graph()

    for wid, title in works:
        G.add_node(
            f"w{wid}",
            label=title,
            title=f"作品: {title}",
            group="work",
            color="#99ccff",
            shape="box"
        )

    for a, b, sim in edges:
        G.add_edge(f"w{a}", f"w{b}", weight=sim)

    components = list(nx.community.greedy_modularity_communities(G))
    print("发现子图数量:", len(components))

    # 遍历每个子图

    for comp in components:
        if len(comp) <= 2:
            continue  # 小于2个节点没必要处理

        subG = G.subgraph(comp)

        # 找出中心节点（你可以改用其他中心性算法）
        centrality = nx.degree_centrality(subG)
        center_node = max(centrality, key=centrality.get)# type: ignore[arg-type]

        # 删除所有不含中心节点的边
        for u, v in list(subG.edges()):
            if center_node not in (u, v):
                G.remove_edge(u, v)

        print(f"子图 {comp} → 中心节点 {center_node}，保留星形结构")

    return G

