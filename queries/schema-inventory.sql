-- Read-only SQL analytics endpoint inventory for the approved synthetic schema.
-- Use the Fabric browser SQL editor; do not assume Windows Desktop or a local driver.
-- For a customer domain, an owner must review and replace this allowlist first.
SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION,
       DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'gold'
  AND TABLE_NAME IN (
      'dim_date', 'dim_plant', 'dim_line', 'dim_asset',
      'dim_shift', 'dim_product', 'dim_customer', 'dim_defect_type',
      'fact_production_run', 'fact_quality_inspection',
      'fact_maintenance_event', 'fact_customer_order', 'agg_plant_month'
  )
ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION;
