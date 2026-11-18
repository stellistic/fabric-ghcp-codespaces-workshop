-- Read-only SQL analytics endpoint check, independent of semantic relationships.
-- Confirm the exact approved endpoint/workspace, source version and filter context.
SELECT d.YearMonth,
       SUM(CAST(r.ActualUnits AS BIGINT)) AS [Actual Units]
FROM gold.fact_production_run AS r
JOIN gold.dim_date AS d ON r.DateKey = d.DateKey
GROUP BY d.YearMonth
ORDER BY d.YearMonth;
