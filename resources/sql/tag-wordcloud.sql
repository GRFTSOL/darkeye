SELECT 
tag_name,
count(tag_name) AS num
FROM work_tag_relation
JOIN tag ON work_tag_relation.tag_id=tag.tag_id
WHERE tag.tag_type_id !=1 AND tag.tag_type_id !=6--取消基本信息的统计
GROUP BY tag_name
ORDER BY num DESC
