-- Target table for the PutDatabaseRecord branch.
-- Column names must match the record fields (the processor translates names
-- case-insensitively and fails on unmatched columns), so no extra columns here.
--
-- DECIMAL instead of DOUBLE for the measured values: the MySQL branch reads the CSV
-- with an inferred schema, which types some decimals as 32-bit floats. Into a DOUBLE
-- column, 15.6 then lands as 15.600000381469727. DECIMAL rounds it back to 15.6.

CREATE TABLE IF NOT EXISTS cars (
  Car          VARCHAR(100)  NOT NULL,
  MPG          DECIMAL(4,1)  NOT NULL,
  Cylinders    INT           NOT NULL,
  Displacement DECIMAL(5,1)  NOT NULL,
  Horsepower   INT           NULL,
  Weight       INT           NOT NULL,
  Acceleration DECIMAL(4,1)  NOT NULL,
  Model        INT           NOT NULL,
  Origin       VARCHAR(10)   NOT NULL,
  CONSTRAINT chk_cars_origin CHECK (Origin IN ('US', 'Europe', 'Japan')),
  INDEX idx_cars_origin_model (Origin, Model)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
