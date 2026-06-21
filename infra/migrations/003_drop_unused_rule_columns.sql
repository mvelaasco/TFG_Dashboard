ALTER TABLE association_rules
  DROP COLUMN IF EXISTS rhs_support,
  DROP COLUMN IF EXISTS conviction,
  DROP COLUMN IF EXISTS inclusion,
  DROP COLUMN IF EXISTS interestingness,
  DROP COLUMN IF EXISTS comprehensibility,
  DROP COLUMN IF EXISTS yulesq,
  DROP COLUMN IF EXISTS zhang;
