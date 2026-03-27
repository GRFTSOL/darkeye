-- v1.0 -> v2.0 migration
-- 变更点：
-- 1) 新增 series 表
-- 2) work: story -> notes，新增 runtime/label_id/maker_id/series_id/fanart
-- 3) actress/actor 新增 notes
-- 4) label 新增 aliases

PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;
PRAGMA user_version = 2;--设置数据库版本号

DROP TABLE IF EXISTS db_version;--删除旧的数据库版本表。

-- 依赖 work 的视图/触发器在重建 work 前先删除
DROP TRIGGER IF EXISTS update_work_timestamp;
DROP VIEW IF EXISTS v_actress_movie_stats;
DROP VIEW IF EXISTS v_work_all_info;

-- actor 新增 notes
ALTER TABLE actor ADD COLUMN notes TEXT;

-- actress 新增 notes
ALTER TABLE actress ADD COLUMN notes TEXT;

-- label 新增 aliases
ALTER TABLE label ADD COLUMN aliases TEXT;

-- 新增 series 表
CREATE TABLE IF NOT EXISTS series(
	series_id INTEGER PRIMARY KEY AUTOINCREMENT,
	cn_name TEXT,
	jp_name TEXT,
	aliases TEXT,
	detail TEXT,
	related_series TEXT
);

-- 重建 work 表（SQLite 无法通过 ALTER TABLE 新增外键约束）


CREATE TABLE work_old(
    work_id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial_number TEXT NOT NULL UNIQUE,
    director TEXT,
    runtime INTEGER,
    notes TEXT,
    release_date TEXT,
    image_url TEXT,
    video_url TEXT,
	cn_title TEXT,
	jp_title TEXT,
	cn_story TEXT,
	jp_story TEXT,
	maker_id INTEGER,
	label_id INTEGER,
	series_id INTEGER,
	fanart TEXT,
	create_time TEXT DEFAULT (datetime('now', 'localtime')),
    update_time TEXT DEFAULT (datetime('now', 'localtime')),
	is_deleted INTEGER DEFAULT 0,
	javtxt_id INT,
	fcover_url TEXT,
	on_dan INTEGER,
	FOREIGN KEY(maker_id) REFERENCES maker(maker_id),
	FOREIGN KEY(label_id) REFERENCES label(label_id),
	FOREIGN KEY(series_id) REFERENCES series(series_id)
);

INSERT INTO work_old (
	work_id,
	serial_number,
	director,
	runtime,
	notes,
	release_date,
	image_url,
	video_url,
	cn_title,
	jp_title,
	cn_story,
	jp_story,
	maker_id,
	label_id,
	series_id,
	fanart,
	create_time,
	update_time,
	is_deleted,
	javtxt_id,
	fcover_url,
	on_dan
)
SELECT
	work_id,
	serial_number,
	director,
	NULL AS runtime,
	story AS notes,
	release_date,
	image_url,
	video_url,
	cn_title,
	jp_title,
	cn_story,
	jp_story,
	NULL AS maker_id,
	NULL AS label_id,
	NULL AS series_id,
	NULL AS fanart,
	create_time,
	update_time,
	is_deleted,
	javtxt_id,
	fcover_url,
	on_dan
FROM work;

DROP TABLE work;

ALTER TABLE work_old RENAME TO work;

-- 重建视图（story 改为 notes）
CREATE VIEW v_work_all_info AS--查询作品的基本数据的视图，这个非常的长
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
studio_list AS(--片商表
SELECT 
	w.work_id,
	(SELECT cn_name FROM maker WHERE maker_id =p.maker_id) AS studio_name
FROM 
    work w
INNER JOIN 
    prefix_maker_relation p ON p.prefix = SUBSTR(w.serial_number, 1, INSTR(w.serial_number, '-') - 1)
WHERE 
    w.serial_number LIKE '%-%'
)
SELECT --水平计算表，然后统一合并
	w.work_id,
    w.serial_number AS serial_number,
    w.director AS director,
	w.release_date AS release_date,
    w.runtime AS runtime,
	(SELECT actress_list FROM actress_list WHERE work_id=w.work_id)AS actress,
	(SELECT avg_age_at_release FROM average_age_per_work WHERE work_id=w.work_id)AS avg_age,
	(SELECT state FROM actress_list WHERE work_id=w.work_id)AS state,
	(SELECT actor_list FROM actor_list WHERE work_id=w.work_id)AS actor,
	w.notes AS notes,
	w.cn_title,
	w.cn_story,
	w.jp_title,
	w.jp_story,
	(SELECT studio_name FROM studio_list WHERE work_id=w.work_id)AS studio
FROM 
    work w;

CREATE VIEW v_actress_movie_stats AS--查询女优的作品统计数据的视图
SELECT 
    a.actress_id,
    (SELECT cn FROM actress_name WHERE actress_id = a.actress_id AND(name_type=1)) AS actress_name,
    COUNT(war.work_id) AS total_movies,
    MIN(w.release_date) AS first_movie_date,
    MAX(w.release_date) AS latest_movie_date
FROM 
    actress a
LEFT JOIN work_actress_relation war ON a.actress_id = war.actress_id
LEFT JOIN work w ON war.work_id = w.work_id
GROUP BY a.actress_id
ORDER BY total_movies DESC;

-- 重建 work 更新时间触发器
CREATE TRIGGER update_work_timestamp
AFTER UPDATE ON work
FOR EACH ROW
BEGIN
    UPDATE work
    SET update_time = DATETIME('now', 'localtime')
    WHERE work_id = OLD.work_id;
END;

CREATE VIEW v_work_avg_age_info AS--查询作品的平均年龄，用于统计查询，而且这个很常见
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
)
SELECT --水平计算表，然后统一合并
	w.work_id,
    w.serial_number AS serial_number,
	(SELECT avg_age_at_release FROM average_age_per_work WHERE work_id=w.work_id)AS avg_age
FROM 
    work w;



COMMIT;

PRAGMA foreign_keys = ON;
