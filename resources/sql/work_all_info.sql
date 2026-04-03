WITH actress_age_at_release AS (--计算每个女优发布作品的年龄
  SELECT
    w.work_id,
    a.actress_id,
    w.serial_number,
    w.release_date,
    a.birthday,
    -- 使用 julianday 计算日期差（以天为单位），然后除以 365.25 得到年龄
    (julianday(w.release_date) - julianday(a.birthday)) / 365.25 AS age_at_release
  FROM work w
  JOIN work_actress_relation war ON w.work_id = war.work_id
  JOIN actress a ON war.actress_id = a.actress_id
  WHERE w.release_date IS NOT NULL AND a.birthday IS NOT NULL
),
average_age_per_work AS (--辅助计算年龄的表
  SELECT
    work_id,
    serial_number,
    ROUND(AVG(age_at_release), 1)-0.45 AS avg_age_at_release--假设拍摄后5个多月发布
  FROM actress_age_at_release
  GROUP BY work_id
),
actress_list AS(--计算女优出演的名单
SELECT
    w.work_id,
    GROUP_CONCAT(
        (SELECT cn FROM actress_name WHERE actress_id = a.actress_id AND(name_type=1)),
        ','
    ) AS actress_list,
    GROUP_CONCAT(war.job,',') AS job,
    GROUP_CONCAT(war.state,',') AS state
FROM
    work w
LEFT JOIN 
    work_actress_relation war ON w.work_id = war.work_id
LEFT JOIN 
    actress a ON war.actress_id = a.actress_id
GROUP BY w.work_id
),
actor_list AS(--男优名单
SELECT
    w.work_id,
    GROUP_CONCAT(
        (SELECT cn FROM actor_name WHERE actor_id=war1.actor_id),
        ','
    ) AS actor_list
FROM
    work w
LEFT JOIN 
    work_actor_relation war1 ON w.work_id = war1.work_id
LEFT JOIN 
    actor a ON war1.actor_id = a.actor_id
GROUP BY w.work_id
),
tag_list AS(--标签列表
SELECT
    w.work_id,
    GROUP_CONCAT(t.tag_name, '|') AS tag_list
FROM
    work w
LEFT JOIN
    work_tag_relation wtr ON w.work_id = wtr.work_id
LEFT JOIN
    tag t ON wtr.tag_id = t.tag_id
GROUP BY w.work_id
),
maker_label_series_list AS(--片商/发行商/系列表
SELECT
    w.work_id,
    (SELECT cn_name FROM maker WHERE maker_id = w.maker_id) AS maker_name,
    (SELECT cn_name FROM label WHERE label_id = w.label_id) AS label_name,
    (SELECT cn_name FROM series WHERE series_id = w.series_id) AS series_name
FROM 
    work w
)
SELECT --水平计算表，然后统一合并
    w.work_id,
    w.serial_number AS serial_number,
    w.director AS director,
    w.release_date AS release_date,
    w.runtime AS runtime,
    (SELECT actress_list FROM actress_list WHERE work_id=w.work_id)AS actress,
    (SELECT avg_age_at_release FROM average_age_per_work WHERE work_id=w.work_id)AS avg_age,
    (SELECT actor_list FROM actor_list WHERE work_id=w.work_id)AS actor,
    (SELECT tag_list FROM tag_list WHERE work_id=w.work_id)AS tag,
    w.notes AS notes,
    w.cn_title,
    w.cn_story,
    w.jp_title,
    w.jp_story,
    (SELECT maker_name FROM maker_label_series_list WHERE work_id=w.work_id) AS maker,
    (SELECT label_name FROM maker_label_series_list WHERE work_id=w.work_id) AS label,
    (SELECT series_name FROM maker_label_series_list WHERE work_id=w.work_id) AS series
FROM 
    work w;