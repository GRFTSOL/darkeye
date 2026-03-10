'''
共享 CTE 常量，供 statistics 等混合库查询使用。
跨库的 CTE 查询无法直接在 sqlite 数据库里创建视图。
'''

masturbationsql = '''masturbation_count AS(--按照有work_id撸管记录，统计每部作品撸了几次
SELECT 
	mas.work_id AS work_id,
    w.serial_number AS serial_number,
	count(mas.work_id)AS masturbation_count
FROM priv.masturbation mas
LEFT JOIN work w ON mas.work_id=w.work_id
WHERE mas.work_id is not NULL AND mas.work_id !=''
GROUP BY mas.work_id
)
'''

masturbation_actress_sql = '''masturbation_actress AS(
SELECT 
    a.actress_id,
    -- 当前使用现用名
    (SELECT cn FROM actress_name WHERE actress_id = a.actress_id AND name_type = 1) AS actress_name,
    COUNT(m.work_id) AS num,
	MAX(m.start_time) AS latest_masturbate_time
FROM 
    actress a
LEFT JOIN work_actress_relation war ON a.actress_id = war.actress_id
LEFT JOIN work w ON war.work_id = w.work_id
LEFT JOIN priv.masturbation m ON m.work_id = w.work_id
GROUP BY a.actress_id
ORDER BY 
num DESC,
latest_masturbate_time DESC
)
'''

all_years_sql = '''
all_years AS (
    SELECT min_year AS year
    FROM year_range

    UNION ALL

    SELECT year + 1
    FROM all_years
    JOIN year_range ON year + 1 <= year_range.max_year
)
'''
