-- Independent raw-source oracle. DISTINCT removes exact extract duplicates.
-- Joining the authoritative date dimension rejects impossible DateKeys.
-- Kept separate from Python curation and the model's filter propagation.
WITH unique_runs AS (
    SELECT DISTINCT * FROM raw_runs
)
SELECT substr(d.Date, 1, 7) AS YearMonth,
       SUM(CAST(r.ActualUnits AS INTEGER)) AS ActualUnits
FROM unique_runs AS r
JOIN raw_dates AS d ON r.DateKey = d.DateKey
WHERE trim(r.ActualUnits) <> '' AND CAST(r.ScrapUnits AS INTEGER) >= 0
GROUP BY substr(d.Date, 1, 7)
ORDER BY YearMonth;
